from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.student_profile import StudentProfile


class ExtractMeta(BaseModel):
    detected_type: str | None = None
    document_type: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    text_truncated: bool = False
    student_count: int = 0
    extracted_text_preview: str | None = None


class ExtractResponse(BaseModel):
    """API response: data is always an array — one student object per element."""

    success: bool
    data: list[StudentProfile] = Field(default_factory=list)
    meta: ExtractMeta = Field(default_factory=ExtractMeta)
    raw_gemini: dict[str, Any] | None = None
