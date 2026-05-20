from __future__ import annotations

from app.services.document_type_resolver import resolve_document_type


def test_resolve_from_filename():
    assert resolve_document_type("admission_form", "student_list.pdf") == "student_list"
    assert resolve_document_type("admission_form", "Class_Roster_2024.pdf") == "student_list"


def test_explicit_list_type():
    assert resolve_document_type("student_list", "form.pdf") == "student_list"
