import json
from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Language, Translation
from core.services.mymemory import (
    TranslationQuotaError,
    TranslationResult,
    translate_text,
)
from core.utils import get_country


class PageTests(SimpleTestCase):
    @patch("core.views.get_country", return_value=None)
    def test_home_status_and_languages(self, mock_get_country):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "English")
        self.assertContains(response, "French")


class LanguageDetectionTests(TestCase):
    """Covers the IP -> country -> UI language auto-detect feature."""

    def _language_cookie(self):
        cookie = self.client.cookies.get(settings.LANGUAGE_COOKIE_NAME)
        return cookie.value if cookie else None

    @patch("core.views.get_country", return_value="FR")
    def test_first_visit_activates_language_for_detected_country(self, mock_get_country):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._language_cookie(), "fr")
        # "Translator" nav link should render in French.
        self.assertContains(response, "Traducteur")
        mock_get_country.assert_called_once()

    @patch("core.views.get_country", return_value=None)
    def test_falls_back_to_default_language_when_country_unknown(self, mock_get_country):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._language_cookie(), "en")
        self.assertContains(response, "Translator")

    @patch("core.views.get_country", return_value="SA")
    def test_arabic_speaking_country_gets_rtl_arabic_ui(self, mock_get_country):
        response = self.client.get("/")

        self.assertEqual(self._language_cookie(), "ar")
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "المترجم")  # "Translator" in Arabic

    @patch("core.views.get_country", return_value="FR")
    def test_detection_only_runs_once_per_visitor(self, mock_get_country):
        self.client.get("/")
        self.client.get("/")

        mock_get_country.assert_called_once()

    def test_manual_language_switcher_overrides_detection(self):
        response = self.client.post(
            reverse("set_language"),
            {"language": "de", "next": "/"},
        )

        self.assertRedirects(response, "/")
        self.assertEqual(self._language_cookie(), "de")

        response = self.client.get("/")
        self.assertContains(response, "Übersetzer")  # "Translator" in German


class GetCountryUtilTests(SimpleTestCase):
    def test_returns_none_for_local_ip_without_network_call(self):
        with patch("core.utils.requests.get") as mock_get:
            result = get_country("127.0.0.1")

        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch("core.utils.requests.get")
    def test_returns_country_from_successful_response(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"country": "DE"}
        mock_get.return_value = response

        result = get_country("8.8.8.8")

        self.assertEqual(result, "DE")

    @patch("core.utils.requests.get", side_effect=requests.exceptions.Timeout)
    def test_returns_none_on_timeout(self, mock_get):
        self.assertIsNone(get_country("8.8.8.8"))

    @patch("core.utils.requests.get", side_effect=requests.exceptions.ConnectionError)
    def test_returns_none_on_connection_error(self, mock_get):
        self.assertIsNone(get_country("8.8.8.8"))

    @patch("core.utils.requests.get")
    def test_returns_none_on_bad_status(self, mock_get):
        response = Mock()
        response.raise_for_status.side_effect = requests.exceptions.HTTPError
        mock_get.return_value = response

        self.assertIsNone(get_country("8.8.8.8"))


