import json
import os
from time import monotonic

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from groq import Groq

from .models import Translation
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
        "history.html",
        {"page_obj": page_obj, "query": query},
    )


@login_required
def delete_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    translation.delete()
    return redirect("history")


@login_required
def clear_history(request):
    Translation.objects.filter(user=request.user).delete()
    return redirect("history")


@login_required
def reload_translation(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    return render(request, "translation.html", {"translation": translation})


def home(request):
    return render(
        request,
        "core/translator.html",
        {"languages": SUPPORTED_LANGUAGES, "max_query_bytes": MAX_QUERY_BYTES},
    )


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
    return JsonResponse(
        {
            "translated_text": result.translated_text,
            "match": result.match,
            "latency_ms": latency_ms,
            "word_count": len(source_text.split()),
            "provider": "mymemory",
        }
    )


def history(request):
    from django.shortcuts import render

    entries = [
        {
            "source": "EN → ES",
            "target": "Spanish",
            "text": "The architectural design of the system enforces...",
            "translation": "El diseño arquitectónico del sistema garantiza...",
            "time": "2 hours ago",
        },
        {
            "source": "FR → EN",
            "target": "English",
            "text": "Veuillez agréer, Monsieur, l'expression d...",
            "translation": "Please accept, Sir, the expression of my...",
            "time": "5 hours ago",
        },
        {
            "source": "DE → EN",
            "target": "English",
            "text": "Die Benutzeroberfläche wurde für maxi...",
            "translation": "The user interface has been optimized f...",
            "time": "Yesterday",
        },
        {
            "source": "EN → JP",
            "target": "Japanese",
            "text": "API keys are required to authenticate re...",
            "translation": "APIキーが必要です。",
            "time": "Yesterday",
        },
    ]

    return render(request, "core/history.html", {"entries": entries})


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
