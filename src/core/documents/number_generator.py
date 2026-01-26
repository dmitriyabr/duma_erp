from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.documents.models import DocumentSequence


class DocumentNumberGenerator:
    """
    Generates sequential document numbers in format: PREFIX-YYYY-NNNNNN

    Examples:
        INV-2026-000001
        PAY-2026-000042
        STU-2026-001234
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, prefix: str, year: int | None = None) -> str:
        """
        Generate next document number for given prefix and year.

        Uses SELECT FOR UPDATE to ensure uniqueness in concurrent scenarios.
        """
        if year is None:
            year = datetime.now().year

        # Try to get existing sequence with lock
        stmt = (
            select(DocumentSequence)
            .where(DocumentSequence.prefix == prefix, DocumentSequence.year == year)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        sequence = result.scalar_one_or_none()

        if sequence is None:
            # Create new sequence
            sequence = DocumentSequence(prefix=prefix, year=year, last_number=0)
            self.session.add(sequence)
            await self.session.flush()

            # Re-fetch with lock
            result = await self.session.execute(stmt)
            sequence = result.scalar_one()

        # Increment and format
        sequence.last_number += 1
        await self.session.flush()

        return f"{prefix}-{year}-{sequence.last_number:06d}"


async def get_document_number(session: AsyncSession, prefix: str, year: int | None = None) -> str:
    """Convenience function to generate a document number."""
    generator = DocumentNumberGenerator(session)
    return await generator.generate(prefix, year)
