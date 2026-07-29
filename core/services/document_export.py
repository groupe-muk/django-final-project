"""Build downloadable translation files in memory."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from docx import Document


SUPPORTED_OUTPUT_FORMATS = {"txt", "docx"}


class DocumentExportError(Exception):
    """Raised when a downloadable file cannot be built."""


@dataclass(frozen=True)
class DownloadFile:
    content: bytes
    content_type: str
    filename: str


def build_download(
    text: str,
    output_format: str = "docx",
    *,
    basename: str = "linguashift-translation",
) -> DownloadFile:
    """Return an in-memory translated document ready for FileResponse."""
    body = (text or "").strip()
    if not body:
        raise DocumentExportError("There is no translated text to download.")

    fmt = (output_format or "docx").lower().strip()
    if fmt not in SUPPORTED_OUTPUT_FORMATS:
        raise DocumentExportError("Choose txt or docx as the download format.")

    if fmt == "txt":
        return DownloadFile(
            content=body.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
            filename=f"{basename}.txt",
        )

    document = Document()
    for paragraph in body.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)
    return DownloadFile(
        content=buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        filename=f"{basename}.docx",
    )
