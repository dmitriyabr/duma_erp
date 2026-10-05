"""Immutable price snapshots used by historical cash reports."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.base import Base, BigIntPK


class TransportRepricing(Base):
    __tablename__ = "transport_repricings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoices.id"), index=True)
    invoice_line_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoice_lines.id"))
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transport_zones.id"))
    gross_before: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    net_before: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    gross_after: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    net_after: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    released_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    reason: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
