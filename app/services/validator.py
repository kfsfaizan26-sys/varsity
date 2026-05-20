from __future__ import annotations

import re
from datetime import date, datetime, timezone

from pydantic import ValidationError

from app.schemas.api_responses import ExtractMeta, ExtractResponse
from app.schemas.student_profile import StudentListExtraction, StudentProfile
from app.services.gemini_extractor import is_list_document_type

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^(\+?\d{10,15}|\d{10})$")


def _age_years(dob: date) -> int:
    today = date.today()
    return (
        today.year
        - dob.year
        - ((today.month, today.day) < (dob.month, dob.day))
    )


def _has_student_identity(profile: StudentProfile) -> bool:
    personal = profile.personal
    ids = profile.identifiers
    if personal.full_name or personal.first_name or personal.last_name:
        return True
    if ids.roll_number or ids.application_number:
        return True
    return False


def validate_business_rules(
    profile: StudentProfile,
    *,
    list_mode: bool = False,
    student_index: int | None = None,
) -> tuple[list[str], list[str]]:
    """Return (validation_errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    prefix = f"students[{student_index}] " if student_index is not None else ""

    personal = profile.personal
    contact = profile.contact

    if not _has_student_identity(profile):
        errors.append(f"{prefix}Required: name or roll_number/application_number")
    elif list_mode and not personal.full_name and not (personal.first_name or personal.last_name):
        warnings.append(f"{prefix}full_name is missing (roll/id present)")

    if not personal.date_of_birth:
        if not list_mode:
            warnings.append(f"{prefix}date_of_birth is missing")
    else:
        age = _age_years(personal.date_of_birth)
        if age < 3 or age > 100:
            errors.append(f"{prefix}date_of_birth implies unreasonable age: {age}")

    if contact.email and not EMAIL_RE.match(contact.email):
        errors.append(f"{prefix}Invalid email: {contact.email}")

    if contact.phone:
        normalized = re.sub(r"[\s\-()]", "", contact.phone)
        if not PHONE_RE.match(normalized):
            errors.append(f"{prefix}Invalid phone: {contact.phone}")
    elif not list_mode:
        warnings.append(f"{prefix}phone is missing")

    if not list_mode and not contact.email and not contact.phone:
        warnings.append(f"{prefix}No contact email or phone found")

    for i, guardian in enumerate(profile.guardians):
        if guardian.email and not EMAIL_RE.match(guardian.email):
            errors.append(f"{prefix}Invalid guardian[{i}] email: {guardian.email}")

    return errors, warnings


def _apply_profile_meta(
    profile: StudentProfile,
    detected_type: str,
    document_type: str,
) -> StudentProfile:
    return profile.model_copy(
        update={
            "meta": profile.meta.model_copy(
                update={
                    "detected_type": detected_type,
                    "document_type": document_type,
                    "extraction_timestamp": datetime.now(timezone.utc),
                }
            )
        }
    )


def _resolve_list_mode(raw_data: dict, document_type: str) -> bool:
    if isinstance(raw_data.get("students"), list):
        return True
    return is_list_document_type(document_type)


def build_response(
    raw_data: dict,
    detected_type: str,
    document_type: str,
    extraction_warnings: list[str],
    text_truncated: bool = False,
) -> ExtractResponse:
    meta = ExtractMeta(
        detected_type=detected_type,
        document_type=document_type,
        text_truncated=text_truncated,
        warnings=list(extraction_warnings),
    )

    list_mode = _resolve_list_mode(raw_data, document_type)

    if list_mode:
        return _build_list_response(raw_data, detected_type, document_type, meta)

    return _build_single_response(raw_data, detected_type, document_type, meta)


def _build_single_response(
    raw_data: dict,
    detected_type: str,
    document_type: str,
    meta: ExtractMeta,
) -> ExtractResponse:
    try:
        profile = StudentProfile.model_validate(raw_data)
    except ValidationError as exc:
        meta.validation_errors = [e["msg"] for e in exc.errors()]
        return ExtractResponse(
            success=False,
            data=[],
            meta=meta,
            raw_gemini=raw_data,
        )

    profile = _apply_profile_meta(profile, detected_type, document_type)
    biz_errors, biz_warnings = validate_business_rules(profile, list_mode=False)
    meta.validation_errors.extend(biz_errors)
    meta.warnings.extend(biz_warnings)
    meta.student_count = 1

    success = len(meta.validation_errors) == 0
    return ExtractResponse(
        success=success,
        data=[profile] if success else [],
        meta=meta,
        raw_gemini=raw_data if not success else None,
    )


def _build_list_response(
    raw_data: dict,
    detected_type: str,
    document_type: str,
    meta: ExtractMeta,
) -> ExtractResponse:
    # Gemini sometimes returns a single student object instead of {students: [...]}
    if "students" not in raw_data and "personal" in raw_data:
        raw_data = {"students": [raw_data]}

    try:
        parsed = StudentListExtraction.model_validate(raw_data)
    except ValidationError as exc:
        meta.validation_errors = [e["msg"] for e in exc.errors()]
        return ExtractResponse(
            success=False,
            data=[],
            meta=meta,
            raw_gemini=raw_data,
        )

    students: list[StudentProfile] = []
    for index, profile in enumerate(parsed.students):
        profile = _apply_profile_meta(profile, detected_type, document_type)
        biz_errors, biz_warnings = validate_business_rules(
            profile, list_mode=True, student_index=index
        )
        meta.validation_errors.extend(biz_errors)
        meta.warnings.extend(biz_warnings)
        students.append(profile)

    meta.student_count = len(students)

    if meta.student_count == 0:
        meta.validation_errors.append("No students found in document")

    if meta.student_count == 1:
        meta.warnings.append(
            "Only 1 student extracted — for class lists use document_type=student_list "
            "and ensure the full table is in the PDF"
        )

    success = len(meta.validation_errors) == 0 and meta.student_count > 0
    return ExtractResponse(
        success=success,
        data=students if success else [],
        meta=meta,
        raw_gemini=raw_data if not success else None,
    )
