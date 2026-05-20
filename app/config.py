from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_fallback_models: str = "gemini-flash-latest,gemini-2.5-flash"
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000"
    ocr_lang: str = "eng"
    tesseract_cmd: str = ""
    max_text_chars: int = 100000
    max_image_dimension: int = 2500
    pdf_text_threshold: int = 100

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def gemini_model_chain(self) -> list[str]:
        """Primary model first, then fallbacks (deduplicated)."""
        chain: list[str] = []
        for name in [self.gemini_model, *self.gemini_fallback_models.split(",")]:
            name = name.strip()
            if name and name not in chain:
                chain.append(name)
        return chain


@lru_cache
def get_settings() -> Settings:
    return Settings()
