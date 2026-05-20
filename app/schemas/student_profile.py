from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Address(BaseModel):
    line1: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class PersonalInfo(BaseModel):
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    nationality: str | None = None


class ContactInfo(BaseModel):
    email: str | None = None
    phone: str | None = None
    address: Address | None = None


class Guardian(BaseModel):
    name: str | None = None
    relationship: str | None = None
    phone: str | None = None
    email: str | None = None


class AcademicInfo(BaseModel):
    previous_institution: str | None = None
    board_or_curriculum: str | None = None
    year_of_passing: int | None = None
    qualification: str | None = None


class Identifiers(BaseModel):
    application_number: str | None = None
    roll_number: str | None = None


class ProfileMeta(BaseModel):
    detected_type: Literal["pdf_text", "pdf_scanned", "image", "excel"] | None = None
    document_type: str | None = None
    extraction_timestamp: datetime | None = None


class StudentProfile(BaseModel):
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    guardians: list[Guardian] = Field(default_factory=list)
    academic: AcademicInfo = Field(default_factory=AcademicInfo)
    identifiers: Identifiers = Field(default_factory=Identifiers)
    meta: ProfileMeta = Field(default_factory=ProfileMeta)

    @model_validator(mode="before")
    @classmethod
    def coerce_null_nested_objects(cls, data: object) -> object:
        """Gemini often returns null for nested objects; coerce to empty dicts."""
        if not isinstance(data, dict):
            return data
        for key in ("personal", "contact", "academic", "identifiers", "meta"):
            if data.get(key) is None:
                data[key] = {}
        contact = data.get("contact")
        if isinstance(contact, dict) and contact.get("address") is None:
            contact["address"] = {}
        if data.get("guardians") is None:
            data["guardians"] = []
        return data


class StudentListExtraction(BaseModel):
    """Multiple students from a class list, roster, or spreadsheet export."""

    students: list[StudentProfile] = Field(default_factory=list)
    document_summary: str | None = None
