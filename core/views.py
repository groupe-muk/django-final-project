import json
import os
from io import BytesIO
from pathlib import Path
from time import monotonic

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation as i18n
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from groq import Groq

from .models import Language, Translation
from .services.document_export import (
    DocumentExportError,
    SUPPORTED_OUTPUT_FORMATS,
    build_download,
)
from .services.document_extract import DocumentExtractError, extract_text
from .services.long_translate import translate_long_text
from .services.mymemory import (
    MAX_QUERY_BYTES,
    TranslationQuotaError,
    TranslationServiceError,
    translate_text,
)
from .utils import get_client_ip, get_country


SUPPORTED_LANGUAGES = [
    {"code": "ar", "name": "Arabic"},
    {"code": "zh-CN", "name": "Chinese (Simplified)"},
    {"code": "en", "name": "English"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "hi", "name": "Hindi"},
    {"code": "it", "name": "Italian"},
    {"code": "ja", "name": "Japanese"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "es", "name": "Spanish"},
    {"code": "sw", "name": "Swahili"},
]
SUPPORTED_LANGUAGE_CODES = {language["code"] for language in SUPPORTED_LANGUAGES}
SUPPORTED_LANGUAGE_NAMES = {
    language["code"]: language["name"] for language in SUPPORTED_LANGUAGES
}


@require_GET
def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        return JsonResponse({"status": "unhealthy"}, status=503)
    return JsonResponse({"status": "ok"})


def get_language(code):
    language, _ = Language.objects.get_or_create(
        code=code,
        defaults={"name": SUPPORTED_LANGUAGE_NAMES[code]},
    )
    return language


@login_required
def history(request):
    query = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "all").strip().lower()
    valid_modes = {"all", "text", "voice", "document"}
    if mode not in valid_modes:
        mode = "all"

    translations = Translation.objects.filter(user=request.user).select_related(
        "source_lang", "target_lang"
    )

    if mode != "all":
        translations = translations.filter(input_mode=mode)

    if query:
        translations = translations.filter(
            Q(source_text__icontains=query)
            | Q(translated_text__icontains=query)
            | Q(document_name__icontains=query)
            | Q(source_lang__name__icontains=query)
            | Q(target_lang__name__icontains=query)
            | Q(source_lang__code__icontains=query)
            | Q(target_lang__code__icontains=query)
        )

    paginator = Paginator(translations, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/history.html",
        {
            "page_obj": page_obj,
            "query": query,
            "mode": mode,
            "languages": SUPPORTED_LANGUAGES,
        },
    )


@login_required
@require_POST
def delete_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    translation.delete()
    messages.success(request, _("Translation deleted."))
    return redirect("history")


@login_required
@require_POST
def clear_history(request):
    Translation.objects.filter(user=request.user).delete()
    messages.success(request, _("Translation history cleared."))
    return redirect("history")


@login_required
@require_POST
def edit_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)

    source_lang_code = request.POST.get("source_lang", "")
    target_lang_code = request.POST.get("target_lang", "")
    translated_text = request.POST.get("translated_text", "").strip()

    if translation.is_document:
        source_text = translation.source_text
        document_name = request.POST.get("document_name", translation.document_name).strip()
    else:
        source_text = request.POST.get("source_text", "").strip()
        document_name = ""

    if translation.is_document:
        if not translated_text:
            messages.error(request, _("Translated text is required."))
        elif not document_name:
            messages.error(request, _("Document name is required."))
        elif (
            source_lang_code not in SUPPORTED_LANGUAGE_CODES
            or target_lang_code not in SUPPORTED_LANGUAGE_CODES
        ):
            messages.error(request, _("Select supported source and target languages."))
        elif source_lang_code == target_lang_code:
            messages.error(request, _("Source and target languages must be different."))
        else:
            with transaction.atomic():
                translation.source_lang = get_language(source_lang_code)
                translation.target_lang = get_language(target_lang_code)
                translation.document_name = document_name
                translation.source_text = f"[Document] {document_name}"
                translation.translated_text = translated_text
                translation.word_count = len(translated_text.split())
                translation.save()
            messages.success(request, _("Document translation updated."))
    elif not source_text or not translated_text:
        messages.error(request, _("Original and translated text are required."))
    elif (
        source_lang_code not in SUPPORTED_LANGUAGE_CODES
        or target_lang_code not in SUPPORTED_LANGUAGE_CODES
    ):
        messages.error(request, _("Select supported source and target languages."))
    elif source_lang_code == target_lang_code:
        messages.error(request, _("Source and target languages must be different."))
    else:
        with transaction.atomic():
            translation.source_lang = get_language(source_lang_code)
            translation.target_lang = get_language(target_lang_code)
            translation.source_text = source_text
            translation.translated_text = translated_text
            translation.save()
        messages.success(request, _("Translation updated."))

    return redirect("history")

