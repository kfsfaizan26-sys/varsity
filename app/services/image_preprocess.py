from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.config import Settings


def _pil_to_cv(image: Image.Image) -> np.ndarray:
    if image.mode != "RGB":
        image = image.convert("RGB")
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _cv_to_pil(array: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _deskew(gray: np.ndarray) -> np.ndarray:
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def preprocess_image_bytes(data: bytes, settings: Settings) -> bytes:
    """EXIF rotate, resize, grayscale + deskew for OCR."""
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)

    max_dim = settings.max_image_dimension
    w, h = image.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        image = image.resize(
            (int(w * scale), int(h * scale)),
            Image.Resampling.LANCZOS,
        )

    bgr = _pil_to_cv(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = _deskew(gray)
    # mild contrast boost
    gray = cv2.convertScaleAbs(gray, alpha=1.2, beta=10)

    out = _cv_to_pil(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
    buffer = io.BytesIO()
    out.save(buffer, format="PNG")
    return buffer.getvalue()
