from __future__ import annotations

import io

import pytesseract
from PIL import Image

from app.config import Settings
from app.models.extracted_document import ExtractedDocument
from app.services.image_preprocess import preprocess_image_bytes
from app.services.ocr_utils import require_tesseract


def extract_image(data: bytes, settings: Settings) -> ExtractedDocument:
    require_tesseract(settings)
    processed = preprocess_image_bytes(data, settings)
    img = Image.open(io.BytesIO(processed))
    text = pytesseract.image_to_string(img, lang=settings.ocr_lang).strip()
    warnings: list[str] = []
    if not text:
        warnings.append("OCR returned empty text for image")
    return ExtractedDocument(
        full_text=text,
        detected_type="image",
        page_count=1,
        warnings=warnings,
    )
