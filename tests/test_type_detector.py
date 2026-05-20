from __future__ import annotations

import fitz

from app.config import Settings
from app.services.type_detector import detect_document_type, is_excel, is_image, is_pdf


def _minimal_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_is_pdf_by_extension():
    assert is_pdf("form.pdf", None) is True


def test_is_image_by_extension():
    assert is_image("photo.jpg", None) is True


def test_is_excel_by_extension():
    assert is_excel("data.xlsx", None) is True


def test_detect_pdf_text(settings: Settings):
    data = _minimal_pdf_with_text("Student Name: John Doe " * 10)
    detected = detect_document_type("admission.pdf", "application/pdf", data, settings)
    assert detected == "pdf_text"


def test_detect_image_png(settings: Settings):
    # minimal PNG header + IHDR chunk is not valid image for full pipeline,
    # but type detection uses extension
    detected = detect_document_type("scan.png", "image/png", b"\x89PNG\r\n\x1a\n", settings)
    assert detected == "image"
