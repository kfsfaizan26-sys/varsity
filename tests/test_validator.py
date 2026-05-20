from __future__ import annotations

from datetime import date

from app.schemas.student_profile import ContactInfo, PersonalInfo, StudentProfile
from app.services.validator import build_response, validate_business_rules


def test_validate_business_rules_missing_name():
    profile = StudentProfile()
    errors, _warnings = validate_business_rules(profile)
    assert any("name" in e for e in errors)


def test_validate_invalid_email():
    profile = StudentProfile(
        personal=PersonalInfo(full_name="Jane Doe", date_of_birth=date(2005, 1, 15)),
        contact=ContactInfo(email="not-an-email", phone="9876543210"),
    )
    errors, _warnings = validate_business_rules(profile)
    assert any("Invalid email" in e for e in errors)


def test_build_response_success():
    raw = {
        "personal": {
            "full_name": "Jane Doe",
            "date_of_birth": "2005-01-15",
        },
        "contact": {"email": "jane@school.edu", "phone": "9876543210"},
        "guardians": [],
        "academic": {},
        "identifiers": {},
        "meta": {},
    }
    response = build_response(
        raw,
        detected_type="pdf_text",
        document_type="admission_form",
        extraction_warnings=[],
    )
    assert response.success is True
    assert len(response.data) == 1
    assert response.data[0].personal.full_name == "Jane Doe"


def test_coerce_null_academic():
    raw = {
        "personal": {"full_name": "Aarav Kumar"},
        "contact": {"phone": "9876543210"},
        "guardians": [],
        "academic": None,
        "identifiers": {"roll_number": "101"},
        "meta": {},
    }
    response = build_response(
        raw,
        detected_type="pdf_text",
        document_type="admission_form",
        extraction_warnings=[],
    )
    assert response.success is True
    assert len(response.data) == 1


def test_build_list_response_multiple_students():
    raw = {
        "students": [
            {
                "personal": {"full_name": "Aarav Kumar"},
                "contact": {"phone": "9876543210"},
                "guardians": [],
                "academic": None,
                "identifiers": {"roll_number": "101"},
                "meta": {},
            },
            {
                "personal": {"full_name": "Priya Singh"},
                "contact": {"phone": "9876543211"},
                "guardians": [],
                "academic": None,
                "identifiers": {"roll_number": "102"},
                "meta": {},
            },
        ]
    }
    response = build_response(
        raw,
        detected_type="pdf_text",
        document_type="student_list",
        extraction_warnings=[],
    )
    assert response.success is True
    assert response.meta.student_count == 2
    assert len(response.data) == 2
    assert response.data[0].personal.full_name == "Aarav Kumar"
    assert response.data[1].personal.full_name == "Priya Singh"
