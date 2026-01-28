"""Attachment model for payment confirmations and proofs."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class Attachment(Base):
    """Stored file (image or PDF) for payment confirmation / proof."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)  # relative path or S3 key
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False, index=True
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

    created_by: Mapped["User"] = relationship("User")


from src.core.auth.models import User  # noqa: E402
