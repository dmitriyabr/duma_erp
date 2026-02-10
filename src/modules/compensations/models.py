"""Compensation models (Expense Claims)."""

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


class ExpenseClaimStatus(StrEnum):
    """Expense claim status."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


class ExpenseClaim(Base):
    """Expense claim (out-of-pocket reimbursement or generated from a procurement payment)."""

    __tablename__ = "expense_claims"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    claim_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    payment_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("procurement_payments.id"), nullable=True, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False, index=True
    )
    purpose_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_purposes.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExpenseClaimStatus.PENDING_APPROVAL.value, index=True
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    auto_created_from_payment: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )
    related_procurement_payment_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
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
    payment: Mapped["ProcurementPayment"] = relationship("ProcurementPayment")
    employee: Mapped["User"] = relationship("User")
    purpose: Mapped["PaymentPurpose"] = relationship("PaymentPurpose")

    @property
    def employee_name(self) -> str:
        # Expect relationship to be eager-loaded in service queries to avoid async lazy-load.
        return self.employee.full_name


class PayoutMethod(StrEnum):
    """Payout method."""

    MPESA = "mpesa"
    BANK = "bank"
    CASH = "cash"
    OTHER = "other"


class CompensationPayout(Base):
    """Payout to employee."""

    __tablename__ = "compensation_payouts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    payout_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False, index=True
    )
    payout_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_attachment_id: Mapped[int | None] = mapped_column(BigIntPK, nullable=True)

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
    employee: Mapped["User"] = relationship("User")
    allocations: Mapped[list["PayoutAllocation"]] = relationship(
        "PayoutAllocation", back_populates="payout", cascade="all, delete-orphan"
    )


class PayoutAllocation(Base):
    """Allocation of payout to expense claims."""

    __tablename__ = "payout_allocations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    payout_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("compensation_payouts.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("expense_claims.id"), nullable=False, index=True
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    payout: Mapped["CompensationPayout"] = relationship(
        "CompensationPayout", back_populates="allocations"
    )
    claim: Mapped["ExpenseClaim"] = relationship("ExpenseClaim")


class EmployeeBalance(Base):
    """Employee balance summary."""

    __tablename__ = "employee_balances"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    total_approved: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    total_paid: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
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
    employee: Mapped["User"] = relationship("User")
