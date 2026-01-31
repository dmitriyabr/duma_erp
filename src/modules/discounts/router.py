"""API endpoints for Discounts module."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.discounts.models import Discount
from src.modules.discounts.schemas import (
    DiscountApply,
    DiscountReasonCreate,
    DiscountReasonResponse,
    DiscountReasonUpdate,
    DiscountResponse,
    StudentDiscountCreate,
    StudentDiscountResponse,
    StudentDiscountUpdate,
)
from src.modules.discounts.service import DiscountService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/discounts", tags=["Discounts"])


# --- Discount Reason Endpoints ---


@router.post(
    "/reasons",
    response_model=ApiResponse[DiscountReasonResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_reason(
    data: DiscountReasonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create a new discount reason. Requires SUPER_ADMIN role."""
    service = DiscountService(db)
    reason = await service.create_reason(data, current_user.id)
    return ApiResponse(
        success=True,
        message="Discount reason created successfully",
        data=DiscountReasonResponse.model_validate(reason),
    )


@router.get(
    "/reasons",
    response_model=ApiResponse[list[DiscountReasonResponse]],
)
async def list_reasons(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """List all discount reasons."""
    service = DiscountService(db)
    reasons = await service.list_reasons(include_inactive=include_inactive)
    return ApiResponse(
        success=True,
        data=[DiscountReasonResponse.model_validate(r) for r in reasons],
    )


@router.get(
    "/reasons/{reason_id}",
    response_model=ApiResponse[DiscountReasonResponse],
)
async def get_reason(
    reason_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """Get discount reason by ID."""
    service = DiscountService(db)
    reason = await service.get_reason_by_id(reason_id)
    return ApiResponse(
        success=True,
        data=DiscountReasonResponse.model_validate(reason),
    )


@router.patch(
    "/reasons/{reason_id}",
    response_model=ApiResponse[DiscountReasonResponse],
)
async def update_reason(
    reason_id: int,
    data: DiscountReasonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Update a discount reason. Requires SUPER_ADMIN role."""
    service = DiscountService(db)
    reason = await service.update_reason(reason_id, data, current_user.id)
    return ApiResponse(
        success=True,
        message="Discount reason updated successfully",
        data=DiscountReasonResponse.model_validate(reason),
    )


# --- Discount Endpoints (applied to invoice line) ---


def _discount_to_response(discount) -> DiscountResponse:
    """Convert Discount to response."""
    return DiscountResponse(
        id=discount.id,
        invoice_line_id=discount.invoice_line_id,
        value_type=discount.value_type,
        value=discount.value,
        calculated_amount=discount.calculated_amount,
        reason_id=discount.reason_id,
        reason_name=discount.reason.name if discount.reason else None,
        reason_text=discount.reason_text,
        student_discount_id=discount.student_discount_id,
        applied_by_id=discount.applied_by_id,
    )


@router.post(
    "/apply",
    response_model=ApiResponse[DiscountResponse],
    status_code=status.HTTP_201_CREATED,
)
async def apply_discount(
    data: DiscountApply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Apply a discount to an invoice line."""
    service = DiscountService(db)
    discount = await service.apply_discount(data, current_user.id)
    # Reload to get reason relationship
    result = await db.execute(
        select(Discount)
        .where(Discount.id == discount.id)
        .options(selectinload(Discount.reason))
    )
    discount = result.scalar_one()
    return ApiResponse(
        success=True,
        message="Discount applied successfully",
        data=_discount_to_response(discount),
    )


@router.delete(
    "/{discount_id}",
    response_model=ApiResponse[None],
)
async def remove_discount(
    discount_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Remove a discount from an invoice line."""
    service = DiscountService(db)
    await service.remove_discount(discount_id, current_user.id)
    return ApiResponse(
        success=True,
        message="Discount removed successfully",
        data=None,
    )


@router.get(
    "/line/{invoice_line_id}",
    response_model=ApiResponse[list[DiscountResponse]],
)
async def get_line_discounts(
    invoice_line_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """Get all discounts applied to an invoice line."""
    service = DiscountService(db)
    discounts = await service.get_line_discounts(invoice_line_id)
    return ApiResponse(
        success=True,
        data=[_discount_to_response(d) for d in discounts],
    )


# --- Student Discount Endpoints (standing discount) ---


def _student_discount_to_response(discount) -> StudentDiscountResponse:
    """Convert StudentDiscount to response."""
    return StudentDiscountResponse(
        id=discount.id,
        student_id=discount.student_id,
        student_name=discount.student.full_name if discount.student else None,
        applies_to=discount.applies_to,
        value_type=discount.value_type,
        value=discount.value,
        reason_id=discount.reason_id,
        reason_name=discount.reason.name if discount.reason else None,
        reason_text=discount.reason_text,
        is_active=discount.is_active,
        created_by_id=discount.created_by_id,
    )


@router.post(
    "/student",
    response_model=ApiResponse[StudentDiscountResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_student_discount(
    data: StudentDiscountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create a standing discount for a student."""
    service = DiscountService(db)
    discount = await service.create_student_discount(data, current_user.id)
    discount = await service.get_student_discount_by_id(discount.id)
    return ApiResponse(
        success=True,
        message="Student discount created successfully",
        data=_student_discount_to_response(discount),
    )


@router.get(
    "/student",
    response_model=ApiResponse[PaginatedResponse[StudentDiscountResponse]],
)
async def list_student_discounts(
    student_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """List student discounts (read-only for Accountant)."""
    service = DiscountService(db)
    discounts, total = await service.list_student_discounts(
        student_id=student_id,
        include_inactive=include_inactive,
        page=page,
        limit=limit,
    )
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_student_discount_to_response(d) for d in discounts],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/student/{discount_id}",
    response_model=ApiResponse[StudentDiscountResponse],
)
async def get_student_discount(
    discount_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """Get student discount by ID."""
    service = DiscountService(db)
    discount = await service.get_student_discount_by_id(discount_id)
    return ApiResponse(
        success=True,
        data=_student_discount_to_response(discount),
    )


@router.patch(
    "/student/{discount_id}",
    response_model=ApiResponse[StudentDiscountResponse],
)
async def update_student_discount(
    discount_id: int,
    data: StudentDiscountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Update a student discount."""
    service = DiscountService(db)
    discount = await service.update_student_discount(discount_id, data, current_user.id)
    discount = await service.get_student_discount_by_id(discount.id)
    return ApiResponse(
        success=True,
        message="Student discount updated successfully",
        data=_student_discount_to_response(discount),
    )
