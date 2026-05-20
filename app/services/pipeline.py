from __future__ import annotations

from app.config import Settings
from app.schemas.api_responses import ExtractMeta
from app.extractors import (
    extract_excel,
    extract_image,
    extract_pdf_scanned,
    extract_pdf_text,
)
from app.models.extracted_document import DetectedDocType, ExtractedDocument
from app.schemas.api_responses import ExtractResponse
from app.services.document_type_resolver import resolve_document_type
from app.services.gemini_extractor import GeminiExtractor
from app.services.type_detector import detect_document_type
from app.services.validator import build_response

_PREVIEW_LEN = 2000


def _truncate_text(doc: ExtractedDocument, max_chars: int) -> tuple[ExtractedDocument, bool]:
    if len(doc.full_text) <= max_chars:
        return doc, False
    truncated = doc.model_copy(
        update={
            "full_text": doc.full_text[:max_chars],
            "warnings": doc.warnings + [f"Text truncated to {max_chars} characters for Gemini"],
        }
    )
    return truncated, True


def extract_text_from_bytes(
    data: bytes,
    filename: str,
    content_type: str | None,
    settings: Settings,
) -> ExtractedDocument:
    detected: DetectedDocType = detect_document_type(
        filename, content_type, data, settings
    )
    if detected == "pdf_text":
        doc = extract_pdf_text(data)
        # Image-only PDFs are misclassified as pdf_text — retry with OCR when almost empty
        if len(doc.full_text.strip()) < 30 and not (doc.tables_markdown or "").strip():
            try:
                ocr_doc = extract_pdf_scanned(data, settings)
                if len(ocr_doc.full_text.strip()) > len(doc.full_text.strip()):
                    ocr_doc.warnings = list(doc.warnings) + [
                        "PDF had little selectable text; used OCR fallback"
                    ]
                    return ocr_doc
            except Exception:
                doc.warnings.append(
                    "Little text in PDF; install poppler+tesseract for OCR fallback"
                )
        return doc
    if detected == "pdf_scanned":
        return extract_pdf_scanned(data, settings)
    if detected == "image":
        return extract_image(data, settings)
    return extract_excel(data)


def run_extraction_pipeline(
    data: bytes,
    filename: str,
    content_type: str | None,
    document_type: str,
    settings: Settings,
) -> ExtractResponse:
    doc = extract_text_from_bytes(data, filename, content_type, settings)
    doc, text_truncated = _truncate_text(doc, settings.max_text_chars)
    extracted_text = doc.tables_markdown or doc.full_text or ""
    document_type = resolve_document_type(document_type, filename, extracted_text)

    preview_source = doc.tables_markdown or doc.full_text
    text_preview = preview_source[:_PREVIEW_LEN] if preview_source else None

    if not settings.gemini_configured:
        meta_warnings = list(doc.warnings) + ["GEMINI_API_KEY not configured"]
        return ExtractResponse(
            success=False,
            data=[],
            meta=ExtractMeta(
                detected_type=doc.detected_type,
                document_type=document_type,
                validation_errors=["Gemini API key is not configured"],
                warnings=meta_warnings,
                text_truncated=text_truncated,
                extracted_text_preview=text_preview,
            ),
        )

    if not doc.full_text.strip() and not (doc.tables_markdown or "").strip():
        return ExtractResponse(
            success=False,
            data=[],
            meta=ExtractMeta(
                detected_type=doc.detected_type,
                document_type=document_type,
                validation_errors=["No text could be extracted from document"],
                warnings=doc.warnings,
                text_truncated=text_truncated,
                extracted_text_preview=text_preview,
            ),
        )

    gemini = GeminiExtractor(settings)
    raw = gemini.extract(doc, document_type=document_type)
    response = build_response(
        raw,
        detected_type=doc.detected_type,
        document_type=document_type,
        extraction_warnings=doc.warnings,
        text_truncated=text_truncated,
    )
    response.meta.extracted_text_preview = text_preview
    response.meta.document_type = document_type
    return response
