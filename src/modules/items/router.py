"""API endpoints for Items module."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.items.models import ItemType
from src.modules.items.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ItemCreate,
    ItemPriceHistoryResponse,
    ItemResponse,
    ItemUpdate,
    KitCreate,
    KitItemResponse,
    KitPriceHistoryResponse,
    KitResponse,
    KitUpdate,
)
from src.modules.items.service import ItemService
from src.shared.schemas.base import ApiResponse

router = APIRouter(prefix="/items", tags=["Items"])


# --- Category Endpoints ---


@router.post(
    "/categories",
    response_model=ApiResponse[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create a new category. Requires SUPER_ADMIN role."""
    service = ItemService(db)
    category = await service.create_category(data, current_user.id)
    return ApiResponse(
        success=True,
        message="Category created successfully",
        data=CategoryResponse.model_validate(category),
    )


@router.get(
    "/categories",
    response_model=ApiResponse[list[CategoryResponse]],
)
async def list_categories(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)),
):
    """List all categories."""
    service = ItemService(db)
    categories = await service.list_categories(include_inactive=include_inactive)
    return ApiResponse(
        success=True,
        data=[CategoryResponse.model_validate(c) for c in categories],
    )


@router.get(
    "/categories/{category_id}",
    response_model=ApiResponse[CategoryResponse],
)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)),
):
    """Get category by ID."""
    service = ItemService(db)
    category = await service.get_category_by_id(category_id)
    return ApiResponse(
        success=True,
        data=CategoryResponse.model_validate(category),
    )


@router.patch(
    "/categories/{category_id}",
    response_model=ApiResponse[CategoryResponse],
)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Update a category. Requires SUPER_ADMIN role."""
    service = ItemService(db)
    category = await service.update_category(category_id, data, current_user.id)
    return ApiResponse(
        success=True,
        message="Category updated successfully",
        data=CategoryResponse.model_validate(category),
    )


# --- Item Endpoints ---


@router.post(
    "",
    response_model=ApiResponse[ItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    data: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create a new item. Requires SUPER_ADMIN role."""
    service = ItemService(db)
    item = await service.create_item(data, current_user.id)
    item = await service.get_item_by_id(item.id, with_category=True)
    return ApiResponse(
        success=True,
        message="Item created successfully",
        data=ItemResponse(
            id=item.id,
            category_id=item.category_id,
            category_name=item.category.name if item.category else None,
            sku_code=item.sku_code,
            name=item.name,
            item_type=item.item_type,
            price_type=item.price_type,
            price=item.price,
            requires_full_payment=item.requires_full_payment,
            is_active=item.is_active,
        ),
    )


@router.get(
    "",
    response_model=ApiResponse[list[ItemResponse]],
)
async def list_items(
    category_id: int | None = None,
    item_type: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)),
):
    """List all items with optional filters."""
    service = ItemService(db)
    type_filter = ItemType(item_type) if item_type else None
    items = await service.list_items(
        category_id=category_id,
        item_type=type_filter,
        include_inactive=include_inactive,
    )
    return ApiResponse(
        success=True,
        data=[
            ItemResponse(
                id=item.id,
                category_id=item.category_id,
                category_name=item.category.name if item.category else None,
                sku_code=item.sku_code,
                name=item.name,
                item_type=item.item_type,
                price_type=item.price_type,
                price=item.price,
                requires_full_payment=item.requires_full_payment,
                is_active=item.is_active,
            )
            for item in items
        ],
    )


# --- Kit Endpoints ---


