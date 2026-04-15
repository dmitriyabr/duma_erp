"""API endpoints for shared billing accounts."""

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.billing_accounts.schemas import (
    BillingAccountAddMembersRequest,
    BillingAccountChildCreate,
    BillingAccountCreate,
    BillingAccountDetail,
    BillingAccountListFilters,
    BillingAccountSummary,
    BillingAccountUpdate,
)
from src.modules.billing_accounts.service import BillingAccountService
from src.modules.payments.schemas import StatementResponse
from src.modules.payments.service import PaymentService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/billing-accounts", tags=["Billing Accounts"])


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[BillingAccountSummary]],
)
async def list_billing_accounts(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = BillingAccountService(db)
    filters = BillingAccountListFilters(
        search=search,
        page=page,
        limit=limit,
    )
    items, total = await service.list_billing_accounts(filters)
    return ApiResponse(
        data=PaginatedResponse.create(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )
    )


@router.post(
    "",
    response_model=ApiResponse[BillingAccountDetail],
    status_code=status.HTTP_201_CREATED,
)
async def create_billing_account(
    data: BillingAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = BillingAccountService(db)
    account = await service.create_family_account(data, current_user.id)
    detail = await service.get_billing_account_detail(account.id)
    return ApiResponse(data=detail, message="Billing account created successfully")


@router.get(
    "/{account_id}",
    response_model=ApiResponse[BillingAccountDetail],
)
async def get_billing_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = BillingAccountService(db)
    detail = await service.get_billing_account_detail(account_id)
    return ApiResponse(data=detail)


@router.patch(
    "/{account_id}",
    response_model=ApiResponse[BillingAccountDetail],
)
async def update_billing_account(
    account_id: int,
    data: BillingAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = BillingAccountService(db)
    account = await service.update_billing_account(account_id, data, current_user.id)
    detail = await service.get_billing_account_detail(account.id)
    return ApiResponse(data=detail, message="Billing account updated successfully")


@router.post(
    "/{account_id}/members",
    response_model=ApiResponse[BillingAccountDetail],
)
async def add_billing_account_members(
    account_id: int,
    data: BillingAccountAddMembersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = BillingAccountService(db)
    account = await service.add_members(account_id, data, current_user.id)
    detail = await service.get_billing_account_detail(account.id)
    return ApiResponse(data=detail, message="Students added to billing account")


@router.post(
    "/{account_id}/children",
    response_model=ApiResponse[BillingAccountDetail],
)
async def add_billing_account_child(
    account_id: int,
    data: BillingAccountChildCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = BillingAccountService(db)
    account = await service.add_child(account_id, data, current_user.id)
    detail = await service.get_billing_account_detail(account.id)
    return ApiResponse(data=detail, message="Child added to billing account")


@router.get(
    "/{account_id}/statement",
    response_model=ApiResponse[StatementResponse],
)
async def get_billing_account_statement(
    account_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = PaymentService(db)
    statement = await service.get_billing_account_statement(account_id, date_from, date_to)
    return ApiResponse(data=statement)
