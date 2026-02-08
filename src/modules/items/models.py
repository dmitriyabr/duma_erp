"""Item, Category, Kit models."""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class ItemType(StrEnum):
    """Item type enumeration."""

    SERVICE = "service"
    PRODUCT = "product"


class PriceType(StrEnum):
    """Price type enumeration."""

    STANDARD = "standard"  # Price from Item.price
    BY_GRADE = "by_grade"  # Price from PriceSetting by student's grade
    BY_ZONE = "by_zone"  # Price from TransportPricing by student's zone


class Category(Base):
    """Product/service category."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    items: Mapped[list["Item"]] = relationship("Item", back_populates="category")
    kits: Mapped[list["Kit"]] = relationship("Kit", back_populates="category")


class ItemVariant(Base):
    """Group of interchangeable item variants (e.g. same model, different sizes)."""

    __tablename__ = "item_variants"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships (many-to-many through ItemVariantMembership)
    items: Mapped[list["Item"]] = relationship(
        "Item", secondary="item_variant_memberships", back_populates="variants"
    )


class ItemVariantMembership(Base):
    """Association between Item and ItemVariant (many-to-many)."""

    __tablename__ = "item_variant_memberships"
    __table_args__ = (
        UniqueConstraint("variant_id", "item_id", name="uq_variant_item"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("item_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    variant: Mapped["ItemVariant"] = relationship("ItemVariant")
    item: Mapped["Item"] = relationship("Item")


class Item(Base):
    """Product or service that can be added to an invoice."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=False, index=True
    )
    sku_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)  # service | product
    price_type: Mapped[str] = mapped_column(String(20), nullable=False)  # standard | by_grade | by_zone
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )  # Null for by_grade/by_zone or kit-only items
    requires_full_payment: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # True for products and special fees (admission), False for regular services
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="items")
    variants: Mapped[list["ItemVariant"]] = relationship(
        "ItemVariant", secondary="item_variant_memberships", back_populates="items"
    )
    price_history: Mapped[list["ItemPriceHistory"]] = relationship(
        "ItemPriceHistory", back_populates="item", order_by="desc(ItemPriceHistory.effective_from)"
    )
    kit_items: Mapped[list["KitItem"]] = relationship("KitItem", back_populates="item", foreign_keys="[KitItem.item_id]")
    stock: Mapped["Stock | None"] = relationship(
        "Stock", back_populates="item", uselist=False
    )


# Forward reference for Stock (imported at module load time)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.inventory.models import Stock


class ItemPriceHistory(Base):
    """History of item price changes for accounting purposes."""

    __tablename__ = "item_price_history"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    effective_from: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="price_history")


class Kit(Base):
    """Product kit/bundle with its own price."""

    __tablename__ = "kits"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=False, index=True
    )
    sku_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)  # service | product
    price_type: Mapped[str] = mapped_column(String(20), nullable=False)  # standard | by_grade | by_zone
    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    requires_full_payment: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # Kits typically contain products, so require full payment by default
    is_editable_components: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # Whether invoice lines for this kit can override component items
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="kits")
    kit_items: Mapped[list["KitItem"]] = relationship(
        "KitItem", back_populates="kit", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["KitPriceHistory"]] = relationship(
        "KitPriceHistory", back_populates="kit", order_by="desc(KitPriceHistory.effective_from)"
    )


class KitItem(Base):
    """Item included in a kit - can be a direct item or a variant."""

    __tablename__ = "kit_items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    kit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Source type: 'item' or 'variant'
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'item' | 'variant'
    
    # If source_type = 'item'
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True, index=True
    )
    
    # If source_type = 'variant'
    variant_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("item_variants.id"), nullable=True, index=True
    )
    default_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True, index=True
    )
    
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    kit: Mapped["Kit"] = relationship("Kit", back_populates="kit_items")
    item: Mapped["Item | None"] = relationship("Item", foreign_keys=[item_id], back_populates="kit_items")
    variant: Mapped["ItemVariant | None"] = relationship("ItemVariant", foreign_keys=[variant_id])
    default_item: Mapped["Item | None"] = relationship("Item", foreign_keys=[default_item_id])
    
    __table_args__ = (
        CheckConstraint(
            "(source_type = 'item' AND item_id IS NOT NULL AND variant_id IS NULL AND default_item_id IS NULL) OR "
            "(source_type = 'variant' AND variant_id IS NOT NULL AND default_item_id IS NOT NULL AND item_id IS NULL)",
            name="ck_kit_item_source",
        ),
    )


class KitPriceHistory(Base):
    """History of kit price changes for accounting purposes."""

    __tablename__ = "kit_price_history"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    kit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    effective_from: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    kit: Mapped["Kit"] = relationship("Kit", back_populates="price_history")
