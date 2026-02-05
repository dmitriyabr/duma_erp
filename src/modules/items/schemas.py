"""Schemas for Items module."""

from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.modules.items.models import ItemType, PriceType


# --- Category Schemas ---


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    name: str = Field(..., min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    """Schema for category response."""

    id: int
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


# --- Item Schemas ---


class ItemCreate(BaseModel):
    """Schema for creating an item."""

    category_id: int
    sku_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    item_type: ItemType
    price_type: PriceType
    price: Decimal | None = Field(None, ge=0, decimal_places=2)
    requires_full_payment: bool | None = None  # If None, defaults based on item_type

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate price based on price_type."""
        price_type = info.data.get("price_type")
        if price_type == PriceType.STANDARD and v is None:
            raise ValueError("Price is required for standard price type")
        if price_type in (PriceType.BY_GRADE, PriceType.BY_ZONE) and v is not None:
            raise ValueError("Price must be null for by_grade/by_zone price types")
        return v


class ItemUpdate(BaseModel):
    """Schema for updating an item."""

    category_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    price: Decimal | None = Field(None, ge=0, decimal_places=2)
    requires_full_payment: bool | None = None
    is_active: bool | None = None


class ItemResponse(BaseModel):
    """Schema for item response."""

    id: int
    category_id: int
    category_name: str | None = None
    sku_code: str
    name: str
    item_type: str
    price_type: str
    price: Decimal | None
    requires_full_payment: bool
    is_active: bool
    model_config = {"from_attributes": True}


class ItemPriceHistoryResponse(BaseModel):
    """Schema for item price history response."""

    id: int
    item_id: int
    price: Decimal
    effective_from: str
    changed_by_id: int

    model_config = {"from_attributes": True}


# --- Kit Schemas ---


class KitItemCreate(BaseModel):
    """Schema for kit item in kit creation."""

    source_type: Literal["item", "variant"] = "item"  # Default to 'item' for backward compatibility
    item_id: int | None = None  # If source_type = 'item'
    variant_id: int | None = None  # If source_type = 'variant'
    default_item_id: int | None = None  # If source_type = 'variant'
    quantity: int = Field(1, ge=1)

    @model_validator(mode="after")
    def validate_source(self):
        """Validate that source_type matches provided fields."""
        if self.source_type == "item":
            if not self.item_id:
                raise ValueError("item_id required when source_type='item'")
            if self.variant_id or self.default_item_id:
                raise ValueError("variant_id and default_item_id must be null when source_type='item'")
        elif self.source_type == "variant":
            if not self.variant_id or not self.default_item_id:
                raise ValueError("variant_id and default_item_id required when source_type='variant'")
            if self.item_id:
                raise ValueError("item_id must be null when source_type='variant'")
        return self


class KitCreate(BaseModel):
    """Schema for creating a kit."""

    category_id: int
    sku_code: str | None = Field(None, min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    item_type: ItemType
    price_type: PriceType
    price: Decimal | None = Field(None, ge=0, decimal_places=2)
    requires_full_payment: bool | None = None  # Defaults based on item_type
    is_editable_components: bool | None = None  # Defaults to False
    items: list[KitItemCreate] = Field(default_factory=list)

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate price based on price_type."""
        price_type = info.data.get("price_type")
        if price_type == PriceType.STANDARD and v is None:
            raise ValueError("Price is required for standard price type")
        if price_type in (PriceType.BY_GRADE, PriceType.BY_ZONE) and v is not None:
            raise ValueError("Price must be null for by_grade/by_zone price types")
        return v

    @model_validator(mode="after")
    def validate_items_by_type(self):
        """Ensure product kits have components and services don't."""
        if self.item_type == ItemType.PRODUCT and not self.items:
            raise ValueError("Product kits must include at least one item")
        if self.item_type == ItemType.SERVICE and self.items:
            raise ValueError("Service kits cannot include inventory items")
        return self


class KitItemUpdate(BaseModel):
    """Schema for updating kit items."""

    source_type: Literal["item", "variant"] = "item"  # Default to 'item' for backward compatibility
    item_id: int | None = None
    variant_id: int | None = None
    default_item_id: int | None = None
    quantity: int = Field(1, ge=1)

    @model_validator(mode="after")
    def validate_source(self):
        """Validate that source_type matches provided fields."""
        if self.source_type == "item":
            if not self.item_id:
                raise ValueError("item_id required when source_type='item'")
            if self.variant_id or self.default_item_id:
                raise ValueError("variant_id and default_item_id must be null when source_type='item'")
        elif self.source_type == "variant":
            if not self.variant_id or not self.default_item_id:
                raise ValueError("variant_id and default_item_id required when source_type='variant'")
            if self.item_id:
                raise ValueError("item_id must be null when source_type='variant'")
        return self


class KitUpdate(BaseModel):
    """Schema for updating a kit."""

    category_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    price: Decimal | None = Field(None, ge=0, decimal_places=2)
    requires_full_payment: bool | None = None
    is_active: bool | None = None
    is_editable_components: bool | None = None
    items: list[KitItemUpdate] | None = None

    @model_validator(mode="after")
    def validate_items_for_update(self):
        """Ensure items are not provided for service kits."""
        if self.items is not None and len(self.items) == 0:
            raise ValueError("Items list cannot be empty when provided")
        return self


class KitItemResponse(BaseModel):
    """Schema for kit item response."""

    id: int
    source_type: str
    item_id: int | None = None
    variant_id: int | None = None
    default_item_id: int | None = None
    item_name: str | None = None  # If source_type='item', else None
    variant_name: str | None = None  # If source_type='variant', else None
    default_item_name: str | None = None  # If source_type='variant'
    quantity: int

    model_config = {"from_attributes": True}


class KitResponse(BaseModel):
    """Schema for kit response."""

    id: int
    category_id: int
    category_name: str | None = None
    sku_code: str
    name: str
    item_type: str
    price_type: str
    price: Decimal | None
    requires_full_payment: bool
    is_active: bool
    is_editable_components: bool | None = None
    items: list[KitItemResponse] = []

    model_config = {"from_attributes": True}


class KitPriceHistoryResponse(BaseModel):
    """Schema for kit price history response."""

    id: int
    kit_id: int
    price: Decimal
    effective_from: str
    changed_by_id: int

    model_config = {"from_attributes": True}


# --- Item Variant Schemas ---


class ItemVariantCreate(BaseModel):
    """Schema for creating an item variant."""

    name: str = Field(..., min_length=1, max_length=200)
    item_ids: list[int] = Field(default_factory=list)  # Items to include in this variant


class ItemVariantUpdate(BaseModel):
    """Schema for updating an item variant."""

    name: str | None = Field(None, min_length=1, max_length=200)
    is_active: bool | None = None
    # Full list of item IDs that should belong to this variant (replaces all memberships)
    item_ids: list[int] | None = None


class ItemVariantItemResponse(BaseModel):
    """Item that belongs to a variant."""

    id: int
    name: str
    sku_code: str


class ItemVariantResponse(BaseModel):
    """Schema for variant response."""

    id: int
    name: str
    is_active: bool
    items: list[ItemVariantItemResponse] = []

    model_config = {"from_attributes": True}
