"""Service for school settings (single row)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.school_settings.models import SchoolSettings
from src.core.school_settings.schemas import SchoolSettingsUpdate


async def get_school_settings(db: AsyncSession) -> SchoolSettings:
    """Get the single school settings row; create with defaults if missing."""
    result = await db.execute(select(SchoolSettings).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SchoolSettings(
            school_name="",
            school_address="",
            school_phone="",
            school_email="",
            use_paybill=True,
            mpesa_business_number="",
            use_bank_transfer=False,
            bank_name="",
            bank_account_name="",
            bank_account_number="",
            bank_branch="",
            bank_swift_code="",
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
    return row


async def update_school_settings(
    db: AsyncSession,
    data: SchoolSettingsUpdate,
) -> SchoolSettings:
    """Update school settings (only provided fields)."""
    row = await get_school_settings(db)
    update = data.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(row, key, value)
    await db.flush()
    await db.refresh(row)
    return row
