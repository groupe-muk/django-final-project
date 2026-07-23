let mediaRecorder;
let audioChunks = [];

// Logic for Live Microphone Recording
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            // Package the raw audio chunks into a WAV file
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioFile = new File([audioBlob], "live_recording.wav", { type: 'audio/wav' });
            
            // Send to Django
            await sendAudioToDjango(audioFile);
        };

        mediaRecorder.start();
        console.log("Microphone live. Recording...");
    } catch (err) {
        console.error("Microphone access denied:", err);
        alert("Please allow microphone permissions in your browser to record audio.");
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        console.log("Recording stopped. Processing audio...");
    }
}

// Logic for File Uploads (.mp3, .wav, etc.)
async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (file) {
        console.log("Audio file selected. Processing...");
        await sendAudioToDjango(file);
    }
}

// Send Data to Django Backend
async function sendAudioToDjango(audioFile) {
    const formData = new FormData();
    formData.append('audio_data', audioFile);

    // Django requires the CSRF token for POST requests to prevent 403 Forbidden errors
    const csrfToken = getCookie('csrftoken');

    try {
        const response = await fetch('/transcribe/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            body: formData
        });

        const data = await response.json();
        
        if (response.ok) {
            // Inject the transcribed text directly into Member 1's translation input box
            const inputField = document.getElementById('source-text-input');
            if (inputField) {
                inputField.value = data.text;
            }
        } else {
            alert("Transcription failed: " + data.error);
        }
    } catch (error) {
        console.error("Network error during transcription:", error);
    }
}

// Fetch the CSRF cookie securely
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}