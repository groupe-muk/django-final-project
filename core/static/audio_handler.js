// State variables
let mediaRecorder = null;
let mediaStream = null;
let audioChunks = [];
let isRecording = false;
const MAX_AUDIO_BYTES = 25 * 1024 * 1024;

function setMicButtonState(state) {
    const micButton = document.getElementById('mic-btn');
    if (!micButton) {
        return;
    }

    if (state === 'recording') {
        micButton.classList.add('recording-active');
        micButton.title = 'Stop recording';
        micButton.setAttribute('aria-label', 'Stop recording');
        micButton.disabled = false;
        return;
    }

    if (state === 'processing') {
        micButton.classList.remove('recording-active');
        micButton.title = 'Processing recording...';
        micButton.setAttribute('aria-label', 'Processing recording');
        micButton.disabled = true;
        return;
    }

    micButton.classList.remove('recording-active');
    micButton.title = 'Record audio';
    micButton.setAttribute('aria-label', 'Record audio');
    micButton.disabled = false;
}

function stopMediaStream() {
    if (!mediaStream) {
        return;
    }
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
}

function getSupportedMimeType() {
    if (!window.MediaRecorder || typeof MediaRecorder.isTypeSupported !== 'function') {
        return '';
    }

    const preferredMimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/ogg;codecs=opus',
    ];

    return preferredMimeTypes.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || '';
}

function extensionFromMimeType(mimeType) {
    if (!mimeType) {
        return 'webm';
    }
    if (mimeType.includes('mp4')) {
        return 'm4a';
    }
    if (mimeType.includes('ogg')) {
        return 'ogg';
    }
    return 'webm';
}

function showUiError(message) {
    if (typeof window.showError === 'function') {
        window.showError(message);
    } else {
        alert(message);
    }
}

function setUploadButtonState(isProcessing) {
    const uploadButton = document.getElementById('upload-btn');
    if (!uploadButton) {
        return;
    }
    uploadButton.disabled = isProcessing;
    uploadButton.title = isProcessing ? 'Processing upload...' : 'Upload audio';
    uploadButton.setAttribute('aria-label', isProcessing ? 'Processing upload' : 'Upload audio');
}

function validateAudioFile(file) {
    if (!file) {
        return 'No audio file selected.';
    }
    if (!file.type || !file.type.startsWith('audio/')) {
        return 'Please choose a valid audio file.';
    }
    if (file.size <= 0) {
        return 'The selected audio file is empty.';
    }
    if (file.size > MAX_AUDIO_BYTES) {
        return 'Audio file is too large. Please keep it under 25 MB.';
    }
    return '';
}

// 1. Single Toggle Function for Live Microphone Recording
async function toggleRecording() {
    if (!isRecording) {
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showUiError('Your browser does not support microphone recording.');
                return;
            }
            if (!window.MediaRecorder) {
                showUiError('MediaRecorder is not available in this browser.');
                return;
            }

            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mimeType = getSupportedMimeType();
            mediaRecorder = mimeType
                ? new MediaRecorder(mediaStream, { mimeType })
                : new MediaRecorder(mediaStream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                if (event.data && event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                isRecording = false;
                setMicButtonState('processing');

                try {
                    const resolvedMimeType = mediaRecorder && mediaRecorder.mimeType
                        ? mediaRecorder.mimeType
                        : 'audio/webm';
                    const audioBlob = new Blob(audioChunks, { type: resolvedMimeType });
                    const extension = extensionFromMimeType(resolvedMimeType);
                    const audioFile = new File(
                        [audioBlob],
                        `live_recording.${extension}`,
                        { type: resolvedMimeType }
                    );

                    await sendAudioToDjango(audioFile);
                } finally {
                    stopMediaStream();
                    setMicButtonState('idle');
                }
            };

            mediaRecorder.start();
            isRecording = true;
            setMicButtonState('recording');
            console.log("Microphone live. Recording...");

        } catch (err) {
            console.error("Microphone access denied:", err);
            stopMediaStream();
            setMicButtonState('idle');
            showUiError('Please allow microphone permissions in your browser to record audio.');
        }
    } else {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
            setMicButtonState('processing');
            console.log("Recording stopped. Processing audio...");
        }
    }
}

// 2. Logic for File Uploads (.mp3, .wav, etc.)
async function handleFileUpload(event) {
    const file = event.target.files[0];
    const validationError = validateAudioFile(file);
    if (validationError) {
        showUiError(validationError);
        event.target.value = '';
        return;
    }

    if (file) {
        console.log("Audio file selected. Processing...");
        setUploadButtonState(true);
        try {
            await sendAudioToDjango(file);
        } finally {
            setUploadButtonState(false);
        }
    }
    event.target.value = '';
}

// 3. Send Data to Django Backend
async function sendAudioToDjango(audioFile) {
    const formData = new FormData();
    formData.append('audio_data', audioFile);

    // Django requires the CSRF token for POST requests
    const csrfInput = document.querySelector('#translate-form [name=csrfmiddlewaretoken]');
    const csrfToken = csrfInput ? csrfInput.value : getCookie('csrftoken');

    const translateForm = document.getElementById('translate-form');
    const transcribeUrl = (translateForm && translateForm.dataset.transcribeUrl) || '/transcribe/';

    try {
        const response = await fetch(transcribeUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            body: formData
        });

        let data = {};
        try {
            data = await response.json();
        } catch (parseError) {
            data = {};
        }
        
        if (response.ok) {
            // Inject the transcribed text directly into the translation input box
            const inputField = document.getElementById('source-text-input');
            if (inputField) {
                inputField.value = (data.text || '').trim();
                inputField.dispatchEvent(new Event('input', { bubbles: true }));
            }

            if (inputField && inputField.value) {
                const translateForm = document.getElementById('translate-form');
                const translateButton = document.getElementById('translate-btn');
                if (translateForm && (!translateButton || !translateButton.disabled)) {
                    if (typeof translateForm.requestSubmit === 'function') {
                        translateForm.requestSubmit();
                    } else {
                        translateForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                    }
                }
            }
        } else {
            showUiError('Transcription failed: ' + (data.error || 'Unknown error.'));
        }
    } catch (error) {
        console.error("Network error during transcription:", error);
        showUiError('Network error during transcription. Please try again.');
    }
}

// 4. Utility: Fetch the CSRF cookie securely
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