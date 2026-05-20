from __future__ import annotations

from unittest.mock import MagicMock, patch

import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.pipeline import extract_text_from_bytes, run_extraction_pipeline

SAMPLE_GEMINI_JSON = {
    "personal": {
        "full_name": "Rahul Sharma",
        "date_of_birth": "2004-06-12",
        "gender": "Male",
    },
    "contact": {"email": "rahul@example.com", "phone": "9123456789"},
    "guardians": [{"name": "Mr Sharma", "relationship": "Father"}],
    "academic": {"previous_institution": "ABC School"},
    "identifiers": {"application_number": "APP-001"},
    "meta": {},
}


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_extract_text_from_pdf(settings: Settings):
    data = _pdf_bytes("Admission Form\nStudent: Rahul Sharma\nDOB: 2004-06-12")
    doc = extract_text_from_bytes(data, "form.pdf", "application/pdf", settings)
    assert doc.detected_type == "pdf_text"
    assert "Rahul" in doc.full_text


@patch("app.services.pipeline.GeminiExtractor")
def test_run_pipeline_with_mock_gemini(mock_extractor_cls, settings: Settings):
    mock_instance = MagicMock()
    mock_instance.extract.return_value = SAMPLE_GEMINI_JSON
    mock_extractor_cls.return_value = mock_instance

    data = _pdf_bytes("Student: Rahul Sharma\nEmail: rahul@example.com\nPhone: 9123456789")
    result = run_extraction_pipeline(
        data=data,
        filename="admission.pdf",
        content_type="application/pdf",
        document_type="admission_form",
        settings=settings,
    )
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].personal.full_name == "Rahul Sharma"


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_extract_without_gemini_key(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)
    data = _pdf_bytes("test content " * 20)
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("test.pdf", data, "application/pdf")},
    )
    assert response.status_code == 503
    get_settings.cache_clear()
