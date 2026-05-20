from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DetectedDocType = Literal["pdf_text", "pdf_scanned", "image", "excel"]


class ExtractedDocument(BaseModel):
    full_text: str
    detected_type: DetectedDocType
    page_count: int | None = None
    tables_markdown: str | None = None
    warnings: list[str] = Field(default_factory=list)
