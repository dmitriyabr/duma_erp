"""Student withdrawal settlement models."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class WithdrawalSettlementStatus(StrEnum):
    """Withdrawal settlement lifecycle."""

    POSTED = "posted"
    VOIDED = "voided"


class WithdrawalSettlementLineAction(StrEnum):
    """Manual action applied by a withdrawal settlement."""

    KEEP_CHARGED = "keep_charged"
    CANCEL_UNPAID = "cancel_unpaid"
    WRITE_OFF = "write_off"
    REFUND_ALLOCATION = "refund_allocation"
    DEDUCTION = "deduction"


class WithdrawalSettlement(Base):
    """Manual accounting document for student withdrawal."""

    __tablename__ = "withdrawal_settlements"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    settlement_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.id"), nullable=False, index=True
    )
    billing_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("billing_accounts.id"), nullable=False, index=True
    )
    refund_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_refunds.id"), nullable=True, index=True
    )
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WithdrawalSettlementStatus.POSTED.value, index=True
    )
    retained_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    deduction_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    write_off_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    cancelled_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    remaining_collectible_debt: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("attachments.id"), nullable=True, index=True
    )
    created_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    student: Mapped["Student"] = relationship("Student")
    billing_account: Mapped["BillingAccount"] = relationship("BillingAccount")
    refund: Mapped["PaymentRefund | None"] = relationship("PaymentRefund")
    proof_attachment: Mapped["Attachment | None"] = relationship("Attachment")
    created_by: Mapped["User"] = relationship("User")
    lines: Mapped[list["WithdrawalSettlementLine"]] = relationship(
        "WithdrawalSettlementLine",
        back_populates="settlement",
        cascade="all, delete-orphan",
        order_by="WithdrawalSettlementLine.id",
    )
    invoice_adjustments: Mapped[list["InvoiceAdjustment"]] = relationship(
        "InvoiceAdjustment",
        back_populates="settlement",
        order_by="InvoiceAdjustment.created_at",
    )


class WithdrawalSettlementLine(Base):
    """Line item describing one manual settlement action."""

    __tablename__ = "withdrawal_settlement_lines"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    settlement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("withdrawal_settlements.id"), nullable=False, index=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("invoices.id"), nullable=True, index=True
    )
    invoice_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("invoice_lines.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    settlement: Mapped["WithdrawalSettlement"] = relationship(
        "WithdrawalSettlement", back_populates="lines"
    )
    invoice: Mapped["Invoice | None"] = relationship("Invoice")
    invoice_line: Mapped["InvoiceLine | None"] = relationship("InvoiceLine")


from src.core.attachments.models import Attachment
from src.core.auth.models import User
from src.modules.billing_accounts.models import BillingAccount
from src.modules.invoices.models import Invoice, InvoiceAdjustment, InvoiceLine
from src.modules.payments.models import PaymentRefund
from src.modules.students.models import Student
