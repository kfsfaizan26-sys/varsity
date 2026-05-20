from __future__ import annotations

import json
import re


class GeminiServiceError(Exception):
    """Raised when the Gemini API returns a client-visible error."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _client_error_message(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        body = getattr(response, "text", None) or getattr(response, "body", None)
        if body:
            return str(body)[:800]
    return str(exc)[:800]


def _parse_error_code(message: str) -> int | None:
    """Extract HTTP-style code from google-genai error string or JSON body."""
    match = re.search(r'"code":\s*(\d+)', message)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{3})\s+RESOURCE_EXHAUSTED\b", message)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(429|503|403|400)\b", message)
    if match:
        return int(match.group(1))
    return None


def is_retryable_with_fallback(exc: Exception) -> bool:
    """True when trying another model may succeed (overload / unavailable)."""
    message = _client_error_message(exc).lower()
    code = getattr(exc, "code", None) or _parse_error_code(message)
    if code == 503 or "unavailable" in message or "high demand" in message:
        return True
    if code == 429 and "limit: 0" in message:
        return True
    return False


def raise_for_gemini_error(exc: Exception) -> None:
    """Map google-genai errors to GeminiServiceError with appropriate HTTP codes."""
    message = _client_error_message(exc)
    lowered = message.lower()
    code = getattr(exc, "code", None) or _parse_error_code(message)

    if code == 503 or "unavailable" in lowered or "high demand" in lowered:
        raise GeminiServiceError(
            "Gemini model is temporarily overloaded. The service tries fallback models "
            "automatically; wait 30 seconds and retry, or set GEMINI_MODEL=gemini-2.5-flash-lite in .env",
            status_code=503,
        ) from exc

    if code == 429 or "resource_exhausted" in lowered:
        raise GeminiServiceError(
            "Gemini API quota exceeded for this model. Set GEMINI_MODEL=gemini-2.5-flash-lite "
            "or enable billing: https://ai.google.dev/gemini-api/docs/rate-limits",
            status_code=429,
        ) from exc

    if code == 403 or "403" in message:
        raise GeminiServiceError(
            "Gemini API access denied. Check API key, enabled APIs, and billing.",
            status_code=403,
        ) from exc

    if code == 400:
        raise GeminiServiceError(
            f"Gemini rejected the request: {message[:300]}",
            status_code=400,
        ) from exc

    # Try to surface a short message from JSON error body
    try:
        payload = json.loads(message)
        short = payload.get("error", {}).get("message", message[:300])
    except (json.JSONDecodeError, TypeError):
        short = message[:300]

    raise GeminiServiceError(short, status_code=502) from exc
