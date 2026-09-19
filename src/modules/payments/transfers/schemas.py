"""Payment transfer requests and reviewable effects."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from src.shared.schemas import BaseSchema


class TransferPreviewRequest(BaseSchema):
    target_student_id: int = Field(gt=0)


class TransferRequest(TransferPreviewRequest):
    reason: str = Field(min_length=1, max_length=2000)
    preview_token: str = Field(min_length=64, max_length=64)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A transfer reason is required")
        return value.strip()


class TransferParty(BaseSchema):
    student_id: int
    student_name: str
    student_number: str
    billing_account_id: int
    account_number: str
    account_name: str


class TransferInvoiceImpact(BaseSchema):
    invoice_id: int
    invoice_number: str
    student_name: str
    amount: Decimal
    due_before: Decimal
    due_after: Decimal


class TransferAllocationSlice(BaseSchema):
    invoice_id: int
    amount: Decimal
    created_at: datetime | None


class TransferPreview(BaseSchema):
    payment_id: int
    payment_number: str
    amount: Decimal
    source: TransferParty
    target: TransferParty
    removed_allocations: list[TransferInvoiceImpact]
    new_allocations: list[TransferInvoiceImpact]
    allocation_schedule: list[TransferAllocationSlice]
    source_credit_before: Decimal
    source_credit_after: Decimal
    target_credit_before: Decimal
    target_credit_after: Decimal
    preview_token: str = ""
