from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.base import Base


class DocumentSequence(Base):
    """Stores document number sequences per prefix and year."""

    __tablename__ = "document_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("prefix", "year", name="uq_document_sequence_prefix_year"),
    )