@router.post(
    "/kits",
    response_model=ApiResponse[KitResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_kit(
    data: KitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create a new kit. Requires SUPER_ADMIN role."""
    service = ItemService(db)
    kit = await service.create_kit(data, current_user.id)
    kit = await service.get_kit_by_id(kit.id, with_items=True)
    return ApiResponse(
        success=True,
        message="Kit created successfully",
        data=KitResponse(
            id=kit.id,
            category_id=kit.category_id,
            category_name=kit.category.name if kit.category else None,
            sku_code=kit.sku_code,
            name=kit.name,
            item_type=kit.item_type,
            price_type=kit.price_type,
            price=kit.price,
            requires_full_payment=kit.requires_full_payment,
            is_active=kit.is_active,
            items=[
                KitItemResponse(
                    id=ki.id,
                    item_id=ki.item_id,
                    item_name=ki.item.name if ki.item else None,
                    item_sku=ki.item.sku_code if ki.item else None,
                    quantity=ki.quantity,
                )
                for ki in kit.kit_items
            ],
        ),
    )


@router.get(
    "/kits",
    response_model=ApiResponse[list[KitResponse]],
)
async def list_kits(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)),
):
    """List all kits."""
    service = ItemService(db)
    kits = await service.list_kits(include_inactive=include_inactive)
    return ApiResponse(
        success=True,
        data=[
            KitResponse(
                id=kit.id,
                category_id=kit.category_id,
                category_name=kit.category.name if kit.category else None,
                sku_code=kit.sku_code,
                name=kit.name,
                item_type=kit.item_type,
                price_type=kit.price_type,
                price=kit.price,
                requires_full_payment=kit.requires_full_payment,
                is_active=kit.is_active,
                items=[
                    KitItemResponse(
                        id=ki.id,
                        item_id=ki.item_id,
                        item_name=ki.item.name if ki.item else None,
                        item_sku=ki.item.sku_code if ki.item else None,
                        quantity=ki.quantity,
                    )
                    for ki in kit.kit_items
                ],
            )
            for kit in kits
        ],
    )


@router.get(
    "/kits/{kit_id}",
    response_model=ApiResponse[KitResponse],
)
async def get_kit(
    kit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)),
):
    """Get kit by ID."""
    service = ItemService(db)
    kit = await service.get_kit_by_id(kit_id, with_items=True)
    return ApiResponse(
        success=True,
        data=KitResponse(
            id=kit.id,
            category_id=kit.category_id,
            category_name=kit.category.name if kit.category else None,
            sku_code=kit.sku_code,
            name=kit.name,
            item_type=kit.item_type,
            price_type=kit.price_type,
            price=kit.price,
            requires_full_payment=kit.requires_full_payment,
            is_active=kit.is_active,
            items=[
                KitItemResponse(
                    id=ki.id,
                    item_id=ki.item_id,
                    item_name=ki.item.name if ki.item else None,
                    item_sku=ki.item.sku_code if ki.item else None,
                    quantity=ki.quantity,
                )
                for ki in kit.kit_items
            ],
        ),
    )


@router.patch(
    "/kits/{kit_id}",
    response_model=ApiResponse[KitResponse],
)
async def update_kit(
    kit_id: int,
    data: KitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Update a kit. Requires SUPER_ADMIN role."""
    service = ItemService(db)
    kit = await service.update_kit(kit_id, data, current_user.id)
    kit = await service.get_kit_by_id(kit.id, with_items=True)
    return ApiResponse(
        success=True,
        message="Kit updated successfully",
        data=KitResponse(
            id=kit.id,
            category_id=kit.category_id,
            category_name=kit.category.name if kit.category else None,
            sku_code=kit.sku_code,
            name=kit.name,
            item_type=kit.item_type,
            price_type=kit.price_type,
            price=kit.price,
            requires_full_payment=kit.requires_full_payment,
            is_active=kit.is_active,
            items=[
                KitItemResponse(
                    id=ki.id,
                    item_id=ki.item_id,
                    item_name=ki.item.name if ki.item else None,
                    item_sku=ki.item.sku_code if ki.item else None,
                    quantity=ki.quantity,
                )
                for ki in kit.kit_items
            ],
        ),
    )


@router.get(
    "/kits/{kit_id}/price-history",
    response_model=ApiResponse[list[KitPriceHistoryResponse]],
)
async def get_kit_price_history(
    kit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)),
):
    """Get price history for a kit."""
    service = ItemService(db)
    history = await service.get_kit_price_history(kit_id)
    return ApiResponse(
        success=True,
        data=[
            KitPriceHistoryResponse(
                id=h.id,
                kit_id=h.kit_id,
                price=h.price,
                effective_from=h.effective_from.isoformat(),
                changed_by_id=h.changed_by_id,
            )
            for h in history
        ],
    )


@router.get(
    "/{item_id}",
    response_model=ApiResponse[ItemResponse],
)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)),
):
    """Get item by ID."""
    service = ItemService(db)
    item = await service.get_item_by_id(item_id, with_category=True)
    return ApiResponse(
        success=True,
        data=ItemResponse(
            id=item.id,
            category_id=item.category_id,
            category_name=item.category.name if item.category else None,
            sku_code=item.sku_code,
            name=item.name,
            item_type=item.item_type,
            price_type=item.price_type,
            price=item.price,
            requires_full_payment=item.requires_full_payment,
            is_active=item.is_active,
        ),
    )


@router.patch(
    "/{item_id}",
    response_model=ApiResponse[ItemResponse],
)
async def update_item(
    item_id: int,
    data: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Update an item. Requires SUPER_ADMIN role."""
    service = ItemService(db)
    item = await service.update_item(item_id, data, current_user.id)
    item = await service.get_item_by_id(item.id, with_category=True)
    return ApiResponse(
        success=True,
        message="Item updated successfully",
        data=ItemResponse(
            id=item.id,
            category_id=item.category_id,
            category_name=item.category.name if item.category else None,
            sku_code=item.sku_code,
            name=item.name,
            item_type=item.item_type,
            price_type=item.price_type,
            price=item.price,
            requires_full_payment=item.requires_full_payment,
            is_active=item.is_active,
        ),
    )


@router.get(
    "/{item_id}/price-history",
    response_model=ApiResponse[list[ItemPriceHistoryResponse]],
)
async def get_item_price_history(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)),
):
    """Get price history for an item."""
    service = ItemService(db)
    history = await service.get_item_price_history(item_id)
    return ApiResponse(
        success=True,
        data=[
            ItemPriceHistoryResponse(
                id=h.id,
                item_id=h.item_id,
                price=h.price,
                effective_from=h.effective_from.isoformat(),
                changed_by_id=h.changed_by_id,
            )
            for h in history
        ],
    )
