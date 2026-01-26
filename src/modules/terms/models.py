from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import BaseModel, Base, BigIntPK


class TermStatus(StrEnum):
    """Term status enum."""

    DRAFT = "Draft"
    ACTIVE = "Active"
    CLOSED = "Closed"


class Term(BaseModel):
    """
    Academic term (trimester/semester).

    Each year has 3 terms. Only one term can be Active at a time.
    When a term is Closed, no new invoices can be created for it,
    but payments can still be received (to close outstanding debts).
    """

    __tablename__ = "terms"

    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    term_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, or 3
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "2026-T1"

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TermStatus.DRAFT.value, index=True
    )

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Relationships
    price_settings: Mapped[list["PriceSetting"]] = relationship(
        "PriceSetting", back_populates="term", cascade="all, delete-orphan"
    )
    transport_pricings: Mapped[list["TransportPricing"]] = relationship(
        "TransportPricing", back_populates="term", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("year", "term_number", name="uq_term_year_number"),
    )

    @property
    def is_active(self) -> bool:
        return self.status == TermStatus.ACTIVE.value

    @property
    def is_closed(self) -> bool:
        return self.status == TermStatus.CLOSED.value

    @property
    def is_draft(self) -> bool:
        return self.status == TermStatus.DRAFT.value


class PriceSetting(BaseModel):
    """
    School fee prices per grade for a specific term.
    """

    __tablename__ = "price_settings"

    term_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("terms.id"), nullable=False)
    grade: Mapped[str] = mapped_column(String(50), nullable=False)  # 'PP1', 'Grade 1', etc.
    school_fee_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    term: Mapped["Term"] = relationship("Term", back_populates="price_settings")

    __table_args__ = (
        UniqueConstraint("term_id", "grade", name="uq_price_setting_term_grade"),
    )


class TransportZone(Base):
    """
    Transport zones for student pickup/dropoff.
    """

    __tablename__ = "transport_zones"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    zone_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    transport_pricings: Mapped[list["TransportPricing"]] = relationship(
        "TransportPricing", back_populates="zone"
    )


class TransportPricing(BaseModel):
    """
    Transport fee per zone for a specific term.
    """

    __tablename__ = "transport_pricings"

    term_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("terms.id"), nullable=False)
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transport_zones.id"), nullable=False)
    transport_fee_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    term: Mapped["Term"] = relationship("Term", back_populates="transport_pricings")
    zone: Mapped["TransportZone"] = relationship("TransportZone", back_populates="transport_pricings")

    __table_args__ = (
        UniqueConstraint("term_id", "zone_id", name="uq_transport_pricing_term_zone"),
    )


class FixedFee(BaseModel):
    """
    Fixed fees that don't change per term (admission, interview, diary, etc.).
    """

    __tablename__ = "fixed_fees"

    fee_type: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
