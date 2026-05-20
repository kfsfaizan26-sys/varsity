from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from google import genai
from google.genai import types

from app.config import Settings
from app.models.extracted_document import ExtractedDocument
from app.schemas.student_profile import StudentListExtraction, StudentProfile
from app.services.gemini_errors import (
    GeminiServiceError,
    is_retryable_with_fallback,
    raise_for_gemini_error,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_SINGLE = """You are an expert at extracting student admission form data.
Read the provided document text and return ONLY valid JSON matching the schema.
Use null for fields not found. Dates must be YYYY-MM-DD strings.
Do not invent data that is not supported by the text.
For nested objects (personal, contact, academic, identifiers), use {} not null when empty."""

LIST_COLUMN_MAPPING = """
Column mapping (copy values EXACTLY from the document — do not use null if the cell has text):
- Roll No / Roll / Roll Number / Reg No → identifiers.roll_number
- S.No / Sr No / Serial (only if no roll column) → identifiers.application_number
- Name / Student Name / Student → personal.full_name (also split first_name, last_name if obvious)
- Father / Father Name / Parent / Guardian → guardians[0].name, relationship "Father" or "Guardian"
- Mother / Mother Name → guardians entry with relationship "Mother"
- Phone / Mobile / Contact / Tel → contact.phone
- Email / E-mail → contact.email
- DOB / Date of Birth → personal.date_of_birth as YYYY-MM-DD
- Class / Section / Grade → academic.qualification or leave in academic fields
- Address → contact.address.line1
"""

SYSTEM_PROMPT_LIST = f"""You extract ALL students from class lists, rosters, attendance sheets, or bulk PDFs/Excel exports.
Return ONLY valid JSON matching the schema with a top-level "students" array.
CRITICAL:
- Include EVERY data row in students — one array element per student row (skip header row only).
- If the input has pipe-separated table rows (col1 | col2 | col3), each row is one student.
- Copy roll numbers and names exactly as printed. NEVER return null for a field when the source row has that value.
{LIST_COLUMN_MAPPING}
Use null ONLY when the source document truly has no value for that field.
Dates must be YYYY-MM-DD strings. For nested objects use {{}} not null when empty."""


def is_list_document_type(document_type: str) -> bool:
    dt = document_type.lower().replace("-", "_")
    return any(
        token in dt
        for token in ("student_list", "class_list", "roster", "bulk", "multi_student")
    )


def _build_user_prompt(
    doc: ExtractedDocument,
    schema: dict[str, Any],
    *,
    list_mode: bool,
) -> str:
    if list_mode:
        intro = (
            "Extract ALL students into the students array. "
            "Each table row = one student. Pipe-separated lines are table rows.\n"
        )
    else:
        intro = "Extract student admission profile data from this document.\n"

    parts = [intro, f"Source file type: {doc.detected_type}\n"]

    # Tables first — student lists are usually tabular
    if doc.tables_markdown:
        parts.extend(
            [
                "--- TABLES (read row-by-row) ---\n",
                doc.tables_markdown,
                "\n",
            ]
        )

    parts.extend(
        [
            "--- FULL DOCUMENT TEXT ---\n",
            doc.full_text,
        ]
    )
    parts.extend(
        [
            "\n--- JSON SCHEMA ---\n",
            json.dumps(schema, indent=2),
            "\nRespond with JSON only, no markdown fences.",
        ]
    )
    return "".join(parts)


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)```\s*$", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


class GeminiExtractor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _generate_raw(
        self,
        model: str,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
        )
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part(text=system_prompt),
                    types.Part(text=prompt),
                ],
            )
        ]
        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return response.text or ""

    def _generate_with_fallback(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        models = self._settings.gemini_model_chain
        last_error: Exception | None = None

        for index, model in enumerate(models):
            try:
                logger.info("Gemini request using model=%s", model)
                return self._generate_raw(
                    model,
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
            except GeminiServiceError:
                raise
            except Exception as exc:
                last_error = exc
                has_more = index < len(models) - 1
                if has_more and is_retryable_with_fallback(exc):
                    logger.warning(
                        "Gemini model %s failed (%s), trying fallback",
                        model,
                        type(exc).__name__,
                    )
                    time.sleep(1.5)
                    continue
                raise_for_gemini_error(exc)

        if last_error:
            raise_for_gemini_error(last_error)
        raise GeminiServiceError("No Gemini models configured", status_code=500)

    def extract(self, doc: ExtractedDocument, document_type: str) -> dict[str, Any]:
        list_mode = is_list_document_type(document_type)
        if list_mode:
            schema = StudentListExtraction.model_json_schema()
            system_prompt = SYSTEM_PROMPT_LIST
        else:
            schema = StudentProfile.model_json_schema()
            system_prompt = SYSTEM_PROMPT_SINGLE

        prompt = _build_user_prompt(doc, schema, list_mode=list_mode)
        try:
            raw = self._generate_with_fallback(prompt, system_prompt=system_prompt)
            try:
                return _parse_json_response(raw)
            except (json.JSONDecodeError, AttributeError, ValueError) as first_error:
                logger.warning("Gemini JSON parse failed, retrying: %s", first_error)
                return self._retry_fix_json(prompt, system_prompt=system_prompt)
        except GeminiServiceError:
            raise

    def extract_profile(self, doc: ExtractedDocument, document_type: str = "admission_form") -> dict[str, Any]:
        """Backward-compatible alias."""
        return self.extract(doc, document_type)

    def _retry_fix_json(self, original_prompt: str, *, system_prompt: str) -> dict[str, Any]:
        fix_prompt = (
            original_prompt
            + "\n\nYour previous response was invalid JSON. "
            "Return ONLY corrected valid JSON matching the schema."
        )
        raw = self._generate_with_fallback(
            fix_prompt,
            system_prompt=system_prompt,
            temperature=0.0,
        )
        return _parse_json_response(raw)
