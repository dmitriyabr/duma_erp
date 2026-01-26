from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.jwt import create_access_token, create_refresh_token, decode_token
from src.core.auth.models import User, UserRole
from src.core.auth.password import hash_password, verify_password
from src.core.audit import AuditAction, create_audit_log
from src.core.exceptions import AuthenticationError, DuplicateError, NotFoundError


class AuthService:
    """Service for authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: UserRole,
        phone: str | None = None,
        created_by_id: int | None = None,
    ) -> User:
        """Create a new user."""
        # Check for duplicate email
        existing = await self.get_user_by_email(email)
        if existing:
            raise DuplicateError("User", "email", email)

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            phone=phone,
            role=role.value,
            is_active=True,
        )

        self.session.add(user)
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.CREATE,
            entity_type="User",
            entity_id=user.id,
            user_id=created_by_id,
            entity_identifier=user.email,
            new_values={"email": user.email, "role": user.role, "full_name": user.full_name},
        )

        return user

    async def authenticate(
        self, email: str, password: str, ip_address: str | None = None
    ) -> tuple[User, str, str]:
        """
        Authenticate user and return tokens.

        Returns:
            Tuple of (user, access_token, refresh_token)

        Raises:
            AuthenticationError: If credentials are invalid
        """
        user = await self.get_user_by_email(email)

        if not user:
            raise AuthenticationError("Invalid email or password")

        if not user.can_login:
            raise AuthenticationError("User does not have system access")

        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("User account is deactivated")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()

        # Generate tokens
        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.LOGIN,
            entity_type="User",
            entity_id=user.id,
            user_id=user.id,
            entity_identifier=user.email,
            ip_address=ip_address,
        )

        return user, access_token, refresh_token

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        """
        Refresh access token using refresh token.

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        payload = decode_token(refresh_token, token_type="refresh")

        user_id = int(payload["sub"])
        user = await self.get_user_by_id(user_id)

        if not user:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("User account is deactivated")

        new_access_token = create_access_token(user.id, user.role)
        new_refresh_token = create_refresh_token(user.id)

        return new_access_token, new_refresh_token
