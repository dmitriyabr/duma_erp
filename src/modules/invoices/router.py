"""API endpoints for Invoices module."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.invoices.models import InvoiceStatus, InvoiceType
from src.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceFilters,
    InvoiceLineCreate,
    InvoiceLineDiscountUpdate,
    InvoiceResponse,
    InvoiceSummary,
    IssueInvoiceRequest,
    TermInvoiceGenerationRequest,
    TermInvoiceGenerationForStudentRequest,
    TermInvoiceGenerationResult,
)
from src.modules.invoices.service import InvoiceService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _invoice_to_response(invoice) -> InvoiceResponse:
    """Convert Invoice model to response schema."""
    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        student_id=invoice.student_id,
        student_name=invoice.student.full_name if invoice.student else None,
        student_number=invoice.student.student_number if invoice.student else None,
        term_id=invoice.term_id,
        term_name=invoice.term.display_name if invoice.term else None,
        invoice_type=invoice.invoice_type,
        status=invoice.status,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        subtotal=float(invoice.subtotal),
        discount_total=float(invoice.discount_total),
        total=float(invoice.total),
        paid_total=float(invoice.paid_total),
        amount_due=float(invoice.amount_due),
        notes=invoice.notes,
        created_by_id=invoice.created_by_id,
        lines=[
            {
                "id": line.id,
                "invoice_id": line.invoice_id,
                "kit_id": line.kit_id,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": float(line.unit_price),
                "line_total": float(line.line_total),
                "discount_amount": float(line.discount_amount),
                "net_amount": float(line.net_amount),
                "paid_amount": float(line.paid_amount),
                "remaining_amount": float(line.remaining_amount),
            }
            for line in invoice.lines
        ],
    )


def _invoice_to_summary(invoice) -> InvoiceSummary:
    """Convert Invoice model to summary schema."""
    return InvoiceSummary(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        student_id=invoice.student_id,
        student_name=invoice.student.full_name if invoice.student else None,
        invoice_type=invoice.invoice_type,
        status=invoice.status,
        total=float(invoice.total),
        paid_total=float(invoice.paid_total),
        amount_due=float(invoice.amount_due),
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
    )


# --- Invoice CRUD ---


@router.post(
    "",
    response_model=ApiResponse[InvoiceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_adhoc_invoice(
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create an ad-hoc invoice (draft). Requires ADMIN role."""
    service = InvoiceService(db)
    invoice = await service.create_adhoc_invoice(data, current_user.id)
    invoice = await service.get_invoice_by_id(invoice.id)
    return ApiResponse(
        success=True,
        message="Invoice created successfully",
        data=_invoice_to_response(invoice),
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[InvoiceSummary]],
)
async def list_invoices(
    student_id: int | None = Query(None),
    term_id: int | None = Query(None),
    invoice_type: InvoiceType | None = Query(None),
    status: InvoiceStatus | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """List invoices with filters."""
    service = InvoiceService(db)
    filters = InvoiceFilters(
        student_id=student_id,
        term_id=term_id,
        invoice_type=invoice_type,
        status=status,
        search=search,
        page=page,
        limit=limit,
    )
    invoices, total = await service.list_invoices(filters)
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_invoice_to_summary(inv) for inv in invoices],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/{invoice_id}",
    response_model=ApiResponse[InvoiceResponse],
)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """Get invoice by ID with all lines."""
    service = InvoiceService(db)
    invoice = await service.get_invoice_by_id(invoice_id)
    return ApiResponse(
        success=True,
        data=_invoice_to_response(invoice),
    )


# --- Invoice Lines ---


@router.post(
    "/{invoice_id}/lines",
    response_model=ApiResponse[InvoiceResponse],
)
async def add_invoice_line(
    invoice_id: int,
    data: InvoiceLineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Add a line to a draft invoice."""
    service = InvoiceService(db)
    invoice = await service.add_line(invoice_id, data, current_user.id)
    return ApiResponse(
        success=True,
        message="Line added successfully",
        data=_invoice_to_response(invoice),
    )


@router.delete(
    "/{invoice_id}/lines/{line_id}",
    response_model=ApiResponse[InvoiceResponse],
)
async def remove_invoice_line(
    invoice_id: int,
    line_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Remove a line from a draft invoice."""
    service = InvoiceService(db)
    invoice = await service.remove_line(invoice_id, line_id, current_user.id)
    return ApiResponse(
        success=True,
        message="Line removed successfully",
        data=_invoice_to_response(invoice),
    )


@router.patch(
    "/{invoice_id}/lines/{line_id}/discount",
    response_model=ApiResponse[InvoiceResponse],
)
async def update_line_discount(
    invoice_id: int,
    line_id: int,
    data: InvoiceLineDiscountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Update discount on a specific line."""
    service = InvoiceService(db)
    invoice = await service.update_line_discount(
        invoice_id, line_id, data.discount_amount, current_user.id
    )
    invoice = await service.get_invoice_by_id(invoice.id)
    return ApiResponse(
        success=True,
        message="Discount updated successfully",
        data=_invoice_to_response(invoice),
    )


# --- Invoice Lifecycle ---


@router.post(
    "/{invoice_id}/issue",
    response_model=ApiResponse[InvoiceResponse],
)
async def issue_invoice(
    invoice_id: int,
    data: IssueInvoiceRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Issue a draft invoice."""
    service = InvoiceService(db)
    due_date = data.due_date if data else None
    invoice = await service.issue_invoice(invoice_id, current_user.id, due_date)
    invoice = await service.get_invoice_by_id(invoice.id)
    return ApiResponse(
        success=True,
        message="Invoice issued successfully",
        data=_invoice_to_response(invoice),
    )


@router.post(
    "/{invoice_id}/cancel",
    response_model=ApiResponse[InvoiceResponse],
)
async def cancel_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Cancel an invoice (only if no payments received)."""
    service = InvoiceService(db)
    invoice = await service.cancel_invoice(invoice_id, current_user.id)
    return ApiResponse(
        success=True,
        message="Invoice cancelled successfully",
        data=_invoice_to_response(invoice),
    )


# --- Term Invoice Generation ---


@router.post(
    "/generate-term-invoices",
    response_model=ApiResponse[TermInvoiceGenerationResult],
)
async def generate_term_invoices(
    data: TermInvoiceGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Generate invoices for all active students for a term.

    Creates separate School Fee and Transport invoices.
    Skips students who already have invoices for this term.
    Requires SUPER_ADMIN or ADMIN role.
    """
    service = InvoiceService(db)
    result = await service.generate_term_invoices(data.term_id, current_user.id)
    return ApiResponse(
        success=True,
        message=f"Generated {result.school_fee_invoices_created} school fee and {result.transport_invoices_created} transport invoices",
        data=result,
    )


@router.post(
    "/generate-term-invoices/student",
    response_model=ApiResponse[TermInvoiceGenerationResult],
)
async def generate_term_invoices_for_student(
    data: TermInvoiceGenerationForStudentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Generate term invoices for a single student."""
    service = InvoiceService(db)
    result = await service.generate_term_invoices_for_student(
        data.term_id, data.student_id, current_user.id
    )
    return ApiResponse(
        success=True,
        message=(
            f"Generated {result.school_fee_invoices_created} school fee and "
            f"{result.transport_invoices_created} transport invoices"
        ),
        data=result,
    )
