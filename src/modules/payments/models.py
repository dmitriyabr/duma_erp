"""Payment and CreditAllocation models."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class PaymentMethod(StrEnum):
    """Payment method options."""

    MPESA = "mpesa"
    BANK_TRANSFER = "bank_transfer"


class PaymentStatus(StrEnum):
    """Payment status options."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Payment(Base):
    """
    Payment record - represents a credit top-up for a student.

    When a payment is completed, it adds to the student's credit balance.
    The credit balance can then be allocated to invoices.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    payment_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    receipt_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True, unique=True, index=True
    )

    student_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("students.id"), nullable=False, index=True
    )
    billing_account_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("billing_accounts.id"), nullable=False, index=True
    )
    preferred_invoice_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("invoices.id"), nullable=True, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # M-Pesa transaction ID, bank reference

    confirmation_attachment_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("attachments.id"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.PENDING.value, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="payments")
    billing_account: Mapped["BillingAccount"] = relationship(
        "BillingAccount", back_populates="payments"
    )
    preferred_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice", foreign_keys=[preferred_invoice_id]
    )
    received_by: Mapped["User"] = relationship("User")
    refunds: Mapped[list["PaymentRefund"]] = relationship(
        "PaymentRefund",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentRefund.created_at",
    )

    @property
    def is_completed(self) -> bool:
        return self.status == PaymentStatus.COMPLETED.value

    @property
    def is_pending(self) -> bool:
        return self.status == PaymentStatus.PENDING.value

    @property
    def is_cancelled(self) -> bool:
        return self.status == PaymentStatus.CANCELLED.value


class CreditAllocation(Base):
    """
    Credit allocation - represents allocation of credit balance to an invoice.

    When credit is allocated to an invoice, the invoice's paid_amount increases
    and the student's available credit balance decreases.
    """

    __tablename__ = "credit_allocations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    student_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("students.id"), nullable=False, index=True
    )
    billing_account_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("billing_accounts.id"), nullable=False, index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("invoices.id"), nullable=False, index=True
    )
    invoice_line_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("invoice_lines.id"), nullable=True
    )
    source_payment_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("payments.id"), nullable=True, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    allocated_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student")
    billing_account: Mapped["BillingAccount"] = relationship(
        "BillingAccount", back_populates="allocations"
    )
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="allocations")
    invoice_line: Mapped["InvoiceLine"] = relationship("InvoiceLine")
    allocated_by: Mapped["User"] = relationship("User")
    source_payment: Mapped["Payment | None"] = relationship("Payment")
    reversals: Mapped[list["CreditAllocationReversal"]] = relationship(
        "CreditAllocationReversal",
        back_populates="allocation",
        cascade="all, delete-orphan",
        order_by="CreditAllocationReversal.reversed_at",
    )


class CreditAllocationReversal(Base):
    """Historical reduction recorded against a credit allocation."""

    __tablename__ = "credit_allocation_reversals"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    credit_allocation_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("credit_allocations.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_by_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=True
    )
    reversed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    allocation: Mapped["CreditAllocation"] = relationship(
        "CreditAllocation",
        back_populates="reversals",
    )
    reversed_by: Mapped["User | None"] = relationship("User")


class PaymentRefund(Base):
    """Refund recorded against a completed student payment."""

    __tablename__ = "payment_refunds"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("payments.id"), nullable=False, index=True
    )
    billing_account_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("billing_accounts.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    refund_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    refund_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_attachment_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("attachments.id"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    payment: Mapped["Payment"] = relationship("Payment", back_populates="refunds")
    billing_account: Mapped["BillingAccount"] = relationship(
        "BillingAccount",
        back_populates="refunds",
    )
    refunded_by: Mapped["User"] = relationship("User")


# Import for type hints
from src.core.auth.models import User
from src.modules.billing_accounts.models import BillingAccount
from src.modules.students.models import Student
from src.modules.invoices.models import Invoice, InvoiceLine
