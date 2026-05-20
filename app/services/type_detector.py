from __future__ import annotations

from pathlib import Path

import fitz

from app.config import Settings
from app.models.extracted_document import DetectedDocType

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/webp",
    "image/tiff",
}
EXCEL_EXTENSIONS = {".xlsx", ".xls"}
EXCEL_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
PDF_EXTENSIONS = {".pdf"}
PDF_MIMES = {"application/pdf"}


def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def is_pdf(filename: str, content_type: str | None) -> bool:
    ext = _extension(filename)
    return ext in PDF_EXTENSIONS or (content_type or "") in PDF_MIMES


def is_image(filename: str, content_type: str | None) -> bool:
    ext = _extension(filename)
    return ext in IMAGE_EXTENSIONS or (content_type or "") in IMAGE_MIMES


def is_excel(filename: str, content_type: str | None) -> bool:
    ext = _extension(filename)
    return ext in EXCEL_EXTENSIONS or (content_type or "") in EXCEL_MIMES


def classify_pdf_subtype(data: bytes, settings: Settings) -> DetectedDocType:
    """Distinguish text PDF from scanned/image-only PDF."""
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        text_parts: list[str] = []
        page_limit = min(len(doc), 5)
        for i in range(page_limit):
            text_parts.append(doc[i].get_text())
        combined = "".join(text_parts).strip()
        alpha = sum(1 for c in combined if c.isalnum() or c.isspace())
        ratio = alpha / len(combined) if combined else 0.0
        if len(combined) >= settings.pdf_text_threshold and ratio >= 0.5:
            return "pdf_text"
        return "pdf_scanned"
    finally:
        doc.close()


def detect_document_type(
    filename: str,
    content_type: str | None,
    data: bytes,
    settings: Settings,
) -> DetectedDocType:
    if is_excel(filename, content_type):
        return "excel"
    if is_image(filename, content_type):
        return "image"
    if is_pdf(filename, content_type):
        return classify_pdf_subtype(data, settings)

    # magic bytes fallback
    if data[:4] == b"%PDF":
        return classify_pdf_subtype(data, settings)
    if data[:2] in (b"\xff\xd8", b"\x89P"):
        return "image"
    if data[:2] == b"PK":
        return "excel"
    raise ValueError(
        f"Unsupported file type: {filename} ({content_type}). "
        "Supported: PDF, images (JPEG/PNG/…), Excel (.xlsx/.xls)."
    )
