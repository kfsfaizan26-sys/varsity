from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gemini_api_key="test-key",
        gemini_model="gemini-2.0-flash",
        max_upload_mb=25,
        pdf_text_threshold=50,
    )
