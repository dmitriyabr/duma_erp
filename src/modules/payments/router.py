"""API endpoints for Payments module."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.attachments.service import get_attachment, get_attachment_content
from src.core.auth.dependencies import require_roles
from src.core.pdf import build_receipt_context, image_to_data_uri, pdf_service
from src.core.school_settings.service import get_school_settings
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.payments.models import PaymentMethod, PaymentStatus
from src.modules.payments.schemas import (
    AllocationCreate,
    AllocationResponse,
    AutoAllocateRequest,
    AutoAllocateResult,
    PaymentCreate,
    PaymentFilters,
    PaymentResponse,
    PaymentUpdate,
    StatementResponse,
    StudentBalance,
    StudentBalancesBatchRequest,
    StudentBalancesBatchResponse,
)
from src.modules.invoices.service import InvoiceService
from src.modules.payments.service import PaymentService
from src.shared.schemas.base import ApiResponse, PaginatedResponse
from src.shared.utils.money import round_money

router = APIRouter(prefix="/payments", tags=["Payments"])


# --- Payment Endpoints ---


@router.post(
    "",
    response_model=ApiResponse[PaymentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create a new payment (credit top-up). Accountant is read-only."""
    service = PaymentService(db)
    payment = await service.create_payment(data, current_user.id)
    return ApiResponse(
        data=PaymentResponse.model_validate(payment),
        message="Payment created successfully",
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[PaymentResponse]],
)
async def list_payments(
    student_id: int | None = Query(None),
    status: PaymentStatus | None = Query(None),
    payment_method: PaymentMethod | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER)
    ),
):
    """List payments with optional filters."""
    service = PaymentService(db)
    filters = PaymentFilters(
        student_id=student_id,
        status=status,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    payments, total = await service.list_payments(filters)
    return ApiResponse(
        data=PaginatedResponse.create(
            items=[PaymentResponse.model_validate(p) for p in payments],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/{payment_id}",
    response_model=ApiResponse[PaymentResponse],
)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER)
    ),
):
    """Get payment by ID."""
    service = PaymentService(db)
    payment = await service.get_payment_by_id(payment_id)
    return ApiResponse(data=PaymentResponse.model_validate(payment))


