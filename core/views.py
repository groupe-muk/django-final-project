from django.http import HttpResponse
from django.http import JsonResponse
from groq import Groq
import os



def home(request):
    return HttpResponse("Hello, Django base project!")


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