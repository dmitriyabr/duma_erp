"""Schemas for Discounts module."""

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from src.modules.discounts.models import DiscountValueType, StudentDiscountAppliesTo


# --- Discount Reason Schemas ---


class DiscountReasonCreate(BaseModel):
    """Schema for creating a discount reason."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)


class DiscountReasonUpdate(BaseModel):
    """Schema for updating a discount reason."""

    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class DiscountReasonResponse(BaseModel):
    """Schema for discount reason response."""

    id: int
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


# --- Discount Schemas (applied to invoice line) ---


class DiscountApply(BaseModel):
    """Schema for applying a discount to an invoice line."""

    invoice_line_id: int
    value_type: DiscountValueType
    value: Decimal = Field(..., gt=0)
    reason_id: int | None = None
    reason_text: str | None = None

    @model_validator(mode="after")
    def validate_percentage(self):
        """Validate percentage is not over 100."""
        if self.value_type == DiscountValueType.PERCENTAGE and self.value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return self


class DiscountResponse(BaseModel):
    """Schema for discount response."""

    id: int
    invoice_line_id: int
    value_type: str
    value: Decimal
    calculated_amount: Decimal
    reason_id: int | None
    reason_name: str | None = None
    reason_text: str | None
    student_discount_id: int | None
    applied_by_id: int

    model_config = {"from_attributes": True}


class DiscountRemove(BaseModel):
    """Schema for removing a discount."""

    discount_id: int


# --- Student Discount Schemas (standing discount) ---


class StudentDiscountCreate(BaseModel):
    """Schema for creating a student discount."""

    student_id: int
    applies_to: StudentDiscountAppliesTo = StudentDiscountAppliesTo.SCHOOL_FEE
    value_type: DiscountValueType
    value: Decimal = Field(..., gt=0)
    reason_id: int | None = None
    reason_text: str | None = None

    @model_validator(mode="after")
    def validate_percentage(self):
        """Validate percentage is not over 100."""
        if self.value_type == DiscountValueType.PERCENTAGE and self.value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return self


class StudentDiscountUpdate(BaseModel):
    """Schema for updating a student discount."""

    value_type: DiscountValueType | None = None
    value: Decimal | None = Field(None, gt=0)
    reason_id: int | None = None
    reason_text: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_percentage(self):
        """Validate percentage is not over 100."""
        if self.value_type == DiscountValueType.PERCENTAGE and self.value and self.value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return self


class StudentDiscountResponse(BaseModel):
    """Schema for student discount response."""

    id: int
    student_id: int
    student_name: str | None = None
    applies_to: str
    value_type: str
    value: Decimal
    reason_id: int | None
    reason_name: str | None = None
    reason_text: str | None
    is_active: bool
    created_by_id: int

    model_config = {"from_attributes": True}


