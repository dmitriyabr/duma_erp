from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit.models import AuditLog
from src.core.auth.models import User


class AuditAction(StrEnum):
    """Standard audit actions."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CANCEL = "CANCEL"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"

    # Domain-specific actions
    CREATE_PAYMENT = "CREATE_PAYMENT"
    CANCEL_PAYMENT = "CANCEL_PAYMENT"
    APPLY_DISCOUNT = "APPLY_DISCOUNT"
    GENERATE_INVOICES = "GENERATE_INVOICES"
    ISSUE_STOCK = "ISSUE_STOCK"
    RECEIVE_STOCK = "RECEIVE_STOCK"
    WRITE_OFF = "WRITE_OFF"
    ADJUSTMENT = "ADJUSTMENT"
    APPROVE_GRN = "APPROVE_GRN"
    APPROVE_CLAIM = "APPROVE_CLAIM"
    CREATE_PAYOUT = "CREATE_PAYOUT"
    ISSUE_UNIFORM = "ISSUE_UNIFORM"


class AuditService:
    """Service for creating audit logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str | AuditAction,
        entity_type: str,
        entity_id: int,
        user_id: int | None = None,
        entity_identifier: str | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        comment: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        audit_log = AuditLog(
            user_id=user_id,
            action=str(action),
            entity_type=entity_type,
            entity_id=entity_id,
            entity_identifier=entity_identifier,
            old_values=old_values,
            new_values=new_values,
            comment=comment,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(audit_log)
        await self.db.flush()

        return audit_log


async def create_audit_log(
    session: AsyncSession,
    action: str | AuditAction,
    entity_type: str,
    entity_id: int,
    user_id: int | None = None,
    entity_identifier: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    comment: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """
    Create an audit log entry.

    Args:
        session: Database session
        action: Action performed (e.g., CREATE, UPDATE, CANCEL)
        entity_type: Type of entity (e.g., Student, Invoice, Payment)
        entity_id: ID of the entity
        user_id: ID of the user who performed the action
        entity_identifier: Human-readable identifier (e.g., document number)
        old_values: State before change
        new_values: State after change
        comment: Additional comment
        ip_address: Client IP address
        user_agent: Client user agent

    Returns:
        Created AuditLog instance
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=str(action),
        entity_type=entity_type,
        entity_id=entity_id,
        entity_identifier=entity_identifier,
        old_values=old_values,
        new_values=new_values,
        comment=comment,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    session.add(audit_log)
    await session.flush()

    return audit_log


async def list_audit_entries(
    session: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    """
    List audit log entries with optional filters.
    Returns (list of (AuditLog, user_full_name), total_count).
    """
    q = (
        select(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
    )
    count_q = select(func.count()).select_from(AuditLog)
    if date_from is not None:
        q = q.where(AuditLog.created_at >= date_from)
        count_q = count_q.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        q = q.where(AuditLog.created_at <= date_to)
        count_q = count_q.where(AuditLog.created_at <= date_to)
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
        count_q = count_q.where(AuditLog.user_id == user_id)
    if entity_type is not None:
        q = q.where(AuditLog.entity_type == entity_type)
        count_q = count_q.where(AuditLog.entity_type == entity_type)
    if action is not None:
        q = q.where(AuditLog.action == action)
        count_q = count_q.where(AuditLog.action == action)

    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    q = q.offset((page - 1) * limit).limit(limit)
    result = await session.execute(q)
    rows = result.all()
    return [(row[0], row[1]) for row in rows], total
