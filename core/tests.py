import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Language, Translation
from core.services.mymemory import (
    TranslationQuotaError,
    TranslationResult,
    translate_text,
)
from core.services.chunking import chunk_text
from core.services.document_export import build_download
from core.services.document_extract import DocumentExtractError, extract_text
from core.services.long_translate import translate_long_text
from django.core.files.uploadedfile import SimpleUploadedFile


class PageTests(SimpleTestCase):
    def test_home_status_and_languages(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "English")
        self.assertContains(response, "French")


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

    def test_history_can_filter_by_document_mode(self):
        Translation.objects.create(
            user=self.user,
            source_lang=self.english,
            target_lang=self.french,
            source_text="[Document] brief.pdf",
            translated_text="Bonjour",
            document_name="brief.pdf",
            input_mode="document",
            word_count=1,
        )

        response = self.client.get(reverse("history"), {"mode": "document"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "brief.pdf")
        self.assertNotContains(response, "Hello")


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


class ChunkingTests(SimpleTestCase):
    def test_short_text_is_single_chunk(self):
        self.assertEqual(chunk_text("Hello world"), ["Hello world"])

    def test_chunks_respect_utf8_byte_limit(self):
        # Each "日" is 3 UTF-8 bytes; 200 chars = 600 bytes.
        text = "日" * 200
        chunks = chunk_text(text, max_bytes=500)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.encode("utf-8")), 500)


class DocumentExportTests(SimpleTestCase):
    def test_builds_txt_download(self):
        download = build_download("Bonjour", "txt")
        self.assertEqual(download.content, b"Bonjour")
        self.assertTrue(download.filename.endswith(".txt"))

    def test_builds_docx_download(self):
        download = build_download("Bonjour", "docx")
        self.assertTrue(download.content.startswith(b"PK"))
        self.assertTrue(download.filename.endswith(".docx"))


class DocumentExtractTests(SimpleTestCase):
    def test_extracts_plain_text(self):
        uploaded = SimpleUploadedFile("note.txt", b"Hello from a file")
        self.assertEqual(extract_text(uploaded), "Hello from a file")

    def test_rejects_unsupported_extension(self):
        uploaded = SimpleUploadedFile("note.csv", b"a,b,c")
        with self.assertRaises(DocumentExtractError):
            extract_text(uploaded)

    def test_rejects_oversize_upload(self):
        oversized = SimpleUploadedFile("big.txt", b"x" * 2_000_000)
        with self.assertRaises(DocumentExtractError) as ctx:
            extract_text(oversized)
        self.assertIn("too large", str(ctx.exception).lower())

    @patch("core.services.document_extract.requests.post")
    def test_extracts_image_via_ocr_space(self, mock_post):
        provider = Mock()
        provider.raise_for_status.return_value = None
        provider.json.return_value = {
            "IsErroredOnProcessing": False,
            "ParsedResults": [{"ParsedText": "Hello from OCR"}],
        }
        mock_post.return_value = provider

        with self.settings(OCR_SPACE_API_KEY="test-key"):
            uploaded = SimpleUploadedFile(
                "scan.png",
                b"\x89PNG\r\n\x1a\nfake",
                content_type="image/png",
            )
            self.assertEqual(extract_text(uploaded, source_lang="en"), "Hello from OCR")


class DocumentTranslationEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="docs",
            password="test-password",
        )
        self.client.force_login(self.user)

    @patch("core.views.translate_long_text")
    @patch("core.views.extract_text")
    def test_translates_uploaded_document(self, mock_extract, mock_translate):
        mock_extract.return_value = "Hello world from a document"
        mock_translate.return_value = type(
            "Result",
            (),
            {
                "source_text": "Hello world from a document",
                "translated_text": "Bonjour le monde depuis un document",
                "match": 0.9,
                "latency_ms": 120,
                "chunk_count": 1,
                "word_count": 5,
            },
        )()

        response = self.client.post(
            reverse("translate_document"),
            {
                "source_lang": "en",
                "target_lang": "fr",
                "document": SimpleUploadedFile("note.txt", b"Hello world from a document"),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["translated_text"], "Bonjour le monde depuis un document")
        self.assertEqual(payload["chunk_count"], 1)
        self.assertTrue(payload["saved"])
        saved = Translation.objects.get()
        self.assertEqual(saved.input_mode, "document")
        self.assertEqual(saved.document_name, "note.txt")
        self.assertEqual(saved.source_text, "[Document] note.txt")
        self.assertNotIn("Hello world from a document", saved.source_text)
        self.assertEqual(saved.word_count, 5)

    def test_history_shows_document_name_not_extracted_text(self):
        english = Language.objects.create(code="en", name="English")
        french = Language.objects.create(code="fr", name="French")
        Translation.objects.create(
            user=self.user,
            source_lang=english,
            target_lang=french,
            source_text="[Document] report.pdf",
            translated_text="Bonjour le rapport",
            document_name="report.pdf",
            input_mode="document",
            word_count=3,
        )

        response = self.client.get(reverse("history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "report.pdf")
        self.assertContains(response, "Document")
        self.assertContains(response, "English → French")
        self.assertNotContains(response, "[Document] report.pdf")

    def test_rejects_missing_document(self):
        response = self.client.post(
            reverse("translate_document"),
            {"source_lang": "en", "target_lang": "fr"},
        )
        self.assertEqual(response.status_code, 400)

    def test_download_translation_returns_file(self):
        response = self.client.post(
            reverse("download_translation"),
            data=json.dumps(
                {"translated_text": "Bonjour", "output_format": "txt"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"Bonjour")
        self.assertIn("attachment", response["Content-Disposition"])


class LongTranslateTests(SimpleTestCase):
    @patch("core.services.long_translate.translate_text")
    def test_translates_multiple_chunks(self, mock_translate):
        mock_translate.side_effect = lambda text, *_args: TranslationResult(
            translated_text=f"T({text[:8]})",
            match=0.9,
        )
        long_text = "AAAA " * 40
        result = translate_long_text(long_text, "en", "fr", max_bytes=40)
        self.assertGreaterEqual(result.chunk_count, 2)
        self.assertGreaterEqual(mock_translate.call_count, 2)
        self.assertTrue(result.translated_text.startswith("T("))
