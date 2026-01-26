"""API endpoints for Inventory module."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.inventory.models import IssuanceType, MovementType, RecipientType, StockMovement
from src.modules.inventory.schemas import (
    AdjustStockRequest,
    InternalIssuanceCreate,
    IssuanceItemResponse,
    IssuanceResponse,
    IssueStockRequest,
    InventoryCountRequest,
    InventoryCountResponse,
    ReceiveStockRequest,
    StockMovementResponse,
    StockResponse,
    WriteOffRequest,
    WriteOffResponse,
)
from src.modules.inventory.service import InventoryService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _movement_to_response(movement: StockMovement) -> StockMovementResponse:
    return StockMovementResponse(
        id=movement.id,
        stock_id=movement.stock_id,
        item_id=movement.item_id,
        item_sku=movement.item.sku_code if movement.item else None,
        item_name=movement.item.name if movement.item else None,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        unit_cost=movement.unit_cost,
        quantity_before=movement.quantity_before,
        quantity_after=movement.quantity_after,
        average_cost_before=movement.average_cost_before,
        average_cost_after=movement.average_cost_after,
        reference_type=movement.reference_type,
        reference_id=movement.reference_id,
        notes=movement.notes,
        created_by_id=movement.created_by_id,
        created_by_name=movement.created_by.full_name if movement.created_by else None,
        created_at=movement.created_at,
    )


# --- Stock Endpoints ---


@router.get(
    "/stock",
    response_model=ApiResponse[PaginatedResponse[StockResponse]],
)
async def list_stock(
    include_zero: bool = Query(False, description="Include items with zero stock"),
    category_id: int | None = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)
    ),
):
    """List all stock items."""
    service = InventoryService(db)
    stocks, total = await service.list_stock(
        include_zero=include_zero,
        category_id=category_id,
        page=page,
        limit=limit,
    )
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[
                StockResponse(
                    id=s.id,
                    item_id=s.item_id,
                    item_sku=s.item.sku_code if s.item else None,
                    item_name=s.item.name if s.item else None,
                    quantity_on_hand=s.quantity_on_hand,
                    quantity_reserved=s.quantity_reserved,
                    quantity_available=s.quantity_available,
                    average_cost=s.average_cost,
                )
                for s in stocks
            ],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/stock/{item_id}",
    response_model=ApiResponse[StockResponse],
)
async def get_stock(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)
    ),
):
    """Get stock for a specific item."""
    service = InventoryService(db)
    stock = await service.get_stock_by_item_id(item_id)
    if not stock:
        return ApiResponse(
            success=True,
            data=StockResponse(
                id=0,
                item_id=item_id,
                item_sku=None,
                item_name=None,
                quantity_on_hand=0,
                quantity_reserved=0,
                quantity_available=0,
                average_cost="0.00",
            ),
        )
    return ApiResponse(
        success=True,
        data=StockResponse(
            id=stock.id,
            item_id=stock.item_id,
            item_sku=stock.item.sku_code if stock.item else None,
            item_name=stock.item.name if stock.item else None,
            quantity_on_hand=stock.quantity_on_hand,
            quantity_reserved=stock.quantity_reserved,
            quantity_available=stock.quantity_available,
            average_cost=stock.average_cost,
        ),
    )


# --- Stock Movement Endpoints ---


@router.post(
    "/receive",
    response_model=ApiResponse[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def receive_stock(
    data: ReceiveStockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Receive stock (incoming goods). Requires ADMIN role."""
    service = InventoryService(db)
    movement = await service.receive_stock(data, current_user.id)

    # Reload with relationships
    movements, _ = await service.get_movements(item_id=movement.item_id, page=1, limit=1)
    movement = movements[0] if movements else movement

    return ApiResponse(
        success=True,
        message="Stock received successfully",
        data=StockMovementResponse(
            id=movement.id,
            stock_id=movement.stock_id,
            item_id=movement.item_id,
            item_sku=movement.item.sku_code if movement.item else None,
            item_name=movement.item.name if movement.item else None,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            unit_cost=movement.unit_cost,
            quantity_before=movement.quantity_before,
            quantity_after=movement.quantity_after,
            average_cost_before=movement.average_cost_before,
            average_cost_after=movement.average_cost_after,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            notes=movement.notes,
            created_by_id=movement.created_by_id,
            created_by_name=movement.created_by.full_name if movement.created_by else None,
            created_at=movement.created_at,
        ),
    )


