"""Service for uploading and serving attachments."""

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.attachments.models import Attachment
from src.core.config import settings
from src.core.exceptions import ValidationError


ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def save_attachment(
    db: AsyncSession,
    file: UploadFile,
    created_by_id: int,
) -> Attachment:
    """Save uploaded file to storage and create Attachment record. Accepts images and PDF."""
    if not file.filename or not file.filename.strip():
        raise ValidationError("File name is required")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Allowed types: images (JPEG, PNG, GIF, WebP) and PDF. Got: {content_type}"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValidationError(f"File size must not exceed {MAX_FILE_SIZE // (1024*1024)} MB")

    # Sanitize filename, keep extension
    base = Path(file.filename).stem[:100] or "file"
    ext = Path(file.filename).suffix[:20] or ""
    safe_name = f"{base}{ext}".replace("..", "")

    storage_dir = Path(settings.storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    unique = uuid.uuid4().hex[:12]
    relative_path = f"{unique}_{safe_name}"
    full_path = storage_dir / relative_path
    full_path.write_bytes(content)

    attachment = Attachment(
        file_name=file.filename[:255],
        content_type=content_type,
        storage_path=str(relative_path),
        file_size=len(content),
        created_by_id=created_by_id,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def get_attachment(db: AsyncSession, attachment_id: int) -> Attachment | None:
    """Get attachment by id."""
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    return result.scalar_one_or_none()
