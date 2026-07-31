/**
 * Document upload → extract + translate via Django, then optional download.
 */
(function () {
    const DOCUMENT_ACCEPT = '.pdf,.docx,.txt,.png,.jpg,.jpeg';
    const STEP_ORDER = ['upload', 'extract', 'translate', 'ready'];

    const STAGE_COPY = {
        upload: 'Uploading document…',
        extract: 'Extracting text…',
        translate: 'Translating document…',
        ready: 'Translation ready',
    };

    let elapsedTimerId = null;
    let stageTimerIds = [];
    let processingStartedAt = 0;

    function showUiError(message) {
        if (typeof window.showError === 'function') {
            window.showError(message);
        } else {
            alert(message);
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i += 1) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function clearStageTimers() {
        stageTimerIds.forEach(function (id) {
            window.clearTimeout(id);
        });
        stageTimerIds = [];
    }

    function formatElapsed(ms) {
        const totalSeconds = Math.max(0, Math.floor(ms / 1000));
        if (totalSeconds < 60) {
            return totalSeconds + 's';
        }
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return minutes + 'm ' + seconds + 's';
    }

    function setActiveStep(stepName) {
        const activeIndex = STEP_ORDER.indexOf(stepName);
        const title = document.getElementById('document-progress-title');
        const bar = document.getElementById('document-progress-bar');
        const barFill = document.getElementById('document-progress-bar-fill');

        if (title) {
            title.textContent = STAGE_COPY[stepName] || STAGE_COPY.upload;
        }

        const percent = Math.round(((activeIndex + 1) / STEP_ORDER.length) * 100);
        if (barFill) {
            barFill.style.width = percent + '%';
        }
        if (bar) {
            bar.setAttribute('aria-valuenow', String(percent));
        }
    }

    function startProgressUI(fileName) {
        const panel = document.getElementById('document-progress');
        const errorOutput = document.getElementById('translate-error');
        const successOutput = document.getElementById('translate-success');
        const elapsed = document.getElementById('document-progress-elapsed');

        if (errorOutput) {
            errorOutput.style.display = 'none';
        }
        if (successOutput) {
            successOutput.style.display = 'none';
        }

        document.body.classList.add('document-processing');
        if (panel) {
            panel.hidden = false;
            panel.classList.add('is-visible');
            panel.setAttribute('aria-busy', 'true');
        }

        processingStartedAt = Date.now();
        if (elapsed) {
            elapsed.textContent = '0s';
        }
        if (elapsedTimerId) {
            window.clearInterval(elapsedTimerId);
        }
        elapsedTimerId = window.setInterval(function () {
            if (elapsed) {
                elapsed.textContent = formatElapsed(Date.now() - processingStartedAt);
            }
        }, 250);

        clearStageTimers();
        setActiveStep('upload');
        const title = document.getElementById('document-progress-title');
        if (title && fileName) {
            title.textContent = 'Uploading “' + fileName + '”…';
        }

        // Optimistic stage progression while the single request is in flight.
        stageTimerIds.push(
            window.setTimeout(function () {
                setActiveStep('extract');
            }, 700)
        );
        stageTimerIds.push(
            window.setTimeout(function () {
                setActiveStep('translate');
            }, 2200)
        );
    }

    function finishProgressUI(succeeded) {
        clearStageTimers();
        if (succeeded) {
            setActiveStep('ready');
        }

        if (elapsedTimerId) {
            window.clearInterval(elapsedTimerId);
            elapsedTimerId = null;
        }

        const panel = document.getElementById('document-progress');
        const elapsed = document.getElementById('document-progress-elapsed');
        if (elapsed && processingStartedAt) {
            elapsed.textContent = formatElapsed(Date.now() - processingStartedAt);
        }

        // Keep the success step visible briefly, then hide the panel.
        window.setTimeout(function () {
            document.body.classList.remove('document-processing');
            if (panel) {
                panel.classList.remove('is-visible');
                panel.hidden = true;
                panel.setAttribute('aria-busy', 'false');
            }
        }, succeeded ? 900 : 0);
    }

    function setDocumentUploadState(isProcessing) {
        const uploadButton = document.getElementById('upload-btn');
        const translateButton = document.getElementById('translate-btn');
        if (uploadButton) {
            uploadButton.disabled = isProcessing;
            uploadButton.classList.toggle('is-processing', isProcessing);
            uploadButton.setAttribute(
                'data-tooltip',
                isProcessing
                    ? 'Processing document…'
                    : 'Upload document — PDF, DOCX, TXT, PNG, or JPG (max 1 MB; scanned PDFs up to 3 pages)'
            );
            uploadButton.setAttribute(
                'aria-label',
                isProcessing ? 'Processing document' : 'Upload document'
            );
        }
        if (translateButton) {
            translateButton.disabled = isProcessing;
        }
    }

    function setDownloadState(isProcessing) {
        const downloadButton = document.getElementById('download-doc-btn');
        if (!downloadButton) {
            return;
        }
        downloadButton.disabled = isProcessing;
        const label = isProcessing ? 'Preparing download…' : 'Download translated document';
        downloadButton.setAttribute('data-tooltip', label);
        downloadButton.setAttribute('aria-label', label);
        downloadButton.classList.toggle('is-processing', isProcessing);
    }

    function setDocumentDownloadVisible(visible) {
        const container = document.getElementById('document-download-actions');
        if (container) {
            container.hidden = !visible;
        }
    }
    window.setDocumentDownloadVisible = setDocumentDownloadVisible;

    function extensionAllowed(filename) {
        const lower = (filename || '').toLowerCase();
        return ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'].some(function (ext) {
            return lower.endsWith(ext);
        });
    }

    function applyTranslationResult(data) {
        const sourceInput = document.getElementById('source-text-input');
        const output = document.getElementById('output-copy');
        const successOutput = document.getElementById('translate-success');
        const errorOutput = document.getElementById('translate-error');
        const guestNudge = document.getElementById('guest-history-nudge');

        if (errorOutput) {
            errorOutput.hidden = true;
            errorOutput.style.display = 'none';
        }
        if (guestNudge) {
            guestNudge.hidden = true;
        }

        if (sourceInput && data.source_text) {
            sourceInput.value = data.source_text;
            sourceInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        if (output && data.translated_text) {
            output.textContent = data.translated_text;
            output.style.color = 'var(--color-on-surface)';
            if (typeof output.focus === 'function') {
                output.focus({ preventScroll: false });
            }
        }

        setDocumentDownloadVisible(true);

        const latency = document.getElementById('stat-latency');
        const accuracy = document.getElementById('stat-accuracy');
        const words = document.getElementById('stat-words');
        if (latency && data.latency_ms != null) {
            latency.textContent = data.latency_ms + 'ms';
        }
        if (accuracy) {
            accuracy.textContent =
                data.match == null ? '—' : Math.round(data.match * 100) + '%';
        }
        if (words && data.word_count != null) {
            words.textContent = data.word_count;
        }

        const chunks =
            data.chunk_count && data.chunk_count > 1
                ? ' Translated in ' + data.chunk_count + ' chunks.'
                : '';

        if (data.saved && successOutput) {
            successOutput.textContent =
                'Document translation saved to your history.' + chunks;
            successOutput.hidden = false;
            successOutput.style.display = 'block';
        } else if (!data.saved && guestNudge) {
            guestNudge.hidden = false;
        } else if (successOutput) {
            successOutput.textContent =
                'Document translated. Download when ready.' + chunks;
            successOutput.hidden = false;
            successOutput.style.display = 'block';
        }
    }

    async function sendDocumentToDjango(file) {
        const translateForm = document.getElementById('translate-form');
        const csrfInput = document.querySelector('#translate-form [name=csrfmiddlewaretoken]');
        const csrfToken = csrfInput ? csrfInput.value : getCookie('csrftoken');
        const url =
            (translateForm && translateForm.dataset.translateDocumentUrl) ||
            '/api/translate-document/';

        const formData = new FormData();
        formData.append('document', file);
        formData.append(
            'source_lang',
            document.getElementById('source-lang')?.value || 'en'
        );
        formData.append(
            'target_lang',
            document.getElementById('target-lang')?.value || 'fr'
        );

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: formData,
        });

        let data = {};
        try {
            data = await response.json();
        } catch (parseError) {
            data = {};
        }

        if (!response.ok) {
            throw new Error(data.error || 'Document translation failed.');
        }

        applyTranslationResult(data);
    }

    function setSelectedDocumentName(fileName) {
        if (typeof window.setSelectedDocumentName === 'function') {
            window.setSelectedDocumentName(fileName);
        }
    }

    async function processDocumentFile(file) {
        if (!file) {
            return;
        }
        if (document.body.classList.contains('document-processing')) {
            return;
        }
        if (!extensionAllowed(file.name)) {
            showUiError('Upload a PDF, DOCX, TXT, PNG, or JPG file.');
            return;
        }
        if (file.size <= 0) {
            showUiError('The selected document is empty.');
            return;
        }

        const sourceLang = document.getElementById('source-lang')?.value;
        const targetLang = document.getElementById('target-lang')?.value;
        if (sourceLang && targetLang && sourceLang === targetLang) {
            showUiError('Source and target languages must be different.');
            return;
        }

        setSelectedDocumentName(file.name);
        setDocumentUploadState(true);
        startProgressUI(file.name);
        let succeeded = false;
        try {
            await sendDocumentToDjango(file);
            succeeded = true;
        } catch (error) {
            showUiError(error.message || 'Unable to process the document.');
        } finally {
            finishProgressUI(succeeded);
            setDocumentUploadState(false);
        }
    }

    async function handleDocumentUpload(event) {
        const file = event.target.files && event.target.files[0];
        event.target.value = '';
        await processDocumentFile(file);
    }

    function dragEventHasFiles(event) {
        const types = (event.dataTransfer && event.dataTransfer.types) || [];
        return Array.prototype.indexOf.call(types, 'Files') !== -1;
    }

    function setupDragAndDrop() {
        const dropZone = document.getElementById('source-drop-zone');
        if (!dropZone) {
            return;
        }

        let dragDepth = 0;

        dropZone.addEventListener('dragenter', function (event) {
            if (!dragEventHasFiles(event)) {
                return;
            }
            event.preventDefault();
            dragDepth += 1;
            dropZone.classList.add('is-drag-over');
        });

        dropZone.addEventListener('dragover', function (event) {
            if (!dragEventHasFiles(event)) {
                return;
            }
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
        });

        dropZone.addEventListener('dragleave', function (event) {
            if (!dragEventHasFiles(event)) {
                return;
            }
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) {
                dropZone.classList.remove('is-drag-over');
            }
        });

        dropZone.addEventListener('drop', function (event) {
            if (!dragEventHasFiles(event)) {
                return;
            }
            event.preventDefault();
            dragDepth = 0;
            dropZone.classList.remove('is-drag-over');

            const files = event.dataTransfer.files;
            if (!files || files.length === 0) {
                return;
            }
            if (files.length > 1) {
                showUiError('Please drop a single document at a time.');
                return;
            }
            processDocumentFile(files[0]);
        });

        // Stop the browser from navigating away when a file is dropped
        // outside the drop zone (e.g. elsewhere on the page).
        ['dragover', 'drop'].forEach(function (type) {
            window.addEventListener(type, function (event) {
                if (dragEventHasFiles(event) && !dropZone.contains(event.target)) {
                    event.preventDefault();
                }
            });
        });
    }

    function getTranslatedText() {
        if (typeof window.getTranslationOutputText === 'function') {
            return window.getTranslationOutputText();
        }
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

    async function downloadTranslatedDocument() {
        const translatedText = getTranslatedText();
        if (!translatedText) {
            showUiError('Translate a document first, then download.');
            return;
        }

        const translateForm = document.getElementById('translate-form');
        const csrfInput = document.querySelector('#translate-form [name=csrfmiddlewaretoken]');
        const csrfToken = csrfInput ? csrfInput.value : getCookie('csrftoken');
        const url =
            (translateForm && translateForm.dataset.downloadTranslationUrl) ||
            '/api/download-translation/';
        const formatSelect = document.getElementById('download-format');
        const outputFormat = formatSelect ? formatSelect.value : 'docx';

        setDownloadState(true);
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    translated_text: translatedText,
                    output_format: outputFormat,
                }),
            });

            const contentType = response.headers.get('Content-Type') || '';
            if (!response.ok) {
                let data = {};
                if (contentType.includes('application/json')) {
                    data = await response.json();
                }
                throw new Error(data.error || 'Download failed.');
            }

            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition') || '';
            let filename = 'linguashift-translation.' + outputFormat;
            const match = /filename="?([^"]+)"?/i.exec(disposition);
            if (match && match[1]) {
                filename = match[1];
            }

            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(objectUrl);
        } catch (error) {
            showUiError(error.message || 'Unable to download the translation.');
        } finally {
            setDownloadState(false);
        }
    }

    function ensureDocumentInput() {
        let input = document.getElementById('document-file-input');
        if (!input) {
            input = document.createElement('input');
            input.type = 'file';
            input.id = 'document-file-input';
            input.accept = DOCUMENT_ACCEPT;
            input.style.display = 'none';
            document.body.appendChild(input);
        } else {
            input.accept = DOCUMENT_ACCEPT;
        }
        input.addEventListener('change', handleDocumentUpload);
        return input;
    }

    document.addEventListener('DOMContentLoaded', function () {
        const documentInput = ensureDocumentInput();
        const uploadButton = document.getElementById('upload-btn');
        if (uploadButton) {
            const freshButton = uploadButton.cloneNode(true);
            uploadButton.parentNode.replaceChild(freshButton, uploadButton);
            freshButton.addEventListener('click', function () {
                if (document.body.classList.contains('document-processing')) {
                    return;
                }
                documentInput.click();
            });
            freshButton.setAttribute(
                'data-tooltip',
                'Upload document — PDF, DOCX, TXT, PNG, or JPG (max 1 MB; scanned PDFs up to 3 pages)'
            );
            freshButton.setAttribute('aria-label', 'Upload document');
        }

        const downloadButton = document.getElementById('download-doc-btn');
        if (downloadButton) {
            downloadButton.addEventListener('click', downloadTranslatedDocument);
        }

        setupDragAndDrop();
    });
})();
