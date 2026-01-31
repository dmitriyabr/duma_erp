"""API endpoints for Expense Claims."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.compensations.schemas import (
    ApproveExpenseClaimRequest,
    CompensationPayoutCreate,
    CompensationPayoutResponse,
    EmployeeBalanceResponse,
    EmployeeBalancesBatchRequest,
    EmployeeBalancesBatchResponse,
    ExpenseClaimResponse,
)
from src.modules.compensations.service import ExpenseClaimService, PayoutService
from src.shared.schemas.base import ApiResponse, PaginatedResponse


router = APIRouter(prefix="/compensations/claims", tags=["Compensations"])


def _claim_to_response(claim) -> ExpenseClaimResponse:
    return ExpenseClaimResponse.model_validate(claim)


def _payout_to_response(payout) -> CompensationPayoutResponse:
    return CompensationPayoutResponse.model_validate(payout)


def _balance_to_response(balance) -> EmployeeBalanceResponse:
    return EmployeeBalanceResponse.model_validate(balance)


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[ExpenseClaimResponse]],
)
async def list_claims(
    employee_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UserRole)),
):
    """List expense claims. Regular users see only their own claims."""
    service = ExpenseClaimService(db)
    # Для обычных пользователей всегда фильтруем по их ID
    if current_user.role == UserRole.USER:
        employee_id = current_user.id
    claims, total = await service.list_claims(
        employee_id=employee_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_claim_to_response(c) for c in claims],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/{claim_id}",
    response_model=ApiResponse[ExpenseClaimResponse],
)
async def get_claim(
    claim_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UserRole)),
):
    """Get expense claim by ID. Regular users can only see their own claims."""
    service = ExpenseClaimService(db)
    claim = await service.get_claim_by_id(claim_id)
    # Проверяем, что обычный пользователь может видеть только свои claims
    if current_user.role == UserRole.USER and claim.employee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own expense claims",
        )
    return ApiResponse(success=True, data=_claim_to_response(claim))


@router.post(
    "/{claim_id}/approve",
    response_model=ApiResponse[ExpenseClaimResponse],
)
async def approve_claim(
    claim_id: int,
    data: ApproveExpenseClaimRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Approve or reject an expense claim."""
    service = ExpenseClaimService(db)
    claim = await service.approve_claim(
        claim_id, approve=data.approve, reason=data.reason
    )
    return ApiResponse(success=True, data=_claim_to_response(claim))


payouts_router = APIRouter(prefix="/compensations/payouts", tags=["Compensations"])


@payouts_router.post(
    "",
    response_model=ApiResponse[CompensationPayoutResponse],
)
async def create_payout(
    data: CompensationPayoutCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create payout with FIFO allocations."""
    service = PayoutService(db)
    payout = await service.create_payout(data)
    return ApiResponse(success=True, data=_payout_to_response(payout))


@payouts_router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[CompensationPayoutResponse]],
)
async def list_payouts(
    employee_id: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """List payouts (read-only for Accountant)."""
    service = PayoutService(db)
    payouts, total = await service.list_payouts(
        employee_id=employee_id, date_from=date_from, date_to=date_to, page=page, limit=limit
    )
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_payout_to_response(p) for p in payouts],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@payouts_router.get(
    "/{payout_id}",
    response_model=ApiResponse[CompensationPayoutResponse],
)
async def get_payout(
    payout_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """Get payout by ID (read-only for Accountant)."""
    service = PayoutService(db)
    payout = await service.get_payout_by_id(payout_id)
    return ApiResponse(success=True, data=_payout_to_response(payout))


@payouts_router.post(
    "/employee-balances-batch",
    response_model=ApiResponse[EmployeeBalancesBatchResponse],
)
async def get_employee_balances_batch(
    payload: EmployeeBalancesBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UserRole)),
):
    """Get balances for multiple employees in one request. USER role gets only own balance."""
    employee_ids = payload.employee_ids
    if current_user.role == UserRole.USER:
        employee_ids = [current_user.id] if current_user.id in employee_ids else []
    service = PayoutService(db)
    balances = await service.get_employee_balances_batch(employee_ids)
    return ApiResponse(success=True, data=EmployeeBalancesBatchResponse(balances=balances))


@payouts_router.get(
    "/employees/{employee_id}/balance",
    response_model=ApiResponse[EmployeeBalanceResponse],
)
async def get_employee_balance(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UserRole)),
):
    """Get employee balance. Regular users can only see their own balance."""
    # Проверяем, что обычный пользователь может видеть только свой баланс
    if current_user.role == UserRole.USER and employee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own balance",
        )
    service = PayoutService(db)
    balance = await service.get_employee_balance(employee_id)
    return ApiResponse(success=True, data=_balance_to_response(balance))
