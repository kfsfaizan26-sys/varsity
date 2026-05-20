from __future__ import annotations

import os
import shutil
from functools import lru_cache

# Ensure Homebrew binaries (tesseract, pdfinfo, pdftoppm) are findable even
# when the server is launched without a full interactive shell (e.g. IDE terminals,
# launchd, or shells that haven't sourced /opt/homebrew/bin).
_HOMEBREW_PATHS = ["/opt/homebrew/bin", "/usr/local/bin"]
_current_path = os.environ.get("PATH", "")
_extra = ":".join(p for p in _HOMEBREW_PATHS if p not in _current_path)
if _extra:
    os.environ["PATH"] = _extra + ":" + _current_path

from app.config import Settings


class OcrNotAvailableError(Exception):
    """Raised when Tesseract OCR is required but not installed."""

    def __init__(self) -> None:
        super().__init__(
            "Tesseract OCR is not installed or not on PATH. "
            "macOS: brew install tesseract poppler — then restart the terminal and server. "
            "Linux: sudo apt install tesseract-ocr poppler-utils"
        )


def is_tesseract_available(settings: Settings | None = None) -> bool:
    cmd = (settings.tesseract_cmd if settings else "") or ""
    if cmd.strip():
        from pathlib import Path

        return Path(cmd.strip()).is_file()
    return shutil.which("tesseract") is not None


@lru_cache
def is_poppler_available() -> bool:
    return shutil.which("pdfinfo") is not None


def configure_tesseract(settings: Settings) -> None:
    """Point pytesseract at the binary if TESSERACT_CMD is set in .env."""
    if settings.tesseract_cmd:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def require_tesseract(settings: Settings) -> None:
    configure_tesseract(settings)
    if not is_tesseract_available(settings):
        raise OcrNotAvailableError()
