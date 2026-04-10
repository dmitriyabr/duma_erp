"""Schemas for family/shared billing accounts."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from src.modules.billing_accounts.models import BillingAccountType
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


class BillingAccountCreate(BaseSchema):
    display_name: str = Field(..., min_length=1, max_length=255)
    primary_guardian_name: str | None = Field(None, max_length=200)
    primary_guardian_phone: str | None = Field(None, max_length=20)
    primary_guardian_email: str | None = Field(None, max_length=255)
    notes: str | None = None
    student_ids: list[int] = Field(..., min_length=2, max_length=50)


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
    account_type: BillingAccountType | None = BillingAccountType.FAMILY
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


class BillingAccountSummary(BaseSchema):
    id: int
    account_number: str
    display_name: str
    account_type: str
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
