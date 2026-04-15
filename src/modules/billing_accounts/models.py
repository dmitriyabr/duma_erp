"""Billing account models for shared student payments."""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, relationship, mapped_column

from src.core.database.base import BaseModel


class BillingAccount(BaseModel):
    """Financial owner for one or more students."""

    __tablename__ = "billing_accounts"

    account_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_guardian_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primary_guardian_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached_credit_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    created_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )

    created_by: Mapped["User"] = relationship("User")
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="billing_account",
        order_by="Student.last_name, Student.first_name, Student.id",
    )
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="billing_account")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="billing_account")
    allocations: Mapped[list["CreditAllocation"]] = relationship(
        "CreditAllocation",
        back_populates="billing_account",
    )


from src.core.auth.models import User
from src.modules.invoices.models import Invoice
from src.modules.payments.models import CreditAllocation, Payment
from src.modules.students.models import Student
