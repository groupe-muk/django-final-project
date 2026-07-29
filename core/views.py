import json
import os
from time import monotonic

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from groq import Groq

from .models import Language, Translation
from .services.mymemory import (
    MAX_QUERY_BYTES,
    TranslationQuotaError,
    TranslationServiceError,
    translate_text,
)


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

    translations = Translation.objects.filter(user=request.user).select_related(
        "source_lang", "target_lang"
    )

    if query:
        translations = translations.filter(
            Q(source_text__icontains=query) | Q(translated_text__icontains=query)
        )

    paginator = Paginator(translations, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/history.html",
        {
            "page_obj": page_obj,
            "query": query,
            "languages": SUPPORTED_LANGUAGES,
        },
    )


@login_required
@require_POST
def delete_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    translation.delete()
    messages.success(request, "Translation deleted.")
    return redirect("history")


@login_required
@require_POST
def clear_history(request):
    Translation.objects.filter(user=request.user).delete()
    messages.success(request, "Translation history cleared.")
    return redirect("history")


@login_required
@require_POST
def edit_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)

    source_text = request.POST.get("source_text", "").strip()
    translated_text = request.POST.get("translated_text", "").strip()
    source_lang_code = request.POST.get("source_lang", "")
    target_lang_code = request.POST.get("target_lang", "")

    if not source_text or not translated_text:
        messages.error(request, "Original and translated text are required.")
    elif (
        source_lang_code not in SUPPORTED_LANGUAGE_CODES
        or target_lang_code not in SUPPORTED_LANGUAGE_CODES
    ):
        messages.error(request, "Select supported source and target languages.")
    elif source_lang_code == target_lang_code:
        messages.error(request, "Source and target languages must be different.")
    else:
        with transaction.atomic():
            translation.source_lang = get_language(source_lang_code)
            translation.target_lang = get_language(target_lang_code)
            translation.source_text = source_text
            translation.translated_text = translated_text
            translation.save()
        messages.success(request, "Translation updated.")

    return redirect("history")

from django.shortcuts import render
from .utils import get_country, get_client_ip

COUNTRY_LANGUAGE = {
    "UG": "en",
    "KE": "sw",
    "TZ": "sw",
    "FR": "fr",
}

def home(request):
    if "language" not in request.session:
        ip = get_client_ip(request)
        country = get_country(ip)

        language = COUNTRY_LANGUAGE.get(country, "en")
        request.session["language"] = language

    return render(request, "core/translator.html", {"languages":SUPPORTED_LANGUAGES, "max_query_bytes": MAX_QUERY_BYTES})


   

def translator(request):
    return render(
        request,
        "core/translator.html",
        {"languages": SUPPORTED_LANGUAGES, "max_query_bytes": MAX_QUERY_BYTES},
    )

def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        ip = forwarded.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip


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
