"""Service for uploading and serving attachments."""

import io
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
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def _upload_to_s3(key: str, content: bytes) -> None:
    """Upload bytes to S3/R2 bucket."""
    import aioboto3

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    ) as s3:
        await s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
        )


async def _download_from_s3(key: str) -> bytes:
    """Download object from S3/R2 bucket."""
    import aioboto3

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    ) as s3:
        response = await s3.get_object(Bucket=settings.s3_bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()


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
            f"Allowed types: images (JPEG, PNG, GIF, WebP), PDF, and CSV. Got: {content_type}"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValidationError(f"File size must not exceed {MAX_FILE_SIZE // (1024*1024)} MB")

    # Sanitize filename, keep extension
    base = Path(file.filename).stem[:100] or "file"
    ext = Path(file.filename).suffix[:20] or ""
    safe_name = f"{base}{ext}".replace("..", "")

    unique = uuid.uuid4().hex[:12]
    relative_path = f"{unique}_{safe_name}"

    if settings.use_s3:
        await _upload_to_s3(relative_path, content)
    else:
        storage_dir = Path(settings.storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)
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


async def get_attachment_content(attachment: Attachment) -> bytes:
    """Read attachment bytes from storage (local or S3/R2)."""
    if settings.use_s3:
        return await _download_from_s3(attachment.storage_path)
    full_path = Path(settings.storage_path) / attachment.storage_path
    return full_path.read_bytes()


async def get_attachment(db: AsyncSession, attachment_id: int) -> Attachment | None:
    """Get attachment by id."""
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    return result.scalar_one_or_none()
