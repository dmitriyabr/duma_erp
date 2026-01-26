from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.base import BaseModel


class UserRole(StrEnum):
    """User roles in the system."""

    SUPER_ADMIN = "SuperAdmin"
    ADMIN = "Admin"
    USER = "User"
    ACCOUNTANT = "Accountant"


class User(BaseModel):
    """
    User model for authentication and authorization.

    Note: User represents an employee. Not all employees have system access.
    If password_hash is NULL, the user cannot login (e.g., a guard who paid
    for something but doesn't use the system - manager creates compensation for them).
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def has_role(self, *roles: UserRole) -> bool:
        """Check if user has any of the specified roles."""
        return self.role in [r.value for r in roles]

    @property
    def can_login(self) -> bool:
        """Check if user can login (has password set)."""
        return self.password_hash is not None

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN.value

    @property
    def is_admin(self) -> bool:
        return self.role in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)
