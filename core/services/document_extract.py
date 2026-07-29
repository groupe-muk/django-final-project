"""Extract plain text from uploaded documents (local parsers + OCR.space)."""

from __future__ import annotations

import io
from pathlib import Path

import requests
from django.conf import settings
from docx import Document
from pypdf import PdfReader


class DocumentExtractError(Exception):
    """A safe error that can be returned to an API consumer."""


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# OCR.space language codes for LinguaShift source languages.
OCR_SPACE_LANGUAGE_MAP = {
    "ar": "ara",
    "zh-CN": "chs",
    "en": "eng",
    "fr": "fre",
    "de": "ger",
    "hi": "hin",
    "it": "ita",
    "ja": "jpn",
    "pt": "por",
    "es": "spa",
    "sw": "eng",  # Swahili not listed; English OCR is the safest free fallback.
}


def _extension_for(uploaded_file) -> str:
    name = getattr(uploaded_file, "name", "") or ""
    return Path(name).suffix.lower()


def _read_bytes(uploaded_file) -> bytes:
    if hasattr(uploaded_file, "open"):
        uploaded_file.open("rb")
    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        data = uploaded_file.read()
    finally:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
    if not data:
        raise DocumentExtractError("The uploaded file is empty.")
    return data


def _extract_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentExtractError("Could not decode the text file as UTF-8.")


def _extract_docx(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentExtractError("Could not read the Word document.") from exc

    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    text = "\n".join(part for part in paragraphs if part)
    if not text.strip():
        raise DocumentExtractError("No readable text was found in the Word document.")
    return text


def _extract_pdf_text_layer(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise DocumentExtractError("Could not read the PDF file.") from exc

    if getattr(reader, "is_encrypted", False):
        raise DocumentExtractError("Encrypted PDFs are not supported.")

    page_limit = int(getattr(settings, "DOCUMENT_MAX_PDF_PAGES", 3))
    pages = reader.pages[:page_limit]
    parts: list[str] = []
    for page in pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            parts.append(page_text.strip())

    return "\n\n".join(parts).strip()


def _ocr_space_language(source_lang: str | None) -> str:
    if not source_lang:
        return "eng"
    return OCR_SPACE_LANGUAGE_MAP.get(source_lang, "eng")


def _extract_with_ocr_space(
    data: bytes,
    *,
    filename: str,
    source_lang: str | None = None,
) -> str:
    api_key = getattr(settings, "OCR_SPACE_API_KEY", "") or ""
    if not api_key.strip():
        raise DocumentExtractError(
            "Server is missing OCR_SPACE_API_KEY configuration for scanned documents."
        )

    url = getattr(settings, "OCR_SPACE_URL", "https://api.ocr.space/parse/image")
    timeout = float(getattr(settings, "OCR_SPACE_TIMEOUT_SECONDS", 30))

    try:
        response = requests.post(
            url,
            files={"file": (filename or "document.bin", data)},
            data={
                "apikey": api_key,
                "language": _ocr_space_language(source_lang),
                "OCREngine": "2",
                "isOverlayRequired": "false",
                "scale": "true",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise DocumentExtractError(
            "The OCR service timed out. Please try a smaller file."
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        raise DocumentExtractError(
            "The OCR service is currently unavailable."
        ) from exc

    if payload.get("IsErroredOnProcessing"):
        message = payload.get("ErrorMessage") or payload.get("ErrorDetails") or ""
        if isinstance(message, list):
            message = "; ".join(str(part) for part in message if part)
        message = str(message).strip() or "The OCR service rejected the file."
        raise DocumentExtractError(message)

    results = payload.get("ParsedResults") or []
    texts = []
    for result in results:
        parsed = (result or {}).get("ParsedText") or ""
        if parsed.strip():
            texts.append(parsed.strip())

    text = "\n\n".join(texts).strip()
    if not text:
        raise DocumentExtractError("OCR did not find any readable text in the file.")
    return text


def extract_text(uploaded_file, *, source_lang: str | None = None) -> str:
    """
    Extract plain text from an uploaded document.

    Born-digital TXT/DOCX/PDF use local parsers. Images and PDFs without a text
    layer fall back to the free OCR.space API.
    """
    extension = _extension_for(uploaded_file)
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentExtractError(
            "Unsupported file type. Upload PDF, DOCX, TXT, PNG, or JPG."
        )

    max_bytes = int(getattr(settings, "DOCUMENT_MAX_UPLOAD_BYTES", 1_048_576))
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_bytes:
        raise DocumentExtractError(
            f"File is too large. Keep uploads under {max_bytes} bytes."
        )

    data = _read_bytes(uploaded_file)
    if len(data) > max_bytes:
        raise DocumentExtractError(
            f"File is too large. Keep uploads under {max_bytes} bytes."
        )

    filename = getattr(uploaded_file, "name", "") or f"upload{extension}"

    if extension == ".txt":
        text = _extract_txt(data)
    elif extension == ".docx":
        text = _extract_docx(data)
    elif extension == ".pdf":
        text = _extract_pdf_text_layer(data)
        if not text:
            text = _extract_with_ocr_space(
                data, filename=filename, source_lang=source_lang
            )
    elif extension in IMAGE_EXTENSIONS:
        text = _extract_with_ocr_space(
            data, filename=filename, source_lang=source_lang
        )
    else:
        raise DocumentExtractError(
            "Unsupported file type. Upload PDF, DOCX, TXT, PNG, or JPG."
        )

    text = (text or "").strip()
    if not text:
        raise DocumentExtractError("No readable text was found in the document.")

    max_extract = int(getattr(settings, "DOCUMENT_MAX_EXTRACT_BYTES", 10_000))
    encoded = text.encode("utf-8")
    if len(encoded) > max_extract:
        text = encoded[:max_extract].decode("utf-8", errors="ignore").rstrip()
        text = f"{text}\n\n[Truncated to {max_extract} UTF-8 bytes for free-tier translation.]"

    return text
