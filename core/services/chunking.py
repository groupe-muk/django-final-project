"""Split long source text into MyMemory-safe UTF-8 byte chunks."""

from __future__ import annotations

import re

from .mymemory import MAX_QUERY_BYTES


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")


def _utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _hard_split(text: str, max_bytes: int) -> list[str]:
    """Split a string that has no convenient boundaries into UTF-8-safe pieces."""
    pieces: list[str] = []
    remaining = text
    while remaining:
        if _utf8_len(remaining) <= max_bytes:
            pieces.append(remaining)
            break

        low, high = 1, len(remaining)
        best = 1
        while low <= high:
            mid = (low + high) // 2
            candidate = remaining[:mid]
            if _utf8_len(candidate) <= max_bytes:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        # Prefer splitting on whitespace inside the allowed window.
        window = remaining[:best]
        space_at = window.rfind(" ")
        if space_at > 0:
            best = space_at

        pieces.append(remaining[:best].strip())
        remaining = remaining[best:].lstrip()

    return [piece for piece in pieces if piece]


def chunk_text(text: str, max_bytes: int = MAX_QUERY_BYTES) -> list[str]:
    """
    Split text into chunks that each encode to at most ``max_bytes`` UTF-8 bytes.

    Prefers paragraph boundaries, then sentence boundaries, then hard splits.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if max_bytes < 1:
        raise ValueError("max_bytes must be at least 1.")
    if _utf8_len(cleaned) <= max_bytes:
        return [cleaned]

    chunks: list[str] = []
    paragraphs = [part.strip() for part in _PARAGRAPH_SPLIT.split(cleaned) if part.strip()]

    for paragraph in paragraphs or [cleaned]:
        if _utf8_len(paragraph) <= max_bytes:
            chunks.append(paragraph)
            continue

        sentences = [part.strip() for part in _SENTENCE_SPLIT.split(paragraph) if part.strip()]
        current = ""
        for sentence in sentences or [paragraph]:
            if _utf8_len(sentence) > max_bytes:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(_hard_split(sentence, max_bytes))
                continue

            candidate = f"{current} {sentence}".strip() if current else sentence
            if _utf8_len(candidate) <= max_bytes:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

    return chunks
