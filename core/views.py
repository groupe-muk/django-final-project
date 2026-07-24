from django.http import HttpResponse
from django.http import JsonResponse
from groq import Groq
import os



def home(request):
    from django.shortcuts import render

    return render(request, "core/translator.html")


def translator(request):
    from django.shortcuts import render

    return render(request, "core/translator.html")


def history(request):
    from django.shortcuts import render

    entries = [
        {
            "source": "English",
            "target": "French",
            "text": "The report was approved this morning.",
            "translation": "Le rapport a été approuvé ce matin.",
            "time": "2 min ago",
        },
        {
            "source": "Spanish",
            "target": "English",
            "text": "Necesitamos revisar los detalles finales.",
            "translation": "We need to review the final details.",
            "time": "14 min ago",
        },
        {
            "source": "German",
            "target": "English",
            "text": "Bitte senden Sie die aktualisierte Version.",
            "translation": "Please send the updated version.",
            "time": "1 hour ago",
        },
    ]

    return render(request, "core/history.html", {"entries": entries})


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