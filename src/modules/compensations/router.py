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
    EmployeeClaimTotalsResponse,
    ExpenseClaimCreate,
    ExpenseClaimResponse,
    ExpenseClaimUpdate,
)
from src.modules.compensations.service import ExpenseClaimService, PayoutService
from src.shared.schemas.base import ApiResponse, PaginatedResponse


router = APIRouter(prefix="/compensations/claims", tags=["Compensations"])


def _claim_to_response(claim) -> ExpenseClaimResponse:
    payment = getattr(claim, "payment", None)
    fee_payment = getattr(claim, "fee_payment", None)
    expense_amount = payment.amount if payment else claim.amount
    fee_amount = fee_payment.amount if fee_payment else getattr(claim, "fee_amount", None) or 0
    return ExpenseClaimResponse(
        id=claim.id,
        claim_number=claim.claim_number,
        payment_id=claim.payment_id,
        fee_payment_id=getattr(claim, "fee_payment_id", None),
        employee_id=claim.employee_id,
        employee_name=claim.employee_name,
        purpose_id=payment.purpose_id if payment else claim.purpose_id,
        amount=claim.amount,
        expense_amount=expense_amount,
        fee_amount=fee_amount,
        payee_name=payment.payee_name if payment else None,
        description=claim.description,
        rejection_reason=claim.rejection_reason,
        expense_date=payment.payment_date if payment else claim.expense_date,
        proof_text=payment.proof_text if payment else None,
        proof_attachment_id=payment.proof_attachment_id if payment else None,
        fee_proof_text=fee_payment.proof_text if fee_payment else None,
        fee_proof_attachment_id=fee_payment.proof_attachment_id if fee_payment else None,
        status=claim.status,
        paid_amount=claim.paid_amount,
        remaining_amount=claim.remaining_amount,
        auto_created_from_payment=claim.auto_created_from_payment,
        related_procurement_payment_id=payment.id if payment else claim.related_procurement_payment_id,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def _payout_to_response(payout) -> CompensationPayoutResponse:
    return CompensationPayoutResponse.model_validate(payout)


def _balance_to_response(balance) -> EmployeeBalanceResponse:
    return EmployeeBalanceResponse.model_validate(balance)


@router.post(
    "",
    response_model=ApiResponse[ExpenseClaimResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_claim(
    data: ExpenseClaimCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)),
):
    """Create an out-of-pocket expense claim (no PO/GRN required)."""
    # USER can only create for self.
    employee_id = data.employee_id or current_user.id
    if current_user.role == UserRole.USER:
        employee_id = current_user.id

    # Ensure employee exists (can be user without login password).
    from src.core.auth.service import AuthService

    employee = await AuthService(db).get_user_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    service = ExpenseClaimService(db)
    claim = await service.create_out_of_pocket_claim(
        data,
        employee_id=employee_id,
        created_by_id=current_user.id,
    )
    return ApiResponse(
        success=True,
        message="Expense claim created",
        data=_claim_to_response(claim),
    )


@router.patch(
    "/{claim_id}",
    response_model=ApiResponse[ExpenseClaimResponse],
)
async def update_claim(
    claim_id: int,
    data: ExpenseClaimUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)),
):
    """Update a draft claim. USER can only update own draft claims."""
    service = ExpenseClaimService(db)
    claim = await service.get_claim_by_id(claim_id)
    if current_user.role == UserRole.USER and claim.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own claims")

    # Service requires employee_id to match claim owner. For admins, pass the claim owner.
    owner_id = current_user.id if current_user.role == UserRole.USER else claim.employee_id
    updated = await service.update_out_of_pocket_claim(claim_id, data, employee_id=owner_id)
    return ApiResponse(success=True, message="Expense claim updated", data=_claim_to_response(updated))


@router.post(
    "/{claim_id}/submit",
    response_model=ApiResponse[ExpenseClaimResponse],
)
async def submit_claim(
    claim_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)),
):
    """Submit a draft claim for approval."""
    service = ExpenseClaimService(db)
    claim = await service.get_claim_by_id(claim_id)
    if current_user.role == UserRole.USER and claim.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only submit your own claims")
    owner_id = current_user.id if current_user.role == UserRole.USER else claim.employee_id
    submitted = await service.submit_claim(claim_id, employee_id=owner_id)
    return ApiResponse(success=True, message="Expense claim submitted", data=_claim_to_response(submitted))


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
        claim_id,
        approve=data.approve,
        reason=data.reason,
        acted_by_id=current_user.id,
    )
    return ApiResponse(success=True, data=_claim_to_response(claim))


@router.get(
    "/employees/{employee_id}/totals",
    response_model=ApiResponse[EmployeeClaimTotalsResponse],
)
async def get_employee_claim_totals(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UserRole)),
):
    """Get claimant-friendly totals (includes pending approval)."""
    if current_user.role == UserRole.USER and employee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own totals",
        )
    totals = await PayoutService(db).get_employee_claim_totals(employee_id)
    return ApiResponse(success=True, data=totals)


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