# Maps an ipinfo.io country code to one of the UI languages declared in
# settings.LANGUAGES. Anything not listed here (or any lookup failure)
# falls back to the default LANGUAGE_CODE.
COUNTRY_LANGUAGE = {
    # French-speaking
    "FR": "fr",
    "BE": "fr",
    "CH": "fr",
    "CA": "fr",
    "SN": "fr",
    "CI": "fr",
    # German-speaking
    "DE": "de",
    "AT": "de",
    "LI": "de",
    # Russian-speaking
    "RU": "ru",
    "BY": "ru",
    "KZ": "ru",
    "KG": "ru",
    # Arabic-speaking
    "SA": "ar",
    "AE": "ar",
    "EG": "ar",
    "MA": "ar",
    "DZ": "ar",
    "TN": "ar",
    "IQ": "ar",
    "JO": "ar",
    "LB": "ar",
    "LY": "ar",
    "SY": "ar",
    "YE": "ar",
    "OM": "ar",
    "QA": "ar",
    "KW": "ar",
    "BH": "ar",
    "SD": "ar",
    "PS": "ar",
    # East Africa
    "KE": "sw",
    "TZ": "sw",
    "UG": "en",
}


@login_required
@require_POST
def download_history_translation(request, id):
    """Download a saved history translation as .txt or .docx."""
    translation = get_object_or_404(Translation, id=id, user=request.user)
    output_format = str(request.POST.get("output_format") or "docx").lower()
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        messages.error(request, _("Choose txt or docx as the download format."))
        return redirect("history")

    basename = "linguashift-translation"
    if translation.document_name:
        stem = Path(translation.document_name).stem or basename
        basename = f"{stem}-translated"

    try:
        download = build_download(
            translation.translated_text,
            output_format,
            basename=basename,
        )
    except DocumentExportError as exc:
        messages.error(request, str(exc))
        return redirect("history")

    return FileResponse(
        BytesIO(download.content),
        as_attachment=True,
        filename=download.filename,
        content_type=download.content_type,
    )

def home(request):
    """Landing page. On a visitor's first request (no language cookie set
    yet), best-effort detect their country from IP and activate the
    matching UI language, persisting it in the same cookie Django's
    built-in `set_language` view uses.

    `LocaleMiddleware` reads that cookie on every later request
    automatically, so detection only needs to run once per visitor.
    """
    detected_language = None
    if settings.LANGUAGE_COOKIE_NAME not in request.COOKIES:
        ip = get_client_ip(request)
        country = get_country(ip)
        detected_language = COUNTRY_LANGUAGE.get(country, i18n.get_language() or "en")
        i18n.activate(detected_language)

    response = render(
        request,
        "core/translator.html",
        {"languages": SUPPORTED_LANGUAGES, "max_query_bytes": MAX_QUERY_BYTES},
    )

    if detected_language:
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            detected_language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )

    return response


def translator(request):
    return render(
        request,
        "core/translator.html",
        {"languages": SUPPORTED_LANGUAGES, "max_query_bytes": MAX_QUERY_BYTES},
    )


@require_POST
def translate_api(request):
    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Content-Type must be application/json."},
            status=415,
        )

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    source_text = str(payload.get("source_text") or "").strip()
    source_lang = str(payload.get("source_lang") or "")
    target_lang = str(payload.get("target_lang") or "")

    if not source_text:
        return JsonResponse({"error": "Enter text to translate."}, status=400)
    if source_lang not in SUPPORTED_LANGUAGE_CODES:
        return JsonResponse({"error": "Select a supported source language."}, status=400)
    if target_lang not in SUPPORTED_LANGUAGE_CODES:
        return JsonResponse({"error": "Select a supported target language."}, status=400)
    if source_lang == target_lang:
        return JsonResponse(
            {"error": "Source and target languages must be different."},
            status=400,
        )

    byte_count = len(source_text.encode("utf-8"))
    if byte_count > MAX_QUERY_BYTES:
        return JsonResponse(
            {
                "error": (
                    f"Text is {byte_count} UTF-8 bytes; "
                    f"MyMemory accepts at most {MAX_QUERY_BYTES}."
                )
            },
            status=400,
        )

    started_at = monotonic()
    try:
        result = translate_text(source_text, source_lang, target_lang)
    except TranslationQuotaError as exc:
        return JsonResponse({"error": str(exc)}, status=429)
    except TranslationServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    latency_ms = round((monotonic() - started_at) * 1000)
    translation = None
    if request.user.is_authenticated:
        with transaction.atomic():
            translation = Translation.objects.create(
                user=request.user,
                source_lang=get_language(source_lang),
                target_lang=get_language(target_lang),
                source_text=source_text,
                translated_text=result.translated_text,
                input_mode="text",
                latency_ms=latency_ms,
                was_successful=True,
            )

    return JsonResponse(
        {
            "translation_id": translation.id if translation else None,
            "translated_text": result.translated_text,
            "match": result.match,
            "latency_ms": latency_ms,
            "word_count": len(source_text.split()),
            "provider": "mymemory",
            "saved": translation is not None,
        }
    )


