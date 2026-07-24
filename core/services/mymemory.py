from dataclasses import dataclass
from html import unescape

import requests
from django.conf import settings


MAX_QUERY_BYTES = 500


class TranslationServiceError(Exception):
    """A safe error that can be returned to an API consumer."""


class TranslationQuotaError(TranslationServiceError):
    """The provider's free quota has been exhausted."""


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str
    match: float | None


def translate_text(source_text: str, source_lang: str, target_lang: str) -> TranslationResult:
    """Translate one UTF-8 segment through the MyMemory Get endpoint."""
    if len(source_text.encode("utf-8")) > MAX_QUERY_BYTES:
        raise TranslationServiceError(
            f"Text must be no more than {MAX_QUERY_BYTES} UTF-8 bytes."
        )

    base_url = settings.MYMEMORY_BASE_URL.rstrip("/")
    params = {
        "q": source_text,
        "langpair": f"{source_lang}|{target_lang}",
        "mt": "1",
    }

    if settings.MYMEMORY_CONTACT_EMAIL:
        params["de"] = settings.MYMEMORY_CONTACT_EMAIL
    if settings.MYMEMORY_API_KEY:
        params["key"] = settings.MYMEMORY_API_KEY

    try:
        response = requests.get(
            f"{base_url}/get",
            params=params,
            timeout=settings.MYMEMORY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise TranslationServiceError(
            "The translation service timed out. Please try again."
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        raise TranslationServiceError(
            "The translation service is currently unavailable."
        ) from exc

    if payload.get("quotaFinished"):
        raise TranslationQuotaError(
            "The translation service's free quota has been reached for today."
        )

    response_status = payload.get("responseStatus")
    if str(response_status) != "200":
        details = str(payload.get("responseDetails") or "").lower()
        if "quota" in details or "available free translations" in details:
            raise TranslationQuotaError(
                "The translation service's free quota has been reached for today."
            )
        raise TranslationServiceError("The translation service rejected the request.")

    response_data = payload.get("responseData") or {}
    translated_text = response_data.get("translatedText")
    if not isinstance(translated_text, str) or not translated_text.strip():
        raise TranslationServiceError("The translation service returned no translation.")

    match = response_data.get("match")
    try:
        match = float(match) if match is not None else None
    except (TypeError, ValueError):
        match = None

    return TranslationResult(
        translated_text=unescape(translated_text).strip(),
        match=match,
    )
