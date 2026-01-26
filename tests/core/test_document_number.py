import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.documents import get_document_number


class TestDocumentNumberGenerator:
    """Tests for document number generator."""

    async def test_generate_first_number(self, db_session: AsyncSession):
        """Test generating first document number."""
        number = await get_document_number(db_session, "INV", year=2026)
        assert number == "INV-2026-000001"

    async def test_generate_sequential_numbers(self, db_session: AsyncSession):
        """Test generating sequential document numbers."""
        num1 = await get_document_number(db_session, "INV", year=2026)
        num2 = await get_document_number(db_session, "INV", year=2026)
        num3 = await get_document_number(db_session, "INV", year=2026)

        assert num1 == "INV-2026-000001"
        assert num2 == "INV-2026-000002"
        assert num3 == "INV-2026-000003"

    async def test_different_prefixes(self, db_session: AsyncSession):
        """Test that different prefixes have independent sequences."""
        inv = await get_document_number(db_session, "INV", year=2026)
        pay = await get_document_number(db_session, "PAY", year=2026)
        inv2 = await get_document_number(db_session, "INV", year=2026)

        assert inv == "INV-2026-000001"
        assert pay == "PAY-2026-000001"
        assert inv2 == "INV-2026-000002"

    async def test_different_years(self, db_session: AsyncSession):
        """Test that different years have independent sequences."""
        num_2026 = await get_document_number(db_session, "INV", year=2026)
        num_2027 = await get_document_number(db_session, "INV", year=2027)
        num_2026_2 = await get_document_number(db_session, "INV", year=2026)

        assert num_2026 == "INV-2026-000001"
        assert num_2027 == "INV-2027-000001"
        assert num_2026_2 == "INV-2026-000002"

    async def test_format_with_leading_zeros(self, db_session: AsyncSession):
        """Test that numbers are padded with leading zeros."""
        for _ in range(99):
            await get_document_number(db_session, "STU", year=2026)

        num_100 = await get_document_number(db_session, "STU", year=2026)
        assert num_100 == "STU-2026-000100"
