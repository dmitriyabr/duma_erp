"""Schemas for student withdrawal settlements."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from src.modules.payments.schemas import BillingAccountRefundCreate, BillingAccountRefundPreview
from src.modules.withdrawals.models import WithdrawalSettlementLineAction
from src.shared.schemas.base import BaseSchema


class WithdrawalInvoiceActionRequest(BaseSchema):
    """Manual action for one invoice in a withdrawal settlement."""

    invoice_id: int | None = None
    invoice_line_id: int | None = None
    action: WithdrawalSettlementLineAction
    amount: Decimal = Field(gt=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_invoice_target(self):
        if self.action in (
            WithdrawalSettlementLineAction.CANCEL_UNPAID,
            WithdrawalSettlementLineAction.WRITE_OFF,
            WithdrawalSettlementLineAction.KEEP_CHARGED,
            WithdrawalSettlementLineAction.REFUND_ALLOCATION,
        ) and self.invoice_id is None:
            raise ValueError("invoice_id is required for this settlement action")
        return self


class WithdrawalSettlementRefundRequest(BillingAccountRefundCreate):
    """Optional outgoing refund created as part of a withdrawal settlement."""


class WithdrawalSettlementBaseRequest(BaseSchema):
    """Common manual settlement payload."""

    settlement_date: date
    reason: str = Field(..., min_length=3)
    retained_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    deduction_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None
    proof_attachment_id: int | None = None
    invoice_actions: list[WithdrawalInvoiceActionRequest] = Field(default_factory=list)
    refund: WithdrawalSettlementRefundRequest | None = None


class WithdrawalSettlementPreviewRequest(WithdrawalSettlementBaseRequest):
    """Payload for settlement preview."""


class WithdrawalSettlementCreate(WithdrawalSettlementBaseRequest):
    """Payload for posting settlement."""


class WithdrawalInvoiceImpact(BaseSchema):
    """Projected or posted invoice impact from a settlement."""

    invoice_id: int
    invoice_number: str
    student_id: int
    student_name: str | None = None
    invoice_type: str
    status_before: str
    status_after: str
    action: str
    amount: Decimal
    amount_due_before: Decimal
    amount_due_after: Decimal
    notes: str | None = None


class WithdrawalSettlementLineResponse(BaseSchema):
    """Posted settlement line."""

    id: int
    settlement_id: int
    invoice_id: int | None = None
    invoice_number: str | None = None
    invoice_line_id: int | None = None
    action: str
    amount: Decimal
    notes: str | None = None
    created_at: datetime


class InvoiceAdjustmentResponse(BaseSchema):
    """Receivable adjustment created by settlement."""

    id: int
    adjustment_number: str
    invoice_id: int
    invoice_number: str | None = None
    invoice_line_id: int | None = None
    settlement_id: int | None = None
    adjustment_type: str
    amount: Decimal
    reason: str
    notes: str | None = None
    created_by_id: int
    created_at: datetime


class WithdrawalSettlementPreview(BaseSchema):
    """Manual withdrawal settlement preview."""

    student_id: int
    student_name: str
    billing_account_id: int
    total_paid: Decimal
    current_outstanding_debt: Decimal
    retained_amount: Decimal
    deduction_amount: Decimal
    write_off_amount: Decimal
    cancelled_amount: Decimal
    refund_amount: Decimal
    remaining_collectible_debt_after: Decimal
    invoice_impacts: list[WithdrawalInvoiceImpact]
    refund_preview: BillingAccountRefundPreview | None = None
    warnings: list[str] = Field(default_factory=list)


class WithdrawalSettlementResponse(BaseSchema):
    """Posted settlement response."""

    id: int
    settlement_number: str
    student_id: int
    student_name: str | None = None
    billing_account_id: int
    refund_id: int | None = None
    refund_number: str | None = None
    settlement_date: date
    status: str
    retained_amount: Decimal
    deduction_amount: Decimal
    write_off_amount: Decimal
    cancelled_amount: Decimal
    refund_amount: Decimal
    remaining_collectible_debt: Decimal
    reason: str
    notes: str | None = None
    proof_attachment_id: int | None = None
    created_by_id: int
    posted_at: datetime
    created_at: datetime
    updated_at: datetime
    lines: list[WithdrawalSettlementLineResponse] = Field(default_factory=list)
    invoice_adjustments: list[InvoiceAdjustmentResponse] = Field(default_factory=list)
