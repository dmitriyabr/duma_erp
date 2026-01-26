from datetime import datetime

from pydantic import EmailStr, field_validator

from src.core.auth.models import UserRole
from src.shared.schemas import BaseSchema


class UserCreate(BaseSchema):
    """Schema for creating a new user."""

    email: EmailStr
    password: str | None = None  # None = user cannot login (employee without system access)
    full_name: str
    phone: str | None = None
    role: UserRole

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserUpdate(BaseSchema):
    """Schema for updating a user."""

    email: EmailStr | None = None
    full_name: str | None = None
    phone: str | None = None
    role: UserRole | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Full name must be at least 2 characters")
        return v


class SetPassword(BaseSchema):
    """Schema for setting/changing password."""

    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ChangeOwnPassword(BaseSchema):
    """Schema for user changing their own password."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseSchema):
    """Schema for user response."""

    id: int
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    can_login: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListFilters(BaseSchema):
    """Filters for user list."""

    role: UserRole | None = None
    is_active: bool | None = None
    search: str | None = None  # Search by name or email
    page: int = 1
    limit: int = 20
