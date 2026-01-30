"""School settings model — one row for PDF branding and payment details."""

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class SchoolSettings(Base):
    """Single row: school name, address, Paybill/bank details, logo and stamp (attachment IDs)."""

    __tablename__ = "school_settings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    school_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    school_address: Mapped[str | None] = mapped_column(String(500), nullable=True, default="")
    school_phone: Mapped[str | None] = mapped_column(String(100), nullable=True, default="")
    school_email: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    use_paybill: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mpesa_business_number: Mapped[str | None] = mapped_column(String(50), nullable=True, default="")
    use_bank_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    bank_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    bank_account_number: Mapped[str | None] = mapped_column(String(100), nullable=True, default="")
    bank_branch: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    bank_swift_code: Mapped[str | None] = mapped_column(String(50), nullable=True, default="")
    logo_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stamp_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    logo_attachment: Mapped["Attachment | None"] = relationship(
        "Attachment",
        foreign_keys=[logo_attachment_id],
    )
    stamp_attachment: Mapped["Attachment | None"] = relationship(
        "Attachment",
        foreign_keys=[stamp_attachment_id],
    )


from src.core.attachments.models import Attachment  # noqa: E402