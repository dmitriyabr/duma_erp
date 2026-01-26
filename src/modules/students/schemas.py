"""Schemas for Students module."""

import re
from datetime import date

from pydantic import BaseModel, Field, field_validator

from src.modules.students.models import Gender


# Kenyan phone regex: +254 followed by 9 digits
KENYAN_PHONE_REGEX = re.compile(r"^\+254[0-9]{9}$")


# --- Grade Schemas ---


class GradeCreate(BaseModel):
    """Schema for creating a grade."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = Field(0, ge=0)


class GradeUpdate(BaseModel):
    """Schema for updating a grade."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=100)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class GradeResponse(BaseModel):
    """Schema for grade response."""

    id: int
    code: str
    name: str
    display_order: int
    is_active: bool

    model_config = {"from_attributes": True}


# --- Student Schemas ---


class StudentCreate(BaseModel):
    """Schema for creating a student."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: Gender
    grade_id: int
    transport_zone_id: int | None = None
    guardian_name: str = Field(..., min_length=1, max_length=200)
    guardian_phone: str = Field(..., min_length=10, max_length=20)
    guardian_email: str | None = Field(None, max_length=255)
    enrollment_date: date | None = None
    notes: str | None = None

    @field_validator("guardian_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate Kenyan phone format."""
        # Normalize: remove spaces and dashes
        normalized = v.replace(" ", "").replace("-", "")

        # If starts with 0, convert to +254
        if normalized.startswith("0") and len(normalized) == 10:
            normalized = "+254" + normalized[1:]

        # If starts with 254, add +
        if normalized.startswith("254") and len(normalized) == 12:
            normalized = "+" + normalized

        if not KENYAN_PHONE_REGEX.match(normalized):
            raise ValueError(
                "Phone must be in Kenyan format: +254XXXXXXXXX (e.g., +254712345678)"
            )
        return normalized


class StudentUpdate(BaseModel):
    """Schema for updating a student."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    grade_id: int | None = None
    transport_zone_id: int | None = None
    guardian_name: str | None = Field(None, min_length=1, max_length=200)
    guardian_phone: str | None = Field(None, min_length=10, max_length=20)
    guardian_email: str | None = Field(None, max_length=255)
    enrollment_date: date | None = None
    notes: str | None = None

    @field_validator("guardian_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Validate Kenyan phone format if provided."""
        if v is None:
            return v

        # Normalize: remove spaces and dashes
        normalized = v.replace(" ", "").replace("-", "")

        # If starts with 0, convert to +254
        if normalized.startswith("0") and len(normalized) == 10:
            normalized = "+254" + normalized[1:]

        # If starts with 254, add +
        if normalized.startswith("254") and len(normalized) == 12:
            normalized = "+" + normalized

        if not KENYAN_PHONE_REGEX.match(normalized):
            raise ValueError(
                "Phone must be in Kenyan format: +254XXXXXXXXX (e.g., +254712345678)"
            )
        return normalized


class StudentResponse(BaseModel):
    """Schema for student response."""

    id: int
    student_number: str
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    gender: str
    grade_id: int
    grade_name: str | None = None
    transport_zone_id: int | None
    transport_zone_name: str | None = None
    guardian_name: str
    guardian_phone: str
    guardian_email: str | None
    status: str
    enrollment_date: date | None
    notes: str | None
    created_by_id: int

    model_config = {"from_attributes": True}