def _validate_language_pair(source_lang: str, target_lang: str):
    if source_lang not in SUPPORTED_LANGUAGE_CODES:
        return JsonResponse({"error": "Select a supported source language."}, status=400)
    if target_lang not in SUPPORTED_LANGUAGE_CODES:
        return JsonResponse({"error": "Select a supported target language."}, status=400)
    if source_lang == target_lang:
        return JsonResponse(
            {"error": "Source and target languages must be different."},
            status=400,
        )
    return None


@require_POST
def translate_document(request):
    """Extract text from an uploaded document, translate it, and return JSON."""
    uploaded = request.FILES.get("document")
    if not uploaded:
        return JsonResponse({"error": "Choose a document to upload."}, status=400)

    source_lang = str(request.POST.get("source_lang") or "")
    target_lang = str(request.POST.get("target_lang") or "")
    language_error = _validate_language_pair(source_lang, target_lang)
    if language_error is not None:
        return language_error

    try:
        source_text = extract_text(uploaded, source_lang=source_lang)
    except DocumentExtractError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        result = translate_long_text(source_text, source_lang, target_lang)
    except TranslationQuotaError as exc:
        return JsonResponse({"error": str(exc)}, status=429)
    except TranslationServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    translation = None
    document_name = Path(getattr(uploaded, "name", "") or "document").name
    if request.user.is_authenticated:
        with transaction.atomic():
            translation = Translation.objects.create(
                user=request.user,
                source_lang=get_language(source_lang),
                target_lang=get_language(target_lang),
                source_text=f"[Document] {document_name}",
                translated_text=result.translated_text,
                document_name=document_name,
                input_mode="document",
                latency_ms=result.latency_ms,
                word_count=result.word_count,
                was_successful=True,
            )

    return JsonResponse(
        {
            "translation_id": translation.id if translation else None,
            "source_text": result.source_text,
            "translated_text": result.translated_text,
            "document_name": document_name,
            "match": result.match,
            "latency_ms": result.latency_ms,
            "word_count": result.word_count,
            "chunk_count": result.chunk_count,
            "provider": "mymemory",
            "saved": translation is not None,
        }
    )


@require_POST
def download_translation(request):
    """Build and return a downloadable translated .txt or .docx file."""
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse(
                {"error": "Request body must be a JSON object."},
                status=400,
            )
        translated_text = str(payload.get("translated_text") or "").strip()
        output_format = str(payload.get("output_format") or "docx").lower()
    else:
        translated_text = str(request.POST.get("translated_text") or "").strip()
        output_format = str(request.POST.get("output_format") or "docx").lower()

    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        return JsonResponse(
            {"error": "Choose txt or docx as the download format."},
            status=400,
        )

    try:
        download = build_download(translated_text, output_format)
    except DocumentExportError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return FileResponse(
        BytesIO(download.content),
        as_attachment=True,
        filename=download.filename,
        content_type=download.content_type,
    )

@require_POST
def transcribe_audio(request):
    """
    Receives an audio file, transcribes it using Whisper (with auto-language detection),
    and returns the text as JSON.
    """
    audio_file = request.FILES.get('audio_data')
    if not audio_file:
        return JsonResponse({'error': 'No audio file provided.'}, status=400)

    content_type = getattr(audio_file, 'content_type', '') or ''
    if not content_type.startswith('audio/'):
        return JsonResponse({'error': 'Uploaded file must be an audio file.'}, status=400)

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return JsonResponse({'error': 'Server is missing GROQ_API_KEY configuration.'}, status=503)

    try:
        client = Groq(api_key=api_key)

        # Whisper automatically detects the spoken language.
        transcription = client.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model="whisper-large-v3",
            response_format="json",
        )

        text = (getattr(transcription, 'text', '') or '').strip()
        if not text:
            return JsonResponse({'error': 'No speech detected in the uploaded audio.'}, status=422)

        return JsonResponse({'text': text})
    except Exception as exc:
        return JsonResponse({'error': f'Transcription API Error: {exc}'}, status=502)

