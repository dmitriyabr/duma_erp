from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.base import Base, BigIntPK


class AuditLog(Base):
    """Audit log for tracking all important changes in the system."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    user_id: Mapped[int | None] = mapped_column(BigIntPK, nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(BigIntPK, nullable=False)
    entity_identifier: Mapped[str | None] = mapped_column(String(200), nullable=True)

    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
