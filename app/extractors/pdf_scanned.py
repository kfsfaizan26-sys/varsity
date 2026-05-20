from __future__ import annotations

import io

import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import Settings
from app.models.extracted_document import ExtractedDocument
from app.services.image_preprocess import preprocess_image_bytes
from app.services.ocr_utils import require_tesseract


def _ocr_image(image: Image.Image, settings: Settings) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    processed = preprocess_image_bytes(buffer.getvalue(), settings)
    img = Image.open(io.BytesIO(processed))
    return pytesseract.image_to_string(img, lang=settings.ocr_lang)


def extract_pdf_scanned(data: bytes, settings: Settings) -> ExtractedDocument:
    require_tesseract(settings)
    pages = convert_from_bytes(data, dpi=200)
    parts: list[str] = []
    warnings: list[str] = []
    for i, page in enumerate(pages):
        text = _ocr_image(page, settings).strip()
        if text:
            parts.append(f"--- page {i + 1} ---\n{text}")
        else:
            warnings.append(f"OCR returned empty text for page {i + 1}")
    full_text = "\n\n".join(parts)
    return ExtractedDocument(
        full_text=full_text,
        detected_type="pdf_scanned",
        page_count=len(pages),
        warnings=warnings,
    )
