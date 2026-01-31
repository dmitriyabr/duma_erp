"""API endpoints for Procurement (Purchase Orders)."""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.procurement.schemas import (
    BulkUploadPOError,
    CancelPurchaseOrderRequest,
    ParsePOLinesResponse,
    ParsedPOLine,
    GoodsReceivedFilters,
    GoodsReceivedNoteCreate,
    GoodsReceivedNoteResponse,
    PaymentPurposeCreate,
    PaymentPurposeResponse,
    PaymentPurposeUpdate,
    ProcurementDashboardResponse,
    PurchaseOrderCreate,
    PurchaseOrderFilters,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    ProcurementPaymentCreate,
    ProcurementPaymentFilters,
    ProcurementPaymentResponse,
    CancelProcurementPaymentRequest,
)
from src.modules.items.models import Item, ItemType
from src.modules.procurement.service import (
    GoodsReceivedService,
    PaymentPurposeService,
    ProcurementDashboardService,
    ProcurementPaymentService,
    PurchaseOrderService,
)
from src.shared.schemas.base import ApiResponse, PaginatedResponse
from sqlalchemy import select


router = APIRouter(prefix="/procurement", tags=["Procurement"])


def _po_to_response(po) -> PurchaseOrderResponse:
    forecast_debt = po.expected_total - po.paid_total
    return PurchaseOrderResponse(
        id=po.id,
        po_number=po.po_number,
        supplier_name=po.supplier_name,
        supplier_contact=po.supplier_contact,
        purpose_id=po.purpose_id,
        status=po.status,
        order_date=po.order_date,
        expected_delivery_date=po.expected_delivery_date,
        track_to_warehouse=po.track_to_warehouse,
        expected_total=po.expected_total,
        received_value=po.received_value,
        paid_total=po.paid_total,
        debt_amount=po.debt_amount,
        forecast_debt=forecast_debt,
        notes=po.notes,
        cancelled_reason=po.cancelled_reason,
        created_by_id=po.created_by_id,
        created_at=po.created_at,
        updated_at=po.updated_at,
        lines=[
            {
                "id": line.id,
                "item_id": line.item_id,
                "description": line.description,
                "quantity_expected": line.quantity_expected,
                "quantity_cancelled": line.quantity_cancelled,
                "quantity_received": line.quantity_received,
                "unit_price": line.unit_price,
                "line_total": line.line_total,
                "line_order": line.line_order,
            }
            for line in po.lines
        ],
    )


def _purpose_to_response(purpose) -> PaymentPurposeResponse:
    return PaymentPurposeResponse.model_validate(purpose)