@router.post(
    "/adjust",
    response_model=ApiResponse[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def adjust_stock(
    data: AdjustStockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Adjust stock (correction, write-off). Requires SUPER_ADMIN role."""
    service = InventoryService(db)
    movement = await service.adjust_stock(data, current_user.id)

    # Reload with relationships
    movements, _ = await service.get_movements(item_id=movement.item_id, page=1, limit=1)
    movement = movements[0] if movements else movement

    return ApiResponse(
        success=True,
        message="Stock adjusted successfully",
        data=StockMovementResponse(
            id=movement.id,
            stock_id=movement.stock_id,
            item_id=movement.item_id,
            item_sku=movement.item.sku_code if movement.item else None,
            item_name=movement.item.name if movement.item else None,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            unit_cost=movement.unit_cost,
            quantity_before=movement.quantity_before,
            quantity_after=movement.quantity_after,
            average_cost_before=movement.average_cost_before,
            average_cost_after=movement.average_cost_after,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            notes=movement.notes,
            created_by_id=movement.created_by_id,
            created_by_name=movement.created_by.full_name if movement.created_by else None,
            created_at=movement.created_at,
        ),
    )


@router.post(
    "/writeoff",
    response_model=ApiResponse[WriteOffResponse],
    status_code=status.HTTP_201_CREATED,
)
async def write_off_items(
    data: WriteOffRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Write off items with reasons. Requires ADMIN role."""
    service = InventoryService(db)
    movements = await service.write_off_items(data.items, current_user.id)
    movement_ids = [m.id for m in movements]
    movements = await service.get_movements_by_ids(movement_ids)

    return ApiResponse(
        success=True,
        message="Write-off completed",
        data=WriteOffResponse(
            movements=[_movement_to_response(m) for m in movements],
            total=len(movements),
        ),
    )


@router.post(
    "/inventory-count",
    response_model=ApiResponse[InventoryCountResponse],
    status_code=status.HTTP_201_CREATED,
)
async def inventory_count(
    data: InventoryCountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Apply inventory count (bulk adjustment). Requires ADMIN role."""
    service = InventoryService(db)
    movements = await service.bulk_inventory_adjustment(data.items, current_user.id)
    movement_ids = [m.id for m in movements]
    movements = await service.get_movements_by_ids(movement_ids)
    total_variance = sum(m.quantity for m in movements)

    return ApiResponse(
        success=True,
        message="Inventory count applied",
        data=InventoryCountResponse(
            movements=[_movement_to_response(m) for m in movements],
            adjustments_created=len(movements),
            total_variance=total_variance,
        ),
    )


@router.post(
    "/issue",
    response_model=ApiResponse[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def issue_stock(
    data: IssueStockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Issue stock manually (without reservation). Requires ADMIN role."""
    service = InventoryService(db)
    movement = await service.issue_stock(data, current_user.id)

    # Reload with relationships
    movements, _ = await service.get_movements(item_id=movement.item_id, page=1, limit=1)
    movement = movements[0] if movements else movement

    return ApiResponse(
        success=True,
        message="Stock issued successfully",
        data=StockMovementResponse(
            id=movement.id,
            stock_id=movement.stock_id,
            item_id=movement.item_id,
            item_sku=movement.item.sku_code if movement.item else None,
            item_name=movement.item.name if movement.item else None,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            unit_cost=movement.unit_cost,
            quantity_before=movement.quantity_before,
            quantity_after=movement.quantity_after,
            average_cost_before=movement.average_cost_before,
            average_cost_after=movement.average_cost_after,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            notes=movement.notes,
            created_by_id=movement.created_by_id,
            created_by_name=movement.created_by.full_name if movement.created_by else None,
            created_at=movement.created_at,
        ),
    )


@router.get(
    "/movements",
    response_model=ApiResponse[PaginatedResponse[StockMovementResponse]],
)
async def list_movements(
    item_id: int | None = Query(None, description="Filter by item"),
    movement_type: str | None = Query(None, description="Filter by movement type"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """List stock movements with optional filters."""
    service = InventoryService(db)

    type_filter = MovementType(movement_type) if movement_type else None

    movements, total = await service.get_movements(
        item_id=item_id,
        movement_type=type_filter,
        page=page,
        limit=limit,
    )

    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[
                StockMovementResponse(
                    id=m.id,
                    stock_id=m.stock_id,
                    item_id=m.item_id,
                    item_sku=m.item.sku_code if m.item else None,
                    item_name=m.item.name if m.item else None,
                    movement_type=m.movement_type,
                    quantity=m.quantity,
                    unit_cost=m.unit_cost,
                    quantity_before=m.quantity_before,
                    quantity_after=m.quantity_after,
                    average_cost_before=m.average_cost_before,
                    average_cost_after=m.average_cost_after,
                    reference_type=m.reference_type,
                    reference_id=m.reference_id,
                    notes=m.notes,
                    created_by_id=m.created_by_id,
                    created_by_name=m.created_by.full_name if m.created_by else None,
                    created_at=m.created_at,
                )
                for m in movements
            ],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/movements/{item_id}",
    response_model=ApiResponse[PaginatedResponse[StockMovementResponse]],
)
async def get_item_movements(
    item_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)
    ),
):
    """Get stock movements for a specific item."""
    service = InventoryService(db)

    movements, total = await service.get_movements(
        item_id=item_id,
        page=page,
        limit=limit,
    )

    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[
                StockMovementResponse(
                    id=m.id,
                    stock_id=m.stock_id,
                    item_id=m.item_id,
                    item_sku=m.item.sku_code if m.item else None,
                    item_name=m.item.name if m.item else None,
                    movement_type=m.movement_type,
                    quantity=m.quantity,
                    unit_cost=m.unit_cost,
                    quantity_before=m.quantity_before,
                    quantity_after=m.quantity_after,
                    average_cost_before=m.average_cost_before,
                    average_cost_after=m.average_cost_after,
                    reference_type=m.reference_type,
                    reference_id=m.reference_id,
                    notes=m.notes,
                    created_by_id=m.created_by_id,
                    created_by_name=m.created_by.full_name if m.created_by else None,
                    created_at=m.created_at,
                )
                for m in movements
            ],
            total=total,
            page=page,
            limit=limit,
        ),
    )


# --- Issuance Endpoints ---


def _issuance_to_response(issuance) -> IssuanceResponse:
    """Helper to convert Issuance to response."""
    return IssuanceResponse(
        id=issuance.id,
        issuance_number=issuance.issuance_number,
        issuance_type=issuance.issuance_type,
        recipient_type=issuance.recipient_type,
        recipient_id=issuance.recipient_id,
        recipient_name=issuance.recipient_name,
        reservation_id=issuance.reservation_id,
        issued_by_id=issuance.issued_by_id,
        issued_by_name=issuance.issued_by.full_name if issuance.issued_by else None,
        issued_at=issuance.issued_at,
        notes=issuance.notes,
        status=issuance.status,
        items=[
            IssuanceItemResponse(
                id=item.id,
                item_id=item.item_id,
                item_sku=item.item.sku_code if item.item else None,
                item_name=item.item.name if item.item else None,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
            )
            for item in issuance.items
        ],
    )


@router.post(
    "/issuances",
    response_model=ApiResponse[IssuanceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_internal_issuance(
    data: InternalIssuanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create an internal issuance (to employee, department, etc.). Requires ADMIN role."""
    service = InventoryService(db)
    issuance = await service.create_internal_issuance(data, current_user.id)
    issuance = await service.get_issuance_by_id(issuance.id)

    return ApiResponse(
        success=True,
        message="Issuance created successfully",
        data=_issuance_to_response(issuance),
    )


@router.get(
    "/issuances",
    response_model=ApiResponse[PaginatedResponse[IssuanceResponse]],
)
async def list_issuances(
    issuance_type: str | None = Query(None, description="Filter by issuance type"),
    recipient_type: str | None = Query(None, description="Filter by recipient type"),
    recipient_id: int | None = Query(None, description="Filter by recipient ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """List issuances with optional filters."""
    service = InventoryService(db)

    type_filter = IssuanceType(issuance_type) if issuance_type else None
    recipient_filter = RecipientType(recipient_type) if recipient_type else None

    issuances, total = await service.list_issuances(
        issuance_type=type_filter,
        recipient_type=recipient_filter,
        recipient_id=recipient_id,
        page=page,
        limit=limit,
    )

    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_issuance_to_response(i) for i in issuances],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/issuances/{issuance_id}",
    response_model=ApiResponse[IssuanceResponse],
)
async def get_issuance(
    issuance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)
    ),
):
    """Get issuance by ID."""
    service = InventoryService(db)
    issuance = await service.get_issuance_by_id(issuance_id)

    return ApiResponse(
        success=True,
        data=_issuance_to_response(issuance),
    )


@router.post(
    "/issuances/{issuance_id}/cancel",
    response_model=ApiResponse[IssuanceResponse],
)
async def cancel_issuance(
    issuance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Cancel an issuance and return stock. Requires SUPER_ADMIN role."""
    service = InventoryService(db)
    issuance = await service.cancel_issuance(issuance_id, current_user.id)
    issuance = await service.get_issuance_by_id(issuance.id)

    return ApiResponse(
        success=True,
        message="Issuance cancelled successfully",
        data=_issuance_to_response(issuance),
    )
