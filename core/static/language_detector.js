// Source-language auto-detection built on the browser's native LanguageDetector API.
// https://developer.mozilla.org/en-US/docs/Web/API/Translator_and_Language_Detector_APIs
//
// The API is Chromium-only, secure-context only, and downloads a model on first use.
// Everything here degrades to "not supported" so the caller can hide the feature entirely
// rather than offering something that cannot work.

const AUTO_DETECT_VALUE = '__auto__';

// Below this confidence the top guess is treated as unusable. Short inputs such as a bare
// name or "no" routinely produce a confident-looking but wrong winner.
const MIN_DETECTION_CONFIDENCE = 0.5;

// Detected tags are BCP 47 and may carry region or script subtags the language menu does not
// list. Anything absent from this map falls back to its primary subtag ("pt-BR" -> "pt").
const LANGUAGE_ALIASES = {
    'zh': 'zh-CN',
    'zh-cn': 'zh-CN',
    'zh-sg': 'zh-CN',
    'zh-tw': 'zh-CN',
    'zh-hk': 'zh-CN',
    'zh-hans': 'zh-CN',
    'zh-hant': 'zh-CN',
};

// Reused across translations so the model is created (and downloaded) at most once per page.
let detectorPromise = null;

// An error whose message is safe to show the user verbatim.
class DetectionError extends Error {}

function isDetectionSupported() {
    return typeof window !== 'undefined' && typeof window.LanguageDetector !== 'undefined';
}

// Resolves to 'available' | 'downloadable' | 'downloading' | 'unavailable'.
// Safe to call without a user gesture, unlike create().
async function getDetectionAvailability(supportedCodes) {
    if (!isDetectionSupported()) {
        return 'unavailable';
    }

    try {
        return await LanguageDetector.availability({
            expectedInputLanguages: supportedCodes,
        });
    } catch (error) {
        return 'unavailable';
    }
}

// Must be called from within a user gesture: the API requires transient user activation.
function getDetector(supportedCodes, onDownloadProgress) {
    if (detectorPromise) {
        return detectorPromise;
    }

    detectorPromise = LanguageDetector.create({
        expectedInputLanguages: supportedCodes,
        monitor(monitor) {
            monitor.addEventListener('downloadprogress', (event) => {
                if (typeof onDownloadProgress === 'function') {
                    onDownloadProgress(event.loaded);
                }
            });
        },
    }).catch((error) => {
        // Let the next attempt retry instead of caching the failure forever.
        detectorPromise = null;
        throw error;
    });

    return detectorPromise;
}

function describeLanguage(tag) {
    try {
        const names = new Intl.DisplayNames(['en'], { type: 'language' });
        return names.of(tag) || tag;
    } catch (error) {
        return tag;
    }
}

// Maps a detected BCP 47 tag onto one of the codes the language menu offers,
// or returns null when there is no equivalent.
function toSupportedLanguageCode(detectedTag, supportedCodes) {
    const lowered = String(detectedTag || '').toLowerCase();
    if (!lowered) {
        return null;
    }

    const candidate = LANGUAGE_ALIASES[lowered]
        || LANGUAGE_ALIASES[lowered.split('-')[0]]
        || lowered.split('-')[0];

    return supportedCodes.find((code) => code.toLowerCase() === candidate.toLowerCase()) || null;
}

// Detects the language of `text` and returns { code, confidence, detectedTag }.
// Throws DetectionError with a user-facing message when the result is unusable.
async function detectSourceLanguage(text, supportedCodes, onDownloadProgress) {
    if (!isDetectionSupported()) {
        throw new DetectionError('This browser cannot detect languages. Select a source language.');
    }

    let results;
    try {
        const detector = await getDetector(supportedCodes, onDownloadProgress);
        results = await detector.detect(text);
    } catch (error) {
        if (error && error.name === 'NotAllowedError') {
            // Either a Permissions-Policy block, or create() ran without transient user
            // activation - which happens when the audio pipeline auto-submits the form.
            throw new DetectionError('Language detection needs a direct click. Press Translate again, or select a source language.');
        }
        throw new DetectionError('Language detection failed. Select a source language.');
    }

    // Results arrive sorted by confidence, with the "und" (undetermined) bucket last.
    const best = Array.isArray(results) ? results[0] : null;
    if (!best || best.detectedLanguage === 'und') {
        throw new DetectionError('Could not identify the language. Select a source language.');
    }
    if (best.confidence < MIN_DETECTION_CONFIDENCE) {
        throw new DetectionError('Not confident enough about the language. Select a source language.');
    }

    // Deliberately only the top guess: walking down the list to find something supported is
    // how you end up translating Dutch as though it were German.
    const code = toSupportedLanguageCode(best.detectedLanguage, supportedCodes);
    if (!code) {
        throw new DetectionError(
            'Detected ' + describeLanguage(best.detectedLanguage) + ', which is not supported. Select a source language.'
        );
    }

    return { code: code, confidence: best.confidence, detectedTag: best.detectedLanguage };
}
