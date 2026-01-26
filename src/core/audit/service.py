from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit.models import AuditLog


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
