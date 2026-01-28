"""API for uploading and downloading attachments."""

import io

from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.attachments.schemas import AttachmentResponse
from src.core.attachments.service import get_attachment, get_attachment_content, save_attachment
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User, UserRole
from src.core.auth.dependencies import require_roles
from src.core.database.session import get_db
from src.shared.schemas.base import ApiResponse

router = APIRouter(prefix="/attachments", tags=["Attachments"])


@router.post("", response_model=ApiResponse[AttachmentResponse], status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)),
):
    """Upload a confirmation file (image or PDF). Returns attachment id for use in payment/payout forms."""
    attachment = await save_attachment(db, file, current_user.id)
    await db.commit()
    return ApiResponse(
        success=True,
        message="File uploaded",
        data=AttachmentResponse(
            id=attachment.id,
            file_name=attachment.file_name,
            content_type=attachment.content_type,
            file_size=attachment.file_size,
            created_at=attachment.created_at,
        ),
    )


@router.get("/{attachment_id}", response_model=ApiResponse[AttachmentResponse])
async def get_attachment_info(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get attachment metadata."""
    attachment = await get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return ApiResponse(
        success=True,
        data=AttachmentResponse(
            id=attachment.id,
            file_name=attachment.file_name,
            content_type=attachment.content_type,
            file_size=attachment.file_size,
            created_at=attachment.created_at,
        ),
    )


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download attachment file (for viewing confirmation). Uses local storage or S3/R2."""
    attachment = await get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    try:
        content = await get_attachment_content(attachment)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return StreamingResponse(
        io.BytesIO(content),
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.file_name}"'},
    )
