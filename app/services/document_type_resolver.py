from __future__ import annotations

import re

from app.services.gemini_extractor import is_list_document_type

_LIST_FILENAME_TOKENS = (
    "student_list",
    "students_list",
    "class_list",
    "roster",
    "studentlist",
    "bulk",
    "attendance",
)

# Headers that strongly signal a student roster/list document
_LIST_HEADER_RE = re.compile(
    r"\b(student\s+list|class\s+list|attendance\s+(sheet|register)|roster|roll\s+sheet)\b",
    re.IGNORECASE,
)

# A "student row" looks like:  <name words>  <roll/number>  (optional more cols)
# Matches lines that contain at least one capitalised word followed by digits
_STUDENT_ROW_RE = re.compile(r"^[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+\s+\d+", re.MULTILINE)

# Minimum number of matching student rows to treat the document as a list
_MIN_STUDENT_ROWS = 3


def looks_like_student_list(text: str) -> bool:
    """
    Return True when the extracted text appears to contain a multi-student
    roster, even if the caller passed document_type=admission_form.

    Heuristic:
      - Document has a list-type header keyword (e.g. "STUDENT LIST"), OR
      - At least _MIN_STUDENT_ROWS lines match the <Name> <RollNumber> pattern.
    """
    if not text:
        return False
    if _LIST_HEADER_RE.search(text):
        return True
    matches = _STUDENT_ROW_RE.findall(text)
    return len(matches) >= _MIN_STUDENT_ROWS


def resolve_document_type(document_type: str, filename: str, extracted_text: str = "") -> str:
    """
    Determine the effective document type.

    Priority:
    1. Explicit list type in query param  → honour as-is
    2. Filename contains a list token     → upgrade to student_list
    3. Extracted text looks like a roster → upgrade to student_list
    4. Fall back to the original document_type
    """
    if is_list_document_type(document_type):
        return document_type

    name = (filename or "").lower().replace("-", "_").replace(" ", "_")
    if any(token in name for token in _LIST_FILENAME_TOKENS):
        return "student_list"

    if looks_like_student_list(extracted_text):
        return "student_list"

    return document_type
