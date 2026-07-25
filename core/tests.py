import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from core.services.mymemory import (
    TranslationQuotaError,
    TranslationResult,
    translate_text,
)


class PageTests(SimpleTestCase):
    def test_home_status_and_languages(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "English")
        self.assertContains(response, "French")


class TranslationEndpointTests(SimpleTestCase):
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
