from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.http import JsonResponse
from groq import Groq
import os
from .models import Translation


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
        {"page_obj": page_obj, "query": query},
    )


@login_required
def delete_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    translation.delete()
    return redirect("core/history.html")


@login_required
def clear_history(request):
    Translation.objects.filter(user=request.user).delete()
    return redirect("core/history.html")


@login_required
def reload_translation(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    return render(request, "translation.html", {"translation": translation})
def home(request):
    from django.shortcuts import render

    return render(request, "core/translator.html")


def translator(request):
    from django.shortcuts import render

    return render(request, "core/translator.html")



def transcribe_audio(request):
    """
    Receives an audio file, transcribes it using Whisper (with auto-language detection),
    and returns the text as JSON.
    """
    if request.method == 'POST':
        audio_file = request.FILES.get('audio_data')
        
        if not audio_file:
            return JsonResponse({'error': 'No audio file provided'}, status=400)

        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))

            # Whisper automatically detects the spoken language
            transcription = client.audio.transcriptions.create(
                file=(audio_file.name, audio_file.read()),
                model="whisper-large-v3",
                response_format="json"
            )

            # Return successful transcription
            return JsonResponse({'text': transcription.text})
            
        except Exception as e:
            return JsonResponse({'error': f"Transcription API Error: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Invalid request method. POST required.'}, status=405)
