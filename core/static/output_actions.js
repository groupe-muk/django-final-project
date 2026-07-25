function getTranslationOutputText() {
    const output = document.getElementById('output-copy');
    if (!output) {
        return '';
    }

    const placeholder = document.getElementById('output-placeholder');
    const text = output.textContent.trim();
    if (placeholder && text === placeholder.textContent.trim()) {
        return '';
    }

    return text;
}

function getTargetLanguageCode() {
    const targetSelect = document.getElementById('target-lang');
    return targetSelect ? targetSelect.value : '';
}

function showOutputActionFeedback(message) {
    const successOutput = document.getElementById('translate-success');
    if (successOutput) {
        successOutput.textContent = message;
        successOutput.style.display = 'block';
        window.clearTimeout(showOutputActionFeedback._timer);
        showOutputActionFeedback._timer = window.setTimeout(function () {
            successOutput.style.display = 'none';
        }, 1800);
        return;
    }

    alert(message);
}

// --- 1. LISTEN TO TRANSLATION ---
function listenToTranslation() {
    const textToSpeak = getTranslationOutputText();
    
    if (!textToSpeak) {
        alert("Nothing to play!");
        return;
    }

    // Stop any currently playing audio before starting a new one
    window.speechSynthesis.cancel(); 

    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    
    const targetLang = getTargetLanguageCode();
    if (targetLang) {
        utterance.lang = targetLang;
    }

    // Play the audio
    window.speechSynthesis.speak(utterance);
}

// --- 2. COPY TO CLIPBOARD ---
async function copyTranslation() {
    const textToCopy = getTranslationOutputText();
    
    if (!textToCopy) {
        alert("Nothing to copy!");
        return;
    }

    try {
        await navigator.clipboard.writeText(textToCopy);
        
        showOutputActionFeedback("Translation copied to clipboard!");
    } catch (err) {
        console.error("Failed to copy text: ", err);
        alert("Failed to copy translation.");
    }
}

// --- 3. NATIVE SHARE ---
async function shareTranslation() {
    const textToShare = getTranslationOutputText();
    
    if (!textToShare) {
        alert("Nothing to share!");
        return;
    }

    // Check if the browser supports the native Web Share API
    if (navigator.share) {
        try {
            await navigator.share({
                title: 'LinguaShift Translation',
                text: textToShare,
            });
            showOutputActionFeedback('Translation shared.');
        } catch (err) {
            console.error('Error sharing: ', err);
        }
    } else {
        // Fallback for older browsers (desktop Chrome requires HTTPS for this to work)
        alert("Sharing is not supported on this browser. Please use the Copy button instead.");
    }
}