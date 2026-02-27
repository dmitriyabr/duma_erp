"""M-Pesa C2B events for audit and idempotency."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class MpesaC2BEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    UNMATCHED = "unmatched"
    IGNORED = "ignored"
    ERROR = "error"


class MpesaC2BEvent(Base):
    __tablename__ = "mpesa_c2b_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    trans_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    business_short_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    bill_ref_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    derived_student_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    trans_time_raw: Mapped[str | None] = mapped_column(String(32), nullable=True)

    msisdn: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    payer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    raw_payload: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MpesaC2BEventStatus.RECEIVED.value, index=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payment_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    payment: Mapped["Payment | None"] = relationship("Payment", foreign_keys=[payment_id])


from src.modules.payments.models import Payment  # noqa: E402

