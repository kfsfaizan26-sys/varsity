from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import get_settings
from app.schemas.api_responses import ExtractResponse
from app.services.gemini_errors import GeminiServiceError
from app.services.ocr_utils import OcrNotAvailableError
from app.services.pipeline import run_extraction_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_document(
    file: UploadFile = File(..., description="PDF, image (JPEG/PNG), or Excel file"),
    document_type: str = Query(
        default="admission_form",
        description=(
            "admission_form = one student; student_list = extract ALL rows "
            "(class roster, bulk PDF/Excel)"
        ),
    ),
) -> ExtractResponse:
    settings = get_settings()

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.max_upload_mb} MB",
        )

    if not settings.gemini_configured:
        raise HTTPException(
            status_code=503,
            detail="Gemini API key is not configured. Set GEMINI_API_KEY in .env",
        )

    try:
        return run_extraction_pipeline(
            data=data,
            filename=file.filename,
            content_type=file.content_type,
            document_type=document_type,
            settings=settings,
        )
    except OcrNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Document extraction failed: {exc}",
        ) from exc
