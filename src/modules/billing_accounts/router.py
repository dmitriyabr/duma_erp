"""API endpoints for shared billing accounts."""

from datetime import date
from decimal import Decimal

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
    BillingAccountTermInvoiceGenerationRequest,
    BillingAccountUpdate,
)
from src.modules.billing_accounts.service import BillingAccountService
from src.modules.invoices.schemas import TermInvoiceGenerationResult
from src.modules.invoices.service import InvoiceService
from src.modules.payments.schemas import (
    AutoAllocateRequest,
    BillingAccountRefundCreate,
    BillingAccountRefundPreview,
    BillingAccountRefundPreviewRequest,
    BillingAccountRefundResponse,
    PaymentRefundSourceResponse,
    RefundAllocationImpact,
    StatementResponse,
)
from src.modules.payments.service import PaymentService
from src.shared.schemas.base import ApiResponse, PaginatedResponse
from src.shared.utils.money import round_money

router = APIRouter(prefix="/billing-accounts", tags=["Billing Accounts"])


def _refund_allocation_impact_to_response(reversal) -> RefundAllocationImpact:
    allocation = reversal.allocation
    invoice = allocation.invoice
    paid_after = round_money(invoice.paid_total)
    due_after = round_money(invoice.amount_due)
    paid_before = round_money(paid_after + reversal.amount)
    due_before = round_money(max(Decimal("0.00"), due_after - reversal.amount))
    return RefundAllocationImpact(
        allocation_id=allocation.id,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        student_id=invoice.student_id,
        student_name=invoice.student.full_name if invoice.student else None,
        current_allocation_amount=allocation.amount,
        reversal_amount=reversal.amount,
        invoice_paid_total_before=paid_before,
        invoice_amount_due_before=due_before,
        invoice_paid_total_after=paid_after,
        invoice_amount_due_after=due_after,
    )


def _billing_account_refund_to_response(refund) -> BillingAccountRefundResponse:
    return BillingAccountRefundResponse(
        id=refund.id,
        refund_number=refund.refund_number,
        payment_id=refund.payment_id,
        billing_account_id=refund.billing_account_id,
        amount=refund.amount,
        refund_date=refund.refund_date,
        refund_method=refund.refund_method,
        reference_number=refund.reference_number,
        proof_text=refund.proof_text,
        proof_attachment_id=refund.proof_attachment_id,
        reason=refund.reason,
        notes=refund.notes,
        refunded_by_id=refund.refunded_by_id,
        created_at=refund.created_at,
        updated_at=refund.updated_at,
        payment_sources=[
            PaymentRefundSourceResponse(
                id=source.id,
                refund_id=source.refund_id,
                payment_id=source.payment_id,
                payment_number=source.payment.payment_number if source.payment else None,
                receipt_number=source.payment.receipt_number if source.payment else None,
                amount=source.amount,
                created_at=source.created_at,
            )
            for source in getattr(refund, "sources", [])
        ],
        allocation_reversals=[
            _refund_allocation_impact_to_response(reversal)
            for reversal in getattr(refund, "allocation_reversals", [])
            if reversal.allocation and reversal.allocation.invoice
        ],
    )


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


@router.post(
    "/{account_id}/generate-term-invoices",
    response_model=ApiResponse[TermInvoiceGenerationResult],
)
async def generate_billing_account_term_invoices(
    account_id: int,
    data: BillingAccountTermInvoiceGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    invoice_service = InvoiceService(db)
    result = await invoice_service.generate_term_invoices_for_billing_account(
        data.term_id, account_id, current_user.id
    )
    if result.affected_student_ids:
        await PaymentService(db).allocate_auto(
            AutoAllocateRequest(billing_account_id=account_id),
            current_user.id,
        )
    return ApiResponse(
        data=result,
        message=(
            f"Generated {result.school_fee_invoices_created} school fee and "
            f"{result.transport_invoices_created} transport invoices"
        ),
    )


@router.post(
    "/{account_id}/refunds/preview",
    response_model=ApiResponse[BillingAccountRefundPreview],
)
async def preview_billing_account_refund(
    account_id: int,
    data: BillingAccountRefundPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    service = PaymentService(db)
    preview = await service.preview_billing_account_refund(account_id, data)
    return ApiResponse(data=preview)


@router.post(
    "/{account_id}/refunds",
    response_model=ApiResponse[BillingAccountRefundResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_billing_account_refund(
    account_id: int,
    data: BillingAccountRefundCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    service = PaymentService(db)
    refund = await service.create_billing_account_refund(account_id, data, current_user.id)
    return ApiResponse(
        data=_billing_account_refund_to_response(refund),
        message="Refund created successfully",
    )


@router.get(
    "/{account_id}/refunds",
    response_model=ApiResponse[list[BillingAccountRefundResponse]],
)
async def list_billing_account_refunds(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = PaymentService(db)
    refunds = await service.list_billing_account_refunds(account_id)
    return ApiResponse(data=[_billing_account_refund_to_response(refund) for refund in refunds])


@router.get(
    "/refunds/{refund_id}",
    response_model=ApiResponse[BillingAccountRefundResponse],
)
async def get_billing_account_refund(
    refund_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = PaymentService(db)
    refund = await service.get_payment_refund_by_id(refund_id)
    return ApiResponse(data=_billing_account_refund_to_response(refund))


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