def _payment_to_response(payment) -> ProcurementPaymentResponse:
    return ProcurementPaymentResponse(
        id=payment.id,
        payment_number=payment.payment_number,
        po_id=payment.po_id,
        purpose_id=payment.purpose_id,
        payee_name=payment.payee_name,
        payment_date=payment.payment_date,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference_number=payment.reference_number,
        proof_text=payment.proof_text,
        proof_attachment_id=payment.proof_attachment_id,
        company_paid=payment.company_paid,
        employee_paid_id=payment.employee_paid_id,
        status=payment.status,
        cancelled_reason=payment.cancelled_reason,
        cancelled_by_id=payment.cancelled_by_id,
        cancelled_at=payment.cancelled_at,
        created_by_id=payment.created_by_id,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def _grn_to_response(grn) -> GoodsReceivedNoteResponse:
    return GoodsReceivedNoteResponse(
        id=grn.id,
        grn_number=grn.grn_number,
        po_id=grn.po_id,
        status=grn.status,
        received_date=grn.received_date,
        received_by_id=grn.received_by_id,
        approved_by_id=grn.approved_by_id,
        approved_at=grn.approved_at,
        notes=grn.notes,
        created_at=grn.created_at,
        updated_at=grn.updated_at,
        lines=[
            {
                "id": line.id,
                "po_line_id": line.po_line_id,
                "item_id": line.item_id,
                "quantity_received": line.quantity_received,
            }
            for line in grn.lines
        ],
    )


@router.post(
    "/purchase-orders",
    response_model=ApiResponse[PurchaseOrderResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create a purchase order."""
    service = PurchaseOrderService(db)
    po = await service.create_purchase_order(data, current_user.id)
    return ApiResponse(
        success=True,
        message="Purchase order created successfully",
        data=_po_to_response(po),
    )


@router.get(
    "/purchase-orders",
    response_model=ApiResponse[PaginatedResponse[PurchaseOrderResponse]],
)
async def list_purchase_orders(
    status: str | None = Query(None),
    supplier_name: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """List purchase orders with filters."""
    service = PurchaseOrderService(db)
    filters = PurchaseOrderFilters(
        status=status,
        supplier_name=supplier_name,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    pos, total = await service.list_purchase_orders(filters)
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_po_to_response(po) for po in pos],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get("/purchase-orders/bulk-upload/template")
async def get_po_bulk_upload_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """Download CSV template for PO lines. One example row + all product items (sku, name only)."""
    import csv
    import io

    headers = ["sku", "item_name", "quantity_expected", "unit_price"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerow(["EXAMPLE-001", "Example product", "1", "0.00"])
    result = await db.execute(
        select(Item.sku_code, Item.name)
        .where(Item.item_type == ItemType.PRODUCT.value)
        .where(Item.is_active.is_(True))
        .order_by(Item.sku_code)
    )
    for row in result.all():
        writer.writerow([row.sku_code, row.name, "", ""])
    body = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=po_lines_template.csv"},
    )


@router.post(
    "/purchase-orders/bulk-upload/parse-lines",
    response_model=ApiResponse[ParsePOLinesResponse],
)
async def parse_po_lines_from_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Parse CSV into PO lines only (no PO created). For use on create-PO form."""
    content = await file.read()
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="CSV file is empty")
    service = PurchaseOrderService(db)
    result = await service.parse_po_lines_from_csv(content)
    return ApiResponse(
        success=True,
        data=ParsePOLinesResponse(
            lines=[ParsedPOLine(**line) for line in result["lines"]],
            errors=[BulkUploadPOError(row=e["row"], message=e["message"]) for e in result["errors"]],
        ),
    )


@router.get(
    "/purchase-orders/{po_id}",
    response_model=ApiResponse[PurchaseOrderResponse],
)
async def get_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """Get purchase order by ID."""
    service = PurchaseOrderService(db)
    po = await service.get_purchase_order_by_id(po_id)
    return ApiResponse(success=True, data=_po_to_response(po))


@router.put(
    "/purchase-orders/{po_id}",
    response_model=ApiResponse[PurchaseOrderResponse],
)
async def update_purchase_order(
    po_id: int,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Update a purchase order."""
    service = PurchaseOrderService(db)
    po = await service.update_purchase_order(po_id, data)
    return ApiResponse(
        success=True,
        message="Purchase order updated successfully",
        data=_po_to_response(po),
    )


@router.post(
    "/purchase-orders/{po_id}/submit",
    response_model=ApiResponse[PurchaseOrderResponse],
)
async def submit_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Submit purchase order to supplier (mark ordered)."""
    service = PurchaseOrderService(db)
    po = await service.submit_purchase_order(po_id)
    return ApiResponse(
        success=True,
        message="Purchase order submitted successfully",
        data=_po_to_response(po),
    )


@router.post(
    "/purchase-orders/{po_id}/close",
    response_model=ApiResponse[PurchaseOrderResponse],
)
async def close_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Close purchase order and cancel remaining quantities."""
    service = PurchaseOrderService(db)
    po = await service.close_purchase_order(po_id)
    return ApiResponse(
        success=True,
        message="Purchase order closed successfully",
        data=_po_to_response(po),
    )


@router.post(
    "/purchase-orders/{po_id}/cancel",
    response_model=ApiResponse[PurchaseOrderResponse],
)
async def cancel_purchase_order(
    po_id: int,
    data: CancelPurchaseOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Cancel purchase order."""
    service = PurchaseOrderService(db)
    po = await service.cancel_purchase_order(po_id, data.reason)
    return ApiResponse(
        success=True,
        message="Purchase order cancelled successfully",
        data=_po_to_response(po),
    )


@router.post(
    "/grns",
    response_model=ApiResponse[GoodsReceivedNoteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_grn(
    data: GoodsReceivedNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Create a GRN (draft)."""
    service = GoodsReceivedService(db)
    grn = await service.create_grn(data, current_user.id)
    return ApiResponse(
        success=True,
        message="GRN created successfully",
        data=_grn_to_response(grn),
    )


@router.get(
    "/grns",
    response_model=ApiResponse[PaginatedResponse[GoodsReceivedNoteResponse]],
)
async def list_grns(
    po_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """List GRNs with filters."""
    service = GoodsReceivedService(db)
    filters = GoodsReceivedFilters(
        po_id=po_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    grns, total = await service.list_grns(filters)
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_grn_to_response(grn) for grn in grns],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/grns/{grn_id}",
    response_model=ApiResponse[GoodsReceivedNoteResponse],
)
async def get_grn(
    grn_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """Get GRN by ID."""
    service = GoodsReceivedService(db)
    grn = await service.get_grn_by_id(grn_id)
    return ApiResponse(success=True, data=_grn_to_response(grn))


@router.post(
    "/grns/{grn_id}/approve",
    response_model=ApiResponse[GoodsReceivedNoteResponse],
)
async def approve_grn(
    grn_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Approve a GRN."""
    service = GoodsReceivedService(db)
    allow_self_approve = current_user.role == UserRole.SUPER_ADMIN
    grn = await service.approve_grn(grn_id, current_user.id, allow_self_approve)
    return ApiResponse(
        success=True,
        message="GRN approved successfully",
        data=_grn_to_response(grn),
    )


@router.post(
    "/grns/{grn_id}/cancel",
    response_model=ApiResponse[GoodsReceivedNoteResponse],
)
async def cancel_grn(
    grn_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Cancel a draft GRN."""
    service = GoodsReceivedService(db)
    grn = await service.cancel_grn(grn_id)
    return ApiResponse(
        success=True,
        message="GRN cancelled successfully",
        data=_grn_to_response(grn),
    )


@router.post(
    "/payment-purposes",
    response_model=ApiResponse[PaymentPurposeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_purpose(
    data: PaymentPurposeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create a payment purpose (SUPER_ADMIN)."""
    service = PaymentPurposeService(db)
    purpose = await service.create_purpose(data)
    return ApiResponse(
        success=True,
        message="Payment purpose created successfully",
        data=_purpose_to_response(purpose),
    )


@router.get(
    "/payment-purposes",
    response_model=ApiResponse[list[PaymentPurposeResponse]],
)
async def list_payment_purposes(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """List payment purposes."""
    service = PaymentPurposeService(db)
    purposes = await service.list_purposes(include_inactive=include_inactive)
    return ApiResponse(success=True, data=[_purpose_to_response(p) for p in purposes])


@router.put(
    "/payment-purposes/{purpose_id}",
    response_model=ApiResponse[PaymentPurposeResponse],
)
async def update_payment_purpose(
    purpose_id: int,
    data: PaymentPurposeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Update a payment purpose (SUPER_ADMIN)."""
    service = PaymentPurposeService(db)
    purpose = await service.update_purpose(purpose_id, data)
    return ApiResponse(
        success=True,
        message="Payment purpose updated successfully",
        data=_purpose_to_response(purpose),
    )


@router.post(
    "/payments",
    response_model=ApiResponse[ProcurementPaymentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_procurement_payment(
    data: ProcurementPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create procurement payment."""
    service = ProcurementPaymentService(db)
    payment = await service.create_payment(data, current_user.id)
    return ApiResponse(
        success=True,
        message="Payment created successfully",
        data=_payment_to_response(payment),
    )


@router.get(
    "/payments",
    response_model=ApiResponse[PaginatedResponse[ProcurementPaymentResponse]],
)
async def list_procurement_payments(
    po_id: int | None = Query(None),
    purpose_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """List procurement payments."""
    service = ProcurementPaymentService(db)
    filters = ProcurementPaymentFilters(
        po_id=po_id,
        purpose_id=purpose_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    payments, total = await service.list_payments(filters)
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_payment_to_response(p) for p in payments],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/payments/{payment_id}",
    response_model=ApiResponse[ProcurementPaymentResponse],
)
async def get_procurement_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """Get procurement payment by ID."""
    service = ProcurementPaymentService(db)
    payment = await service.get_payment_by_id(payment_id)
    return ApiResponse(success=True, data=_payment_to_response(payment))


@router.post(
    "/payments/{payment_id}/cancel",
    response_model=ApiResponse[ProcurementPaymentResponse],
)
async def cancel_procurement_payment(
    payment_id: int,
    data: CancelProcurementPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Cancel procurement payment."""
    service = ProcurementPaymentService(db)
    payment = await service.cancel_payment(payment_id, data.reason, current_user.id)
    return ApiResponse(
        success=True,
        message="Payment cancelled successfully",
        data=_payment_to_response(payment),
    )


@router.get(
    "/dashboard",
    response_model=ApiResponse[ProcurementDashboardResponse],
)
async def get_procurement_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    """Get procurement dashboard statistics."""
    service = ProcurementDashboardService(db)
    stats = await service.get_dashboard_stats()
    return ApiResponse(
        success=True,
        data=ProcurementDashboardResponse(**stats),
    )
