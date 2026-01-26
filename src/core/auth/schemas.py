from datetime import datetime

from pydantic import EmailStr

from src.shared.schemas import BaseSchema


class LoginRequest(BaseSchema):
    """Login request schema."""

    email: EmailStr
    password: str


class TokenResponse(BaseSchema):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseSchema):
    """Refresh token request schema."""

    refresh_token: str


class UserResponse(BaseSchema):
    """User response schema."""

    id: int
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class LoginResponse(BaseSchema):
    """Login response with user and tokens."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
