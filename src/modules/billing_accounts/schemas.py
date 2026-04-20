"""Schemas for shared billing accounts."""

from datetime import date
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from src.modules.students.models import Gender
from src.modules.students.schemas import KENYAN_PHONE_REGEX
from src.shared.schemas.base import BaseSchema


class BillingAccountMemberResponse(BaseSchema):
    id: int
    student_id: int
    student_number: str
    student_name: str
    grade_name: str | None = None
    guardian_name: str
    guardian_phone: str
    status: str


class BillingAccountChildCreate(BaseSchema):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: Gender
    grade_id: int
    transport_zone_id: int | None = None
    guardian_name: str | None = Field(None, min_length=1, max_length=200)
    guardian_phone: str | None = Field(None, min_length=10, max_length=20)
    guardian_email: str | None = Field(None, max_length=255)
    enrollment_date: date | None = None
    notes: str | None = None

    @field_validator("guardian_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value

        normalized = value.replace(" ", "").replace("-", "")
        if normalized.startswith("0") and len(normalized) == 10:
            normalized = "+254" + normalized[1:]
        if normalized.startswith("254") and len(normalized) == 12:
            normalized = "+" + normalized

        if not KENYAN_PHONE_REGEX.match(normalized):
            raise ValueError(
                "Phone must be in Kenyan format: +254XXXXXXXXX (e.g., +254712345678)"
            )
        return normalized


class BillingAccountCreate(BaseSchema):
    display_name: str = Field(..., min_length=1, max_length=255)
    primary_guardian_name: str | None = Field(None, max_length=200)
    primary_guardian_phone: str | None = Field(None, max_length=20)
    primary_guardian_email: str | None = Field(None, max_length=255)
    notes: str | None = None
    student_ids: list[int] = Field(default_factory=list, max_length=50)
    new_children: list[BillingAccountChildCreate] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_members_present(self) -> "BillingAccountCreate":
        if not self.student_ids and not self.new_children:
            raise ValueError("Select at least one existing student or add at least one new child")
        return self


class BillingAccountUpdate(BaseSchema):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    primary_guardian_name: str | None = Field(None, max_length=200)
    primary_guardian_phone: str | None = Field(None, max_length=20)
    primary_guardian_email: str | None = Field(None, max_length=255)
    notes: str | None = None


class BillingAccountAddMembersRequest(BaseSchema):
    student_ids: list[int] = Field(..., min_length=1, max_length=50)


class BillingAccountListFilters(BaseSchema):
    search: str | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


class BillingAccountSummary(BaseSchema):
    id: int
    account_number: str
    primary_student_number: str | None = None
    display_name: str
    primary_guardian_name: str | None = None
    primary_guardian_phone: str | None = None
    primary_guardian_email: str | None = None
    notes: str | None = None
    member_count: int
    available_balance: Decimal
    outstanding_debt: Decimal
    balance: Decimal
    created_at: date | None = None


class BillingAccountDetail(BillingAccountSummary):
    members: list[BillingAccountMemberResponse]