@router.get("/{payment_id}/receipt/pdf")
async def download_receipt_pdf(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER)
    ),
):
    """Download payment receipt as PDF (completed payments only)."""
    service = PaymentService(db)
    payment = await service.get_payment_by_id(payment_id)
    if payment.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt is only available for completed payments",
        )
    school_settings = await get_school_settings(db)
    logo_data_uri = None
    stamp_data_uri = None
    if school_settings.logo_attachment_id:
        att = await get_attachment(db, school_settings.logo_attachment_id)
        if att:
            try:
                content = await get_attachment_content(att)
                logo_data_uri = image_to_data_uri(content, att.content_type)
            except Exception:
                pass
    if school_settings.stamp_attachment_id:
        att = await get_attachment(db, school_settings.stamp_attachment_id)
        if att:
            try:
                content = await get_attachment_content(att)
                stamp_data_uri = image_to_data_uri(content, att.content_type)
            except Exception:
                pass

    context = build_receipt_context(
        payment, school_settings,
        logo_data_uri, stamp_data_uri,
    )
    pdf_bytes = pdf_service.generate_receipt_pdf(context)
    filename = f"receipt_{payment.receipt_number or payment.payment_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch(
    "/{payment_id}",
    response_model=ApiResponse[PaymentResponse],
)
async def update_payment(
    payment_id: int,
    data: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Update a pending payment. Accountant is read-only."""
    service = PaymentService(db)
    payment = await service.update_payment(payment_id, data, current_user.id)
    return ApiResponse(
        data=PaymentResponse.model_validate(payment),
        message="Payment updated successfully",
    )


@router.post(
    "/{payment_id}/complete",
    response_model=ApiResponse[PaymentResponse],
)
async def complete_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Complete a pending payment (generates receipt number). Accountant is read-only."""
    service = PaymentService(db)
    payment = await service.complete_payment(payment_id, current_user.id)
    return ApiResponse(
        data=PaymentResponse.model_validate(payment),
        message=f"Payment completed. Receipt: {payment.receipt_number}",
    )


@router.post(
    "/{payment_id}/cancel",
    response_model=ApiResponse[PaymentResponse],
)
async def cancel_payment(
    payment_id: int,
    reason: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Cancel a pending payment."""
    service = PaymentService(db)
    payment = await service.cancel_payment(payment_id, current_user.id, reason)
    return ApiResponse(
        data=PaymentResponse.model_validate(payment),
        message="Payment cancelled",
    )


# --- Balance & Statement Endpoints ---


@router.post(
    "/students/balances-batch",
    response_model=ApiResponse[StudentBalancesBatchResponse],
)
async def get_student_balances_batch(
    payload: StudentBalancesBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER)
    ),
):
    """Get credit balances, outstanding debt, and net balance for multiple students."""
    payment_service = PaymentService(db)
    invoice_service = InvoiceService(db)
    balances = await payment_service.get_student_balances_batch(payload.student_ids)
    totals = await invoice_service.get_outstanding_totals(payload.student_ids)
    debt_by_student = {t.student_id: t.total_due for t in totals}
    merged = [
        StudentBalance(
            student_id=b.student_id,
            total_payments=b.total_payments,
            total_allocated=b.total_allocated,
            available_balance=b.available_balance,
            outstanding_debt=debt_by_student.get(b.student_id, b.outstanding_debt),
            balance=round_money(b.available_balance - debt_by_student.get(b.student_id, b.outstanding_debt)),
        )
        for b in balances
    ]
    return ApiResponse(data=StudentBalancesBatchResponse(balances=merged))


@router.get(
    "/students/{student_id}/balance",
    response_model=ApiResponse[StudentBalance],
)
async def get_student_balance(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER)
    ),
):
    """Get student's credit balance, outstanding debt, and net balance."""
    payment_service = PaymentService(db)
    invoice_service = InvoiceService(db)
    balance = await payment_service.get_student_balance(student_id)
    totals = await invoice_service.get_outstanding_totals([student_id])
    total_due = totals[0].total_due if totals else balance.outstanding_debt
    merged = StudentBalance(
        student_id=balance.student_id,
        total_payments=balance.total_payments,
        total_allocated=balance.total_allocated,
        available_balance=balance.available_balance,
        outstanding_debt=total_due,
        balance=round_money(balance.available_balance - total_due),
    )
    return ApiResponse(data=merged)


@router.get(
    "/students/{student_id}/statement",
    response_model=ApiResponse[StatementResponse],
)
async def get_student_statement(
    student_id: int,
    date_from: date = Query(..., description="Statement start date"),
    date_to: date = Query(..., description="Statement end date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER)
    ),
):
    """Get student account statement."""
    service = PaymentService(db)
    statement = await service.get_statement(student_id, date_from, date_to)
    return ApiResponse(data=statement)


# --- Allocation Endpoints ---


@router.post(
    "/allocations/auto",
    response_model=ApiResponse[AutoAllocateResult],
)
async def auto_allocate(
    data: AutoAllocateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Auto-allocate credit to invoices. Accountant is read-only."""
    service = PaymentService(db)
    result = await service.allocate_auto(data, current_user.id)
    return ApiResponse(
        data=result,
        message=f"Allocated {result.total_allocated} to {result.invoices_fully_paid + result.invoices_partially_paid} invoices",
    )


@router.post(
    "/allocations/manual",
    response_model=ApiResponse[AllocationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def manual_allocate(
    data: AllocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Manually allocate credit to an invoice. Accountant is read-only."""
    service = PaymentService(db)
    allocation = await service.allocate_manual(data, current_user.id)
    return ApiResponse(
        data=AllocationResponse.model_validate(allocation),
        message="Credit allocated successfully",
    )


@router.delete(
    "/allocations/{allocation_id}",
    response_model=ApiResponse[None],
)
async def delete_allocation(
    allocation_id: int,
    reason: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Delete an allocation (return credit to balance)."""
    service = PaymentService(db)
    await service.delete_allocation(allocation_id, current_user.id, reason)
    return ApiResponse(data=None, message="Allocation deleted, credit returned to balance")
