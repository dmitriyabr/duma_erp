from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import AdminUser, CurrentUser, require_roles, SuperAdminUser
from src.core.auth.models import User, UserRole
from src.core.database import get_db
from src.core.exceptions import AuthorizationError
from src.modules.users.schemas import (
    ChangeOwnPassword,
    SetPassword,
    UserCreate,
    UserListFilters,
    UserResponse,
    UserUpdate,
)
from src.modules.users.service import UserService
from src.shared.schemas import PaginatedResponse, SuccessResponse
from src.shared.schemas.base import ApiResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=ApiResponse[PaginatedResponse[UserResponse]])
async def list_users(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)),
    role: UserRole | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    List all users (employees).

    SuperAdmin, Admin, and Accountant (read-only) can access.
    """
    service = UserService(db)

    filters = UserListFilters(
        role=role,
        is_active=is_active,
        search=search,
        page=page,
        limit=limit,
    )

    users, total = await service.list_users(filters)

    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[UserResponse.model_validate(u) for u in users],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get("/{user_id}", response_model=SuccessResponse[UserResponse])
async def get_user(
    user_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user by ID.

    Only SuperAdmin can access this endpoint.
    """
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        from src.core.exceptions import NotFoundError
        raise NotFoundError("User", user_id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="User retrieved",
    )


@router.post("", response_model=SuccessResponse[UserResponse], status_code=201)
async def create_user(
    data: UserCreate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user (employee).

    Only SuperAdmin can create users.

    If password is not provided, the user will be created without system access
    (useful for employees who don't use the system, like guards).
    """
    service = UserService(db)
    user = await service.create(data, created_by_id=current_user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="User created successfully",
    )


@router.put("/{user_id}", response_model=SuccessResponse[UserResponse])
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update user data.

    Only SuperAdmin can update users.
    """
    service = UserService(db)
    user = await service.update(user_id, data, updated_by_id=current_user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="User updated successfully",
    )


@router.post("/{user_id}/deactivate", response_model=SuccessResponse[UserResponse])
async def deactivate_user(
    user_id: int,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a user.

    Only SuperAdmin can deactivate users.
    """
    service = UserService(db)
    user = await service.deactivate(user_id, deactivated_by_id=current_user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="User deactivated",
    )


@router.post("/{user_id}/activate", response_model=SuccessResponse[UserResponse])
async def activate_user(
    user_id: int,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a user.

    Only SuperAdmin can activate users.
    """
    service = UserService(db)
    user = await service.activate(user_id, activated_by_id=current_user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="User activated",
    )


@router.post("/{user_id}/set-password", response_model=SuccessResponse[UserResponse])
async def set_user_password(
    user_id: int,
    data: SetPassword,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Set or reset user password.

    Only SuperAdmin can set passwords.
    This grants system access to users who didn't have it.
    """
    service = UserService(db)
    user = await service.set_password(user_id, data.password, set_by_id=current_user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="Password set successfully",
    )


@router.post("/{user_id}/remove-password", response_model=SuccessResponse[UserResponse])
async def remove_user_password(
    user_id: int,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove user password (revoke system access).

    Only SuperAdmin can remove passwords.
    """
    # Prevent removing own password
    if user_id == current_user.id:
        raise AuthorizationError("Cannot remove your own password")

    service = UserService(db)
    user = await service.remove_password(user_id, removed_by_id=current_user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="System access revoked",
    )


@router.post("/me/change-password", response_model=SuccessResponse[UserResponse])
async def change_own_password(
    data: ChangeOwnPassword,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Change own password.

    Requires current password for verification.
    """
    service = UserService(db)
    user = await service.change_own_password(
        user_id=current_user.id,
        current_password=data.current_password,
        new_password=data.new_password,
    )
    user = await service.get_by_id(user.id)

    return SuccessResponse(
        data=UserResponse.model_validate(user),
        message="Password changed successfully",
    )
