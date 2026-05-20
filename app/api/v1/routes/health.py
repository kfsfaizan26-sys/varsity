from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services.ocr_utils import is_poppler_available, is_tesseract_available

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "gemini_configured": settings.gemini_configured,
        "tesseract_configured": is_tesseract_available(settings),
        "poppler_configured": is_poppler_available(),
    }
