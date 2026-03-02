"""Employee master data model."""

from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class EmployeeStatus(StrEnum):
    """Employment status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


class Employee(Base):
    """Employee master record (HR data)."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    employee_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )  # EMP-YYYY-NNNNNN

    # Optional link to auth user (login account)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    # Personal info
    surname: Mapped[str] = mapped_column(String(200), nullable=False)
    first_name: Mapped[str] = mapped_column(String(200), nullable=False)
    second_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Contacts & address
    mobile_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    physical_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    town: Mapped[str | None] = mapped_column(String(200), nullable=True)
    postal_address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Job info
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    employee_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    salary: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Government / tax ids
    national_id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kra_pin_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nssf_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nhif_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Attachments (scans)
    national_id_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id"),
        nullable=True,
    )
    kra_pin_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id"),
        nullable=True,
    )
    nssf_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id"),
        nullable=True,
    )
    nhif_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id"),
        nullable=True,
    )
    bank_doc_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id"),
        nullable=True,
    )

    # Bank details
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_branch_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    bank_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branch_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_account_holder_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # Next of kin
    next_of_kin_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    next_of_kin_relationship: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    next_of_kin_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    next_of_kin_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relief flags
    has_mortgage_relief: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    has_insurance_relief: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Status & misc
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EmployeeStatus.ACTIVE.value,
        server_default=EmployeeStatus.ACTIVE.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
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

    @property
    def full_name(self) -> str:
        """Return full name in 'First Last' format."""
        middle = f" {self.second_name}" if self.second_name else ""
        return f"{self.first_name}{middle} {self.surname}".strip()