class HealthCheckTests(TestCase):
    def test_health_check_reports_ready(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class TranslationEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="translator",
            password="test-password",
        )
        self.client.force_login(self.user)

    def post_translation(self, payload):
        return self.client.post(
            reverse("translate_api"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    @patch("core.views.translate_text")
    def test_successful_translation(self, mock_translate):
        mock_translate.return_value = TranslationResult(
            translated_text="Bonjour tout le monde",
            match=0.98,
        )

        response = self.post_translation(
            {
                "source_text": "Hello world",
                "source_lang": "en",
                "target_lang": "fr",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["translated_text"], "Bonjour tout le monde")
        self.assertEqual(response.json()["provider"], "mymemory")
        self.assertTrue(response.json()["saved"])
        mock_translate.assert_called_once_with("Hello world", "en", "fr")

        saved = Translation.objects.select_related(
            "source_lang", "target_lang"
        ).get()
        self.assertEqual(saved.user, self.user)
        self.assertEqual(saved.source_lang.code, "en")
        self.assertEqual(saved.target_lang.code, "fr")
        self.assertEqual(saved.source_text, "Hello world")
        self.assertEqual(saved.translated_text, "Bonjour tout le monde")
        self.assertEqual(saved.word_count, 2)

    @patch("core.views.translate_text")
    def test_anonymous_user_can_translate_without_creating_history(
        self, mock_translate
    ):
        mock_translate.return_value = TranslationResult(
            translated_text="Bonjour tout le monde",
            match=0.98,
        )
        self.client.logout()

        response = self.post_translation(
            {
                "source_text": "Hello world",
                "source_lang": "en",
                "target_lang": "fr",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["translated_text"], "Bonjour tout le monde")
        self.assertFalse(response.json()["saved"])
        self.assertIsNone(response.json()["translation_id"])
        self.assertFalse(Translation.objects.exists())
        mock_translate.assert_called_once_with("Hello world", "en", "fr")

    def test_rejects_empty_text(self):
        response = self.post_translation(
            {"source_text": " ", "source_lang": "en", "target_lang": "fr"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Enter text to translate.")

    def test_rejects_same_language(self):
        response = self.post_translation(
            {"source_text": "Hello", "source_lang": "en", "target_lang": "en"}
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_unknown_language(self):
        response = self.post_translation(
            {"source_text": "Hello", "source_lang": "xx", "target_lang": "fr"}
        )

        self.assertEqual(response.status_code, 400)

    def test_limit_is_measured_in_utf8_bytes(self):
        response = self.post_translation(
            {
                "source_text": "日" * 167,
                "source_lang": "ja",
                "target_lang": "en",
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("501 UTF-8 bytes", response.json()["error"])

    @patch("core.views.translate_text")
    def test_reports_quota_exhaustion(self, mock_translate):
        mock_translate.side_effect = TranslationQuotaError("Quota reached.")

        response = self.post_translation(
            {"source_text": "Hello", "source_lang": "en", "target_lang": "fr"}
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "Quota reached.")
        self.assertFalse(Translation.objects.exists())


class TranslationHistoryTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user("owner", password="test-password")
        self.other_user = user_model.objects.create_user(
            "someone-else",
            password="test-password",
        )
        self.english = Language.objects.create(code="en", name="English")
        self.french = Language.objects.create(code="fr", name="French")
        self.spanish = Language.objects.create(code="es", name="Spanish")
        self.translation = Translation.objects.create(
            user=self.user,
            source_lang=self.english,
            target_lang=self.french,
            source_text="Hello",
            translated_text="Bonjour",
        )
        Translation.objects.create(
            user=self.other_user,
            source_lang=self.english,
            target_lang=self.spanish,
            source_text="Private",
            translated_text="Privado",
        )
        self.client.force_login(self.user)

    def test_history_only_displays_the_current_users_translations(self):
        response = self.client.get(reverse("history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello")
        self.assertNotContains(response, "Private")

    def test_translation_can_be_edited_from_history(self):
        response = self.client.post(
            reverse("edit_history", args=[self.translation.id]),
            {
                "source_lang": "en",
                "target_lang": "es",
                "source_text": "Hello there",
                "translated_text": "Hola",
            },
        )

        self.assertRedirects(response, reverse("history"))
        self.translation.refresh_from_db()
        self.assertEqual(self.translation.target_lang, self.spanish)
        self.assertEqual(self.translation.source_text, "Hello there")
        self.assertEqual(self.translation.translated_text, "Hola")
        self.assertEqual(self.translation.word_count, 2)

    def test_user_cannot_edit_another_users_translation(self):
        other_translation = Translation.objects.get(user=self.other_user)

        response = self.client.post(
            reverse("edit_history", args=[other_translation.id]),
            {
                "source_lang": "en",
                "target_lang": "fr",
                "source_text": "Changed",
                "translated_text": "Changed",
            },
        )

        self.assertEqual(response.status_code, 404)
        other_translation.refresh_from_db()
        self.assertEqual(other_translation.source_text, "Private")

    def test_delete_requires_post(self):
        response = self.client.get(
            reverse("delete_history", args=[self.translation.id])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Translation.objects.filter(id=self.translation.id).exists())


class MyMemoryClientTests(SimpleTestCase):
    @patch("core.services.mymemory.requests.get")
    def test_parses_provider_response(self, mock_get):
        provider_response = Mock()
        provider_response.raise_for_status.return_value = None
        provider_response.json.return_value = {
            "responseStatus": 200,
            "quotaFinished": False,
            "responseData": {
                "translatedText": "J&#39;aime Django",
                "match": "0.87",
            },
        }
        mock_get.return_value = provider_response

        result = translate_text("I like Django", "en", "fr")

        self.assertEqual(result.translated_text, "J'aime Django")
        self.assertEqual(result.match, 0.87)
        _, request_kwargs = mock_get.call_args
        self.assertEqual(request_kwargs["params"]["langpair"], "en|fr")
        self.assertEqual(request_kwargs["params"]["mt"], "1")

    @patch("core.services.mymemory.requests.get")
    def test_detects_provider_quota_response(self, mock_get):
        provider_response = Mock()
        provider_response.raise_for_status.return_value = None
        provider_response.json.return_value = {
            "responseStatus": 200,
            "quotaFinished": True,
            "responseData": {},
        }
        mock_get.return_value = provider_response

        with self.assertRaises(TranslationQuotaError):
            translate_text("Hello", "en", "fr")
