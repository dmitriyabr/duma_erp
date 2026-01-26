from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import CurrentUser
from src.core.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from src.core.auth.service import AuthService
from src.core.database import get_db
from src.shared.schemas import SuccessResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=SuccessResponse[LoginResponse])
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens."""
    auth_service = AuthService(db)

    # Get client IP
    ip_address = request.client.host if request.client else None

    user, access_token, refresh_token = await auth_service.authenticate(
        email=data.email,
        password=data.password,
        ip_address=ip_address,
    )

    return SuccessResponse(
        data=LoginResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            refresh_token=refresh_token,
        ),
        message="Login successful",
    )


@router.post("/refresh", response_model=SuccessResponse[TokenResponse])
async def refresh_tokens(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)

    access_token, refresh_token = await auth_service.refresh_tokens(data.refresh_token)

    return SuccessResponse(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        ),
        message="Tokens refreshed",
    )


@router.get("/me", response_model=SuccessResponse[UserResponse])
async def get_current_user_info(current_user: CurrentUser):
    """Get current authenticated user info."""
    return SuccessResponse(
        data=UserResponse.model_validate(current_user),
        message="User info retrieved",
    )
