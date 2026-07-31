"""Translate documents that exceed MyMemory's single-request byte limit."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from .chunking import chunk_text
from .mymemory import MAX_QUERY_BYTES, TranslationResult, translate_text


@dataclass(frozen=True)
class LongTranslationResult:
    source_text: str
    translated_text: str
    match: float | None
    latency_ms: int
    chunk_count: int
    word_count: int


def translate_long_text(
    source_text: str,
    source_lang: str,
    target_lang: str,
    *,
    max_bytes: int = MAX_QUERY_BYTES,
) -> LongTranslationResult:
    """Chunk ``source_text`` and translate each piece through MyMemory."""
    cleaned = (source_text or "").strip()
    if not cleaned:
        raise ValueError("Enter text to translate.")

    chunks = chunk_text(cleaned, max_bytes=max_bytes)
    if not chunks:
        raise ValueError("Enter text to translate.")

    started_at = monotonic()
    translated_parts: list[str] = []
    matches: list[float] = []

    for chunk in chunks:
        result: TranslationResult = translate_text(chunk, source_lang, target_lang)
        translated_parts.append(result.translated_text)
        if result.match is not None:
            matches.append(result.match)

    # Preserve paragraph separation when the source had blank lines.
    if "\n\n" in cleaned:
        translated_text = "\n\n".join(translated_parts)
    else:
        translated_text = " ".join(translated_parts)

    average_match = sum(matches) / len(matches) if matches else None
    latency_ms = round((monotonic() - started_at) * 1000)

    return LongTranslationResult(
        source_text=cleaned,
        translated_text=translated_text.strip(),
        match=average_match,
        latency_ms=latency_ms,
        chunk_count=len(chunks),
        word_count=len(cleaned.split()),
    )
