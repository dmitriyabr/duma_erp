from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.jwt import decode_token
from src.core.auth.models import User, UserRole
from src.core.auth.service import AuthService
from src.core.database import get_db
from src.core.exceptions import AuthenticationError, AuthorizationError


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get current authenticated user from JWT token.

    Usage:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    if not authorization:
        raise AuthenticationError("Authorization header required")

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header format")

    token = authorization.replace("Bearer ", "")

    payload = decode_token(token, token_type="access")
    user_id = int(payload["sub"])

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    return user


def require_roles(*roles: UserRole):
    """
    Dependency factory to require specific roles.

    Usage:
        @router.post("/users")
        async def create_user(
            user: User = Depends(require_roles(UserRole.SUPER_ADMIN))
        ):
            ...
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.has_role(*roles):
            allowed = ", ".join(r.value for r in roles)
            raise AuthorizationError(f"Required role: {allowed}")
        return current_user

    return role_checker


# Convenience dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
SuperAdminUser = Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))]
