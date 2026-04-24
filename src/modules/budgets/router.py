"""API endpoints for budgets and employee advances."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.budgets.schemas import (
    BudgetAdvanceCreate,
    BudgetAdvanceIssueRequest,
    BudgetAdvanceResponse,
    BudgetAdvanceReturnCreate,
    BudgetAdvanceReturnResponse,
    BudgetAdvanceTransferCreate,
    BudgetAdvanceTransferResponse,
    BudgetClosureStatusResponse,
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
    MyBudgetAvailableBalanceResponse,
)
from src.modules.budgets.service import BudgetService
from src.shared.schemas.base import ApiResponse, PaginatedResponse


router = APIRouter(prefix="/budgets", tags=["Budgets"])

BudgetReadRole = Depends(
    require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
)
BudgetWriteRole = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))
BudgetUserRole = Depends(require_roles(*UserRole))


def _return_to_response(row) -> BudgetAdvanceReturnResponse:
    return BudgetAdvanceReturnResponse.model_validate(row)


def _transfer_to_response(row) -> BudgetAdvanceTransferResponse:
    return BudgetAdvanceTransferResponse(
        id=row.id,
        transfer_number=row.transfer_number,
        from_advance_id=row.from_advance_id,
        from_advance_number=row.from_advance.advance_number,
        to_budget_id=row.to_budget_id,
        to_budget_number=row.to_budget.budget_number,
        to_employee_id=row.to_employee_id,
        to_employee_name=getattr(row.to_employee, "full_name", None),
        transfer_date=row.transfer_date,
        amount=row.amount,
        transfer_type=row.transfer_type,
        reason=row.reason,
        created_to_advance_id=row.created_to_advance_id,
        created_to_advance_number=row.created_to_advance.advance_number,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
    )


@router.post("", response_model=ApiResponse[BudgetResponse], status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    budget = await service.create_budget(data, current_user.id)
    return ApiResponse(success=True, message="Budget created", data=BudgetResponse(**(await service.get_budget_snapshot(budget))))


@router.get("", response_model=ApiResponse[PaginatedResponse[BudgetResponse]])
async def list_budgets(
    status: str | None = Query(None),
    purpose_id: int | None = Query(None),
    employee_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    budgets, total = await service.list_budgets(
        status=status, purpose_id=purpose_id, employee_id=employee_id, page=page, limit=limit
    )
    items = [BudgetResponse(**(await service.get_budget_snapshot(budget))) for budget in budgets]
    return ApiResponse(success=True, data=PaginatedResponse.create(items, total, page, limit))


@router.get("/my/budgets", response_model=ApiResponse[list[BudgetResponse]])
async def list_my_budgets(
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetUserRole,
):
    service = BudgetService(db)
    budgets = await service.list_available_budgets_for_employee(current_user.id)
    items = [BudgetResponse(**(await service.get_budget_snapshot(budget))) for budget in budgets]
    return ApiResponse(success=True, data=items)


@router.get("/my/advances", response_model=ApiResponse[PaginatedResponse[BudgetAdvanceResponse]])
async def list_my_advances(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetUserRole,
):
    service = BudgetService(db)
    advances, total = await service.list_advances(employee_id=current_user.id, status=status, page=page, limit=limit)
    items = [BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))) for advance in advances]
    return ApiResponse(success=True, data=PaginatedResponse.create(items, total, page, limit))


@router.get("/{budget_id:int}", response_model=ApiResponse[BudgetResponse])
async def get_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    budget = await service.get_budget_by_id(budget_id)
    return ApiResponse(success=True, data=BudgetResponse(**(await service.get_budget_snapshot(budget))))


@router.get("/{budget_id:int}/closure", response_model=ApiResponse[BudgetClosureStatusResponse])
async def get_budget_closure_status(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    return ApiResponse(success=True, data=BudgetClosureStatusResponse(**(await service.get_budget_closure_status(budget_id))))


@router.get("/{budget_id:int}/my-available-balance", response_model=ApiResponse[MyBudgetAvailableBalanceResponse])
async def get_my_budget_available_balance(
    budget_id: int,
    employee_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetUserRole,
):
    service = BudgetService(db)
    budget = await service.get_budget_by_id(budget_id)
    target_employee_id = current_user.id
    if employee_id is not None and current_user.role in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
        target_employee_id = employee_id
    balance = await service.get_employee_budget_available_total(budget_id, target_employee_id)
    return ApiResponse(
        success=True,
        data=MyBudgetAvailableBalanceResponse(
            budget_id=budget.id,
            budget_number=budget.budget_number,
            budget_name=budget.name,
            available_unreserved_total=balance,
        ),
    )


@router.patch("/{budget_id:int}", response_model=ApiResponse[BudgetResponse])
async def update_budget(
    budget_id: int,
    data: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    budget = await service.update_budget(budget_id, data)
    return ApiResponse(success=True, message="Budget updated", data=BudgetResponse(**(await service.get_budget_snapshot(budget))))


@router.post("/{budget_id:int}/activate", response_model=ApiResponse[BudgetResponse])
async def activate_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    budget = await service.activate_budget(budget_id, current_user.id)
    return ApiResponse(success=True, message="Budget activated", data=BudgetResponse(**(await service.get_budget_snapshot(budget))))


@router.post("/{budget_id:int}/close", response_model=ApiResponse[BudgetResponse])
async def close_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    budget = await service.close_budget(budget_id)
    return ApiResponse(success=True, message="Budget closed", data=BudgetResponse(**(await service.get_budget_snapshot(budget))))


@router.post("/{budget_id:int}/cancel", response_model=ApiResponse[BudgetResponse])
async def cancel_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    budget = await service.cancel_budget(budget_id)
    return ApiResponse(success=True, message="Budget cancelled", data=BudgetResponse(**(await service.get_budget_snapshot(budget))))


@router.post("/advances", response_model=ApiResponse[BudgetAdvanceResponse], status_code=status.HTTP_201_CREATED)
async def create_advance(
    data: BudgetAdvanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    advance = await service.create_advance(data, current_user.id)
    return ApiResponse(success=True, message="Advance created", data=BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))))


@router.get("/advances", response_model=ApiResponse[PaginatedResponse[BudgetAdvanceResponse]])
async def list_advances(
    budget_id: int | None = Query(None),
    employee_id: int | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    advances, total = await service.list_advances(
        budget_id=budget_id, employee_id=employee_id, status=status, page=page, limit=limit
    )
    items = [BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))) for advance in advances]
    return ApiResponse(success=True, data=PaginatedResponse.create(items, total, page, limit))


@router.get("/advances/{advance_id}", response_model=ApiResponse[BudgetAdvanceResponse])
async def get_advance(
    advance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    advance = await service.get_advance_by_id(advance_id)
    return ApiResponse(success=True, data=BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))))


@router.post("/advances/{advance_id}/issue", response_model=ApiResponse[BudgetAdvanceResponse])
async def issue_advance(
    advance_id: int,
    data: BudgetAdvanceIssueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    advance = await service.issue_advance(advance_id, data)
    return ApiResponse(success=True, message="Advance issued", data=BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))))


@router.post("/advances/{advance_id}/cancel", response_model=ApiResponse[BudgetAdvanceResponse])
async def cancel_advance(
    advance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    advance = await service.cancel_advance(advance_id)
    return ApiResponse(success=True, message="Advance cancelled", data=BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))))


@router.post("/advances/{advance_id}/close", response_model=ApiResponse[BudgetAdvanceResponse])
async def close_advance(
    advance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    advance = await service.close_advance(advance_id)
    return ApiResponse(success=True, message="Advance closed", data=BudgetAdvanceResponse(**(await service.get_advance_snapshot(advance))))


@router.post(
    "/advances/{advance_id}/returns",
    response_model=ApiResponse[BudgetAdvanceReturnResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_advance_return(
    advance_id: int,
    data: BudgetAdvanceReturnCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    row = await service.create_return(advance_id, data, current_user.id)
    return ApiResponse(success=True, message="Advance return recorded", data=_return_to_response(row))


@router.get("/advances/{advance_id}/returns", response_model=ApiResponse[list[BudgetAdvanceReturnResponse]])
async def list_advance_returns(
    advance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    rows = await service.list_returns_for_advance(advance_id)
    return ApiResponse(success=True, data=[_return_to_response(row) for row in rows])


@router.post(
    "/advances/{advance_id}/transfer",
    response_model=ApiResponse[BudgetAdvanceTransferResponse],
    status_code=status.HTTP_201_CREATED,
)
async def transfer_advance(
    advance_id: int,
    data: BudgetAdvanceTransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetWriteRole,
):
    service = BudgetService(db)
    row = await service.transfer_advance(advance_id, data, current_user.id)
    return ApiResponse(success=True, message="Advance transferred", data=_transfer_to_response(row))


@router.get("/transfers", response_model=ApiResponse[PaginatedResponse[BudgetAdvanceTransferResponse]])
async def list_transfers(
    budget_id: int | None = Query(None),
    employee_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    rows, total = await service.list_transfers(
        budget_id=budget_id, employee_id=employee_id, page=page, limit=limit
    )
    items = [_transfer_to_response(row) for row in rows]
    return ApiResponse(success=True, data=PaginatedResponse.create(items, total, page, limit))


@router.get("/transfers/{transfer_id}", response_model=ApiResponse[BudgetAdvanceTransferResponse])
async def get_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BudgetReadRole,
):
    service = BudgetService(db)
    row = await service.get_transfer_by_id(transfer_id)
    return ApiResponse(success=True, data=_transfer_to_response(row))
