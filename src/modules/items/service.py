"""Service for Items module."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.models import DocumentSequence
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.modules.items.models import (
    Category,
    Item,
    ItemPriceHistory,
    ItemType,
    ItemVariant,
    ItemVariantMembership,
    Kit,
    KitItem,
    KitPriceHistory,
    PriceType,
)
from src.modules.items.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ItemCreate,
    ItemUpdate,
    ItemVariantCreate,
    ItemVariantUpdate,
    KitCreate,
    KitItemCreate,
    KitUpdate,
)


class ItemService:
    """Service for managing items, categories, kits and variant groups."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # --- Category Methods ---

    async def create_category(self, data: CategoryCreate, created_by_id: int) -> Category:
        """Create a new category."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(Category).where(Category.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise DuplicateError("Category", "name", data.name)

        category = Category(name=data.name)
        self.db.add(category)
        await self.db.flush()

        await self.audit.log(
            action="category.create",
            entity_type="Category",
            entity_id=category.id,
            user_id=created_by_id,
            new_values={"name": data.name},
        )

        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def get_category_by_id(self, category_id: int) -> Category:
        """Get category by ID."""
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise NotFoundError(f"Category with id {category_id} not found")
        return category

    async def list_categories(self, include_inactive: bool = False) -> list[Category]:
        """List all categories."""
        query = select(Category).order_by(Category.name)
        if not include_inactive:
            query = query.where(Category.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_or_create_category_by_name(self, name: str) -> Category:
        """Get category by name, or create if not exists. Does not commit."""
        name_clean = name.strip()
        if not name_clean:
            name_clean = "Uncategorized"
        result = await self.db.execute(
            select(Category).where(Category.name == name_clean)
        )
        category = result.scalar_one_or_none()
        if category:
            return category
        category = Category(name=name_clean)
        self.db.add(category)
        await self.db.flush()
        return category

    async def _generate_item_sku(self, category: Category) -> str:
        """Generate unique SKU for an item in the given category. Does not commit."""
        prefix = self._build_sku_prefix(category.name)
        while True:
            sequence = await self._next_sku_sequence(prefix)
            sku_code = f"{prefix}-{sequence:06d}"
            existing = await self.db.execute(
                select(Item.id).where(Item.sku_code == sku_code)
            )
            if not existing.scalar_one_or_none():
                return sku_code

    async def get_or_create_product_item(
        self,
        category_name: str,
        item_name: str,
        sku: str | None = None,
        created_by_id: int = 0,
    ) -> tuple[Item, bool]:
        """Get or create a product item by category name and item name (or sku).

        Returns (item, created). Does not commit; caller must commit.
        """
        category = await self.get_or_create_category_by_name(category_name)
        item_name_clean = item_name.strip()
        if not item_name_clean:
            raise ValidationError("item_name cannot be empty")

        if sku and sku.strip():
            result = await self.db.execute(
                select(Item).where(
                    Item.sku_code == sku.strip(),
                    Item.item_type == ItemType.PRODUCT.value,
                )
            )
            item = result.scalar_one_or_none()
            if item:
                return item, False

        result = await self.db.execute(
            select(Item).where(
                Item.category_id == category.id,
                Item.name == item_name_clean,
                Item.item_type == ItemType.PRODUCT.value,
            )
        )
        item = result.scalar_one_or_none()
        if item:
            return item, False

        sku_code = await self._generate_item_sku(category)
        item = Item(
            category_id=category.id,
            sku_code=sku_code,
            name=item_name_clean,
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("0.00"),
            requires_full_payment=True,
        )
        self.db.add(item)
        await self.db.flush()

        await self.audit.log(
            action="item.create",
            entity_type="Item",
            entity_id=item.id,
            user_id=created_by_id,
            new_values={
                "sku_code": sku_code,
                "name": item_name_clean,
                "item_type": ItemType.PRODUCT.value,
                "source": "bulk_upload",
            },
        )

        return item, True

    async def update_category(
        self, category_id: int, data: CategoryUpdate, updated_by_id: int
    ) -> Category:
        """Update a category."""
        category = await self.get_category_by_id(category_id)
        old_values = {"name": category.name, "is_active": category.is_active}
        new_values = {}

        if data.name is not None and data.name != category.name:
            # Check for duplicate name
            existing = await self.db.execute(
                select(Category).where(
                    Category.name == data.name, Category.id != category_id
                )
            )
            if existing.scalar_one_or_none():
                raise DuplicateError("Category", "name", data.name)
            category.name = data.name
            new_values["name"] = data.name

        if data.is_active is not None:
            category.is_active = data.is_active
            new_values["is_active"] = data.is_active

        if new_values:
            await self.audit.log(
                action="category.update",
                entity_type="Category",
                entity_id=category_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(category)
        return category

    # --- Item Methods ---

    async def create_item(self, data: ItemCreate, created_by_id: int) -> Item:
        """Create a new item."""
        # Check category exists
        await self.get_category_by_id(data.category_id)

        # Check for duplicate SKU
        existing = await self.db.execute(
            select(Item).where(Item.sku_code == data.sku_code)
        )
        if existing.scalar_one_or_none():
            raise DuplicateError("Item", "sku_code", data.sku_code)

        # Determine requires_full_payment: explicit value or default by item_type
        requires_full_payment = data.requires_full_payment
        if requires_full_payment is None:
            requires_full_payment = data.item_type == ItemType.PRODUCT

        item = Item(
            category_id=data.category_id,
            sku_code=data.sku_code,
            name=data.name,
            item_type=data.item_type.value,
            price_type=data.price_type.value,
            price=data.price,
            requires_full_payment=requires_full_payment,
        )
        self.db.add(item)
        await self.db.flush()

        # Create initial price history if price is set
        if data.price is not None:
            price_history = ItemPriceHistory(
                item_id=item.id,
                price=data.price,
                changed_by_id=created_by_id,
            )
            self.db.add(price_history)

        await self.audit.log(
            action="item.create",
            entity_type="Item",
            entity_id=item.id,
            user_id=created_by_id,
            new_values={
                "sku_code": data.sku_code,
                "name": data.name,
                "item_type": data.item_type.value,
                "price_type": data.price_type.value,
                "price": str(data.price) if data.price else None,
            },
        )

        await self.db.commit()
        await self.db.refresh(item)
        return item

    def _build_sku_prefix(self, category_name: str) -> str:
        cleaned = "".join(ch for ch in category_name.upper() if ch.isalnum())
        if not cleaned:
            cleaned = "CAT"
        return cleaned[:6]

    async def _next_sku_sequence(self, prefix: str) -> int:
        stmt = (
            select(DocumentSequence)
            .where(DocumentSequence.prefix == prefix, DocumentSequence.year == 0)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        sequence = result.scalar_one_or_none()
        if sequence is None:
            sequence = DocumentSequence(prefix=prefix, year=0, last_number=0)
            self.db.add(sequence)
            await self.db.flush()
            result = await self.db.execute(stmt)
            sequence = result.scalar_one()

        sequence.last_number += 1
        await self.db.flush()
        return sequence.last_number

    async def _generate_kit_sku(self, category: Category) -> str:
        prefix = self._build_sku_prefix(category.name)
        while True:
            sequence = await self._next_sku_sequence(prefix)
            sku_code = f"{prefix}-{sequence:06d}"

            existing_kit = await self.db.execute(
                select(Kit.id).where(Kit.sku_code == sku_code)
            )
            if existing_kit.scalar_one_or_none():
                continue

            existing_item = await self.db.execute(
                select(Item.id).where(Item.sku_code == sku_code)
            )
            if existing_item.scalar_one_or_none():
                continue

            return sku_code

    async def get_item_by_id(self, item_id: int, with_category: bool = False) -> Item:
        """Get item by ID."""
        query = select(Item).where(Item.id == item_id)
        if with_category:
            query = query.options(selectinload(Item.category))
        result = await self.db.execute(query)
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(f"Item with id {item_id} not found")
        return item

    async def get_item_by_sku(self, sku_code: str) -> Item:
        """Get item by SKU code."""
        result = await self.db.execute(
            select(Item).where(Item.sku_code == sku_code)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(f"Item with SKU '{sku_code}' not found")
        return item

    async def list_items(
        self,
        category_id: int | None = None,
        item_type: ItemType | None = None,
        include_inactive: bool = False,
    ) -> list[Item]:
        """List items with optional filters."""
        query = select(Item).options(selectinload(Item.category)).order_by(Item.name)

        if not include_inactive:
            query = query.where(Item.is_active == True)
        if category_id is not None:
            query = query.where(Item.category_id == category_id)
        if item_type is not None:
            query = query.where(Item.item_type == item_type.value)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _has_transactions_for_price(self, item_id: int, price_history_id: int) -> bool:
        """Check if there are any transactions using this price history entry.

        This will be implemented when Invoice module is added.
        For now, returns False (no transactions).
        """
        # TODO: Implement when Invoice module is added
        # Check if any InvoiceItem references this price_history_id
        return False

    async def update_item(
        self, item_id: int, data: ItemUpdate, updated_by_id: int
    ) -> Item:
        """Update an item."""
        item = await self.get_item_by_id(item_id)
        old_values = {
            "category_id": item.category_id,
            "name": item.name,
            "price": str(item.price) if item.price else None,
            "requires_full_payment": item.requires_full_payment,
            "is_active": item.is_active,
        }
        new_values = {}

        if data.category_id is not None and data.category_id != item.category_id:
            await self.get_category_by_id(data.category_id)
            item.category_id = data.category_id
            new_values["category_id"] = data.category_id

        if data.name is not None and data.name != item.name:
            item.name = data.name
            new_values["name"] = data.name

        if data.is_active is not None and data.is_active != item.is_active:
            item.is_active = data.is_active
            new_values["is_active"] = data.is_active

        if data.requires_full_payment is not None and data.requires_full_payment != item.requires_full_payment:
            item.requires_full_payment = data.requires_full_payment
            new_values["requires_full_payment"] = data.requires_full_payment

        if data.price is not None and data.price != item.price:
            if item.price_type != PriceType.STANDARD.value:
                raise ValidationError("Cannot set price for by_grade/by_zone items")

            await self._update_price_history(item, data.price, updated_by_id)
            item.price = data.price
            new_values["price"] = str(data.price)

        if new_values:
            await self.audit.log(
                action="item.update",
                entity_type="Item",
                entity_id=item_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def _update_price_history(
        self, item: Item, new_price: Decimal, changed_by_id: int
    ) -> None:
        """Update price history for an item.

        If the latest price has no transactions, update it.
        Otherwise, create a new history entry.
        """
        # Get latest price history
        result = await self.db.execute(
            select(ItemPriceHistory)
            .where(ItemPriceHistory.item_id == item.id)
            .order_by(ItemPriceHistory.effective_from.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        if latest and not await self._has_transactions_for_price(item.id, latest.id):
            # No transactions - update existing entry
            latest.price = new_price
            latest.changed_by_id = changed_by_id
        else:
            # Has transactions or no history - create new entry
            price_history = ItemPriceHistory(
                item_id=item.id,
                price=new_price,
                changed_by_id=changed_by_id,
            )
            self.db.add(price_history)

    async def get_item_price_history(self, item_id: int) -> list[ItemPriceHistory]:
        """Get price history for an item."""
        await self.get_item_by_id(item_id)  # Verify item exists
        result = await self.db.execute(
            select(ItemPriceHistory)
            .where(ItemPriceHistory.item_id == item_id)
            .order_by(ItemPriceHistory.effective_from.desc())
        )
        return list(result.scalars().all())

    # --- Item Variant Methods ---

    async def create_variant(
        self, data: ItemVariantCreate, created_by_id: int
    ) -> ItemVariant:
        """Create a new variant and optionally add items."""
        existing = await self.db.execute(
            select(ItemVariant).where(ItemVariant.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise DuplicateError("ItemVariant", "name", data.name)

        variant = ItemVariant(name=data.name)
        self.db.add(variant)
        await self.db.flush()

        # Add items to variant if provided
        if data.item_ids:
            # Validate all items exist and are products
            result = await self.db.execute(
                select(Item).where(Item.id.in_(data.item_ids))
            )
            items = list(result.scalars().all())
            if len(items) != len(data.item_ids):
                raise NotFoundError("One or more items not found")
            for item in items:
                if item.item_type != ItemType.PRODUCT.value:
                    raise ValidationError(
                        f"Item '{item.name}' is not a product and cannot be added to variant"
                    )

            # Create memberships
            for item_id in data.item_ids:
                membership = ItemVariantMembership(
                    variant_id=variant.id,
                    item_id=item_id,
                    is_default=False,
                )
                self.db.add(membership)

        await self.audit.log(
            action="variant.create",
            entity_type="ItemVariant",
            entity_id=variant.id,
            user_id=created_by_id,
            new_values={"name": data.name, "item_ids": data.item_ids},
        )

        await self.db.commit()
        await self.db.refresh(variant)
        return variant

    async def get_variant_by_id(self, variant_id: int) -> ItemVariant:
        """Get variant by ID."""
        result = await self.db.execute(
            select(ItemVariant).where(ItemVariant.id == variant_id)
        )
        variant = result.scalar_one_or_none()
        if not variant:
            raise NotFoundError(f"ItemVariant with id {variant_id} not found")
        return variant

    async def list_variants(
        self, include_inactive: bool = False
    ) -> list[ItemVariant]:
        """List all variants."""
        query = select(ItemVariant).order_by(ItemVariant.name)
        if not include_inactive:
            query = query.where(ItemVariant.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_items_for_variant(self, variant_id: int) -> list[Item]:
        """Get all items that belong to a specific variant."""
        # Load variant with items relationship
        result = await self.db.execute(
            select(ItemVariant)
            .where(ItemVariant.id == variant_id)
            .options(selectinload(ItemVariant.items))
        )
        variant = result.scalar_one_or_none()
        if not variant:
            return []
        # Return items sorted by name
        return sorted(variant.items, key=lambda item: item.name)

    async def update_variant(
        self, variant_id: int, data: ItemVariantUpdate, updated_by_id: int
    ) -> ItemVariant:
        """Update a variant and optionally reassign items."""
        variant = await self.get_variant_by_id(variant_id)
        old_values = {
            "name": variant.name,
            "is_active": variant.is_active,
        }
        new_values: dict[str, object] = {}

        if data.name is not None and data.name != variant.name:
            existing = await self.db.execute(
                select(ItemVariant).where(
                    ItemVariant.name == data.name,
                    ItemVariant.id != variant_id,
                )
            )
            if existing.scalar_one_or_none():
                raise DuplicateError("ItemVariant", "name", data.name)
            variant.name = data.name
            new_values["name"] = data.name

        if data.is_active is not None and data.is_active != variant.is_active:
            variant.is_active = data.is_active
            new_values["is_active"] = data.is_active

        # Reassign items to this variant if full list provided
        if data.item_ids is not None:
            # Get current item IDs
            result = await self.db.execute(
                select(ItemVariantMembership.item_id).where(
                    ItemVariantMembership.variant_id == variant_id
                )
            )
            current_ids = {row[0] for row in result.all()}
            new_ids = set(data.item_ids)

            to_remove = current_ids - new_ids
            to_add = new_ids - current_ids

            # Remove memberships
            if to_remove:
                await self.db.execute(
                    ItemVariantMembership.__table__.delete().where(
                        ItemVariantMembership.variant_id == variant_id,
                        ItemVariantMembership.item_id.in_(list(to_remove)),
                    )
                )

            # Add new memberships
            if to_add:
                # Validate all items exist and are products
                result = await self.db.execute(
                    select(Item).where(Item.id.in_(list(to_add)))
                )
                items = list(result.scalars().all())
                if len(items) != len(to_add):
                    raise NotFoundError("One or more items not found")
                for item in items:
                    if item.item_type != ItemType.PRODUCT.value:
                        raise ValidationError(
                            f"Item '{item.name}' is not a product and cannot be added to variant"
                        )

                # Create memberships
                for item_id in to_add:
                    membership = ItemVariantMembership(
                        variant_id=variant_id,
                        item_id=item_id,
                        is_default=False,
                    )
                    self.db.add(membership)

            new_values["item_ids"] = data.item_ids

        if new_values:
            await self.audit.log(
                action="variant.update",
                entity_type="ItemVariant",
                entity_id=variant_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(variant)
        return variant

    # --- Kit Methods ---

    async def create_kit(self, data: KitCreate, created_by_id: int) -> Kit:
        """Create a new kit."""
        category = await self.get_category_by_id(data.category_id)

        sku_code = data.sku_code
        if not sku_code:
            sku_code = await self._generate_kit_sku(category)

        # Check for duplicate SKU
        existing = await self.db.execute(select(Kit).where(Kit.sku_code == sku_code))
        if existing.scalar_one_or_none():
            raise DuplicateError("Kit", "sku_code", sku_code)

        # Also check Item SKUs
        existing_item = await self.db.execute(
            select(Item).where(Item.sku_code == sku_code)
        )
        if existing_item.scalar_one_or_none():
            raise DuplicateError("Item", "sku_code", sku_code)

        if data.item_type == ItemType.PRODUCT:
            if not data.items:
                raise ValidationError("Product kits must include at least one item")
            # Validate kit items
            for kit_item in data.items:
                if kit_item.source_type == "item":
                    if not kit_item.item_id:
                        raise ValidationError("item_id required when source_type='item'")
                    await self.get_item_by_id(kit_item.item_id)
                elif kit_item.source_type == "variant":
                    if not kit_item.variant_id or not kit_item.default_item_id:
                        raise ValidationError("variant_id and default_item_id required when source_type='variant'")
                    variant = await self.get_variant_by_id(kit_item.variant_id)
                    # Verify default_item_id is in the variant
                    variant_items = await self.get_items_for_variant(kit_item.variant_id)
                    if not any(item.id == kit_item.default_item_id for item in variant_items):
                        raise ValidationError(
                            f"default_item_id {kit_item.default_item_id} is not in variant {variant.name}"
                        )
                    await self.get_item_by_id(kit_item.default_item_id)
        elif data.items:
            raise ValidationError("Service kits cannot include inventory items")

        requires_full_payment = data.requires_full_payment
        if requires_full_payment is None:
            requires_full_payment = data.item_type == ItemType.PRODUCT

        is_editable_components = bool(data.is_editable_components) if data.is_editable_components is not None else False

        kit = Kit(
            category_id=data.category_id,
            sku_code=sku_code,
            name=data.name,
            item_type=data.item_type.value,
            price_type=data.price_type.value,
            price=data.price,
            requires_full_payment=requires_full_payment,
            is_editable_components=is_editable_components,
        )
        self.db.add(kit)
        await self.db.flush()

        # Add kit items
        if data.items:
            for kit_item_data in data.items:
                if kit_item_data.source_type == "item":
                    kit_item = KitItem(
                        kit_id=kit.id,
                        source_type="item",
                        item_id=kit_item_data.item_id,
                        variant_id=None,
                        default_item_id=None,
                        quantity=kit_item_data.quantity,
                    )
                else:  # variant
                    kit_item = KitItem(
                        kit_id=kit.id,
                        source_type="variant",
                        item_id=None,
                        variant_id=kit_item_data.variant_id,
                        default_item_id=kit_item_data.default_item_id,
                        quantity=kit_item_data.quantity,
                    )
                self.db.add(kit_item)

        # Create initial price history for standard pricing
        if data.price is not None:
            price_history = KitPriceHistory(
                kit_id=kit.id,
                price=data.price,
                changed_by_id=created_by_id,
            )
            self.db.add(price_history)

        await self.audit.log(
            action="kit.create",
            entity_type="Kit",
            entity_id=kit.id,
            user_id=created_by_id,
            new_values={
                "sku_code": sku_code,
                "name": data.name,
                "category_id": data.category_id,
                "item_type": data.item_type.value,
                "price_type": data.price_type.value,
                "price": str(data.price) if data.price is not None else None,
                "items": [{"item_id": i.item_id, "quantity": i.quantity} for i in data.items],
            },
        )

        await self.db.commit()
        await self.db.refresh(kit)
        return kit

    async def get_kit_by_id(self, kit_id: int, with_items: bool = False) -> Kit:
        """Get kit by ID."""
        query = select(Kit).where(Kit.id == kit_id)
        if with_items:
            query = query.options(
                selectinload(Kit.kit_items).selectinload(KitItem.item),
                selectinload(Kit.kit_items).selectinload(KitItem.variant),
                selectinload(Kit.kit_items).selectinload(KitItem.default_item),
                selectinload(Kit.category),
            )
        result = await self.db.execute(query)
        kit = result.scalar_one_or_none()
        if not kit:
            raise NotFoundError(f"Kit with id {kit_id} not found")
        return kit

    async def list_kits(self, include_inactive: bool = False, exclude_fixed_fees: bool = True) -> list[Kit]:
        """
        List all kits.

        Args:
            include_inactive: Include inactive kits
            exclude_fixed_fees: Exclude kits from "Fixed Fees" category (default True)
        """
        query = (
            select(Kit)
            .options(
                selectinload(Kit.kit_items).selectinload(KitItem.item),
                selectinload(Kit.kit_items).selectinload(KitItem.variant),
                selectinload(Kit.kit_items).selectinload(KitItem.default_item),
                selectinload(Kit.category),
            )
            .order_by(Kit.name)
        )
        if not include_inactive:
            query = query.where(Kit.is_active == True)

        # Exclude "Fixed Fees" category from regular catalog
        if exclude_fixed_fees:
            fixed_fees_category = await self.db.execute(
                select(Category.id).where(Category.name == "Fixed Fees")
            )
            fixed_fees_cat_id = fixed_fees_category.scalar_one_or_none()
            if fixed_fees_cat_id:
                query = query.where(Kit.category_id != fixed_fees_cat_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _has_transactions_for_kit_price(self, kit_id: int, price_history_id: int) -> bool:
        """Check if there are any transactions using this kit price history entry.

        This will be implemented when Invoice module is added.
        For now, returns False (no transactions).
        """
        # TODO: Implement when Invoice module is added
        return False

    async def update_kit(
        self, kit_id: int, data: KitUpdate, updated_by_id: int
    ) -> Kit:
        """Update a kit."""
        kit = await self.get_kit_by_id(kit_id, with_items=True)
        old_values = {
            "category_id": kit.category_id,
            "name": kit.name,
            "price": str(kit.price),
            "requires_full_payment": kit.requires_full_payment,
            "is_active": kit.is_active,
        }
        new_values = {}

        if data.category_id is not None and data.category_id != kit.category_id:
            await self.get_category_by_id(data.category_id)
            kit.category_id = data.category_id
            new_values["category_id"] = data.category_id

        if data.name is not None and data.name != kit.name:
            kit.name = data.name
            new_values["name"] = data.name

        if data.is_active is not None and data.is_active != kit.is_active:
            kit.is_active = data.is_active
            new_values["is_active"] = data.is_active

        if (
            data.is_editable_components is not None
            and data.is_editable_components != kit.is_editable_components
        ):
            kit.is_editable_components = data.is_editable_components
            new_values["is_editable_components"] = data.is_editable_components

        if data.requires_full_payment is not None and data.requires_full_payment != kit.requires_full_payment:
            kit.requires_full_payment = data.requires_full_payment
            new_values["requires_full_payment"] = data.requires_full_payment

        if data.price is not None and data.price != kit.price:
            if kit.price_type != PriceType.STANDARD.value:
                raise ValidationError("Cannot set price for by_grade/by_zone kits")
            await self._update_kit_price_history(kit, data.price, updated_by_id)
            kit.price = data.price
            new_values["price"] = str(data.price)

        if data.items is not None:
            if kit.item_type == ItemType.SERVICE.value:
                raise ValidationError("Service kits cannot include inventory items")
            # Validate kit items
            for kit_item_data in data.items:
                if kit_item_data.source_type == "item":
                    if not kit_item_data.item_id:
                        raise ValidationError("item_id required when source_type='item'")
                    await self.get_item_by_id(kit_item_data.item_id)
                elif kit_item_data.source_type == "variant":
                    if not kit_item_data.variant_id or not kit_item_data.default_item_id:
                        raise ValidationError("variant_id and default_item_id required when source_type='variant'")
                    variant = await self.get_variant_by_id(kit_item_data.variant_id)
                    # Verify default_item_id is in the variant
                    variant_items = await self.get_items_for_variant(kit_item_data.variant_id)
                    if not any(item.id == kit_item_data.default_item_id for item in variant_items):
                        raise ValidationError(
                            f"default_item_id {kit_item_data.default_item_id} is not in variant {variant.name}"
                        )
                    await self.get_item_by_id(kit_item_data.default_item_id)

            # Remove existing kit items
            for kit_item in kit.kit_items:
                await self.db.delete(kit_item)

            # Add new kit items
            for kit_item_data in data.items:
                if kit_item_data.source_type == "item":
                    kit_item = KitItem(
                        kit_id=kit.id,
                        source_type="item",
                        item_id=kit_item_data.item_id,
                        variant_id=None,
                        default_item_id=None,
                        quantity=kit_item_data.quantity,
                    )
                else:  # variant
                    kit_item = KitItem(
                        kit_id=kit.id,
                        source_type="variant",
                        item_id=None,
                        variant_id=kit_item_data.variant_id,
                        default_item_id=kit_item_data.default_item_id,
                        quantity=kit_item_data.quantity,
                    )
                self.db.add(kit_item)

            new_values["items"] = [
                {
                    "source_type": i.source_type,
                    "item_id": i.item_id,
                    "variant_id": i.variant_id,
                    "default_item_id": i.default_item_id,
                    "quantity": i.quantity,
                }
                for i in data.items
            ]

        if new_values:
            await self.audit.log(
                action="kit.update",
                entity_type="Kit",
                entity_id=kit_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(kit)
        return kit

    async def _update_kit_price_history(
        self, kit: Kit, new_price: Decimal, changed_by_id: int
    ) -> None:
        """Update price history for a kit.

        If the latest price has no transactions, update it.
        Otherwise, create a new history entry.
        """
        # Get latest price history
        result = await self.db.execute(
            select(KitPriceHistory)
            .where(KitPriceHistory.kit_id == kit.id)
            .order_by(KitPriceHistory.effective_from.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        if latest and not await self._has_transactions_for_kit_price(kit.id, latest.id):
            # No transactions - update existing entry
            latest.price = new_price
            latest.changed_by_id = changed_by_id
        else:
            # Has transactions or no history - create new entry
            price_history = KitPriceHistory(
                kit_id=kit.id,
                price=new_price,
                changed_by_id=changed_by_id,
            )
            self.db.add(price_history)

    async def get_kit_price_history(self, kit_id: int) -> list[KitPriceHistory]:
        """Get price history for a kit."""
        await self.get_kit_by_id(kit_id)  # Verify kit exists
        result = await self.db.execute(
            select(KitPriceHistory)
            .where(KitPriceHistory.kit_id == kit_id)
            .order_by(KitPriceHistory.effective_from.desc())
        )
        return list(result.scalars().all())
