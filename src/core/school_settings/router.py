"""API for school settings (PDF branding and payment details)."""

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import get_current_user, require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.core.school_settings.schemas import SchoolSettingsResponse, SchoolSettingsUpdate
from src.core.school_settings.service import get_school_settings, update_school_settings
from src.shared.schemas.base import ApiResponse

router = APIRouter(prefix="/school-settings", tags=["School Settings"])


@router.get("", response_model=ApiResponse[SchoolSettingsResponse])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get school settings (name, address, M-Pesa, bank, logo/stamp attachment IDs)."""
    row = await get_school_settings(db)
    await db.commit()
    return ApiResponse(
        success=True,
        data=SchoolSettingsResponse(
            id=row.id,
            school_name=row.school_name or "",
            school_address=row.school_address or "",
            school_phone=row.school_phone or "",
            school_email=row.school_email or "",
            use_paybill=row.use_paybill,
            mpesa_business_number=row.mpesa_business_number or "",
            use_bank_transfer=row.use_bank_transfer,
            bank_name=row.bank_name or "",
            bank_account_name=row.bank_account_name or "",
            bank_account_number=row.bank_account_number or "",
            bank_branch=row.bank_branch or "",
            bank_swift_code=row.bank_swift_code or "",
            logo_attachment_id=row.logo_attachment_id,
            stamp_attachment_id=row.stamp_attachment_id,
        ),
    )


@router.put("", response_model=ApiResponse[SchoolSettingsResponse])
async def put_settings(
    data: SchoolSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Update school settings (only SuperAdmin/Admin)."""
    row = await update_school_settings(db, data)
    await db.commit()
    return ApiResponse(
        success=True,
        message="School settings updated",
        data=SchoolSettingsResponse(
            id=row.id,
            school_name=row.school_name or "",
            school_address=row.school_address or "",
            school_phone=row.school_phone or "",
            school_email=row.school_email or "",
            use_paybill=row.use_paybill,
            mpesa_business_number=row.mpesa_business_number or "",
            use_bank_transfer=row.use_bank_transfer,
            bank_name=row.bank_name or "",
            bank_account_name=row.bank_account_name or "",
            bank_account_number=row.bank_account_number or "",
            bank_branch=row.bank_branch or "",
            bank_swift_code=row.bank_swift_code or "",
            logo_attachment_id=row.logo_attachment_id,
            stamp_attachment_id=row.stamp_attachment_id,
        ),
    )
