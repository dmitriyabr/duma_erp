"""Tests for Items module."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.modules.items.models import ItemType, PriceType
from src.modules.items.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ItemCreate,
    ItemUpdate,
    KitCreate,
    KitItemCreate,
    KitUpdate,
)
from src.modules.items.service import ItemService


class TestCategoryService:
    """Tests for Category operations in ItemService."""

    async def _create_super_admin(self, db_session: AsyncSession) -> int:
        """Helper to create super admin."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="admin@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        return user.id

    async def test_create_category(self, db_session: AsyncSession):
        """Test creating a new category."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        category = await service.create_category(
            CategoryCreate(name="Test Category"),
            created_by_id=admin_id,
        )

        assert category.id is not None
        assert category.name == "Test Category"
        assert category.is_active is True

    async def test_create_category_duplicate(self, db_session: AsyncSession):
        """Test that duplicate category name raises error."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        await service.create_category(
            CategoryCreate(name="Test Category"),
            created_by_id=admin_id,
        )

        with pytest.raises(DuplicateError):
            await service.create_category(
                CategoryCreate(name="Test Category"),
                created_by_id=admin_id,
            )

    async def test_list_categories(self, db_session: AsyncSession):
        """Test listing categories."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        await service.create_category(
            CategoryCreate(name="Category A"),
            created_by_id=admin_id,
        )
        await service.create_category(
            CategoryCreate(name="Category B"),
            created_by_id=admin_id,
        )

        categories = await service.list_categories()
        assert len(categories) == 2
        names = {c.name for c in categories}
        assert names == {"Category A", "Category B"}

    async def test_update_category(self, db_session: AsyncSession):
        """Test updating a category."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        category = await service.create_category(
            CategoryCreate(name="Old Name"),
            created_by_id=admin_id,
        )

        updated = await service.update_category(
            category.id,
            CategoryUpdate(name="New Name", is_active=False),
            updated_by_id=admin_id,
        )

        assert updated.name == "New Name"
        assert updated.is_active is False

    async def test_get_or_create_category_by_name_creates(self, db_session: AsyncSession):
        """Test get_or_create_category_by_name creates new category."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        category = await service.get_or_create_category_by_name("New Category")
        assert category.id is not None
        assert category.name == "New Category"

    async def test_get_or_create_category_by_name_returns_existing(self, db_session: AsyncSession):
        """Test get_or_create_category_by_name returns same category on second call."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        cat1 = await service.get_or_create_category_by_name("Same Name")
        cat2 = await service.get_or_create_category_by_name("Same Name")
        assert cat1.id == cat2.id
        assert cat1.name == cat2.name == "Same Name"


class TestItemService:
    """Tests for Item operations in ItemService."""

    async def _create_super_admin(self, db_session: AsyncSession) -> int:
        """Helper to create super admin."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="admin@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        return user.id

    async def _create_category(self, db_session: AsyncSession, admin_id: int) -> int:
        """Helper to create a category."""
        service = ItemService(db_session)
        category = await service.create_category(
            CategoryCreate(name="Test Category"),
            created_by_id=admin_id,
        )
        return category.id

    async def test_create_item_standard(self, db_session: AsyncSession):
        """Test creating an item with standard price."""
        admin_id = await self._create_super_admin(db_session)
        category_id = await self._create_category(db_session, admin_id)
        service = ItemService(db_session)

        item = await service.create_item(
            ItemCreate(
                category_id=category_id,
                sku_code="TEST-001",
                name="Test Item",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )

        assert item.id is not None
        assert item.sku_code == "TEST-001"
        assert item.name == "Test Item"
        assert item.item_type == "product"
        assert item.price_type == "standard"
        assert item.price == Decimal("100.00")
        assert item.is_active is True

    async def test_create_item_by_grade(self, db_session: AsyncSession):
        """Test creating an item with by_grade price type."""
        admin_id = await self._create_super_admin(db_session)
        category_id = await self._create_category(db_session, admin_id)
        service = ItemService(db_session)

        item = await service.create_item(
            ItemCreate(
                category_id=category_id,
                sku_code="SCHOOL-FEE",
                name="School Fee",
                item_type=ItemType.SERVICE,
                price_type=PriceType.BY_GRADE,
                price=None,
            ),
            created_by_id=admin_id,
        )

        assert item.price is None
        assert item.price_type == "by_grade"

    async def test_create_item_duplicate_sku(self, db_session: AsyncSession):
        """Test that duplicate SKU raises error."""
        admin_id = await self._create_super_admin(db_session)
        category_id = await self._create_category(db_session, admin_id)
        service = ItemService(db_session)

        await service.create_item(
            ItemCreate(
                category_id=category_id,
                sku_code="TEST-001",
                name="Test Item",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )

        with pytest.raises(DuplicateError):
            await service.create_item(
                ItemCreate(
                    category_id=category_id,
                    sku_code="TEST-001",
                    name="Another Item",
                    item_type=ItemType.PRODUCT,
                    price_type=PriceType.STANDARD,
                    price=Decimal("200.00"),
                ),
                created_by_id=admin_id,
            )

    async def test_get_or_create_product_item_creates(self, db_session: AsyncSession):
        """Test get_or_create_product_item creates new category and product."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        item, created = await service.get_or_create_product_item(
            category_name="Bulk Cat",
            item_name="Bulk Item",
            sku=None,
            created_by_id=admin_id,
        )
        assert created is True
        assert item.id is not None
        assert item.name == "Bulk Item"
        assert item.item_type == ItemType.PRODUCT.value
        assert item.sku_code  # auto-generated

    async def test_get_or_create_product_item_returns_existing_by_name(self, db_session: AsyncSession):
        """Test get_or_create_product_item returns same item on second call (by category+name)."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        item1, created1 = await service.get_or_create_product_item(
            category_name="Same Cat",
            item_name="Same Item",
            sku=None,
            created_by_id=admin_id,
        )
        item2, created2 = await service.get_or_create_product_item(
            category_name="Same Cat",
            item_name="Same Item",
            sku=None,
            created_by_id=admin_id,
        )
        assert created1 is True
        assert created2 is False
        assert item1.id == item2.id

    async def test_get_or_create_product_item_returns_existing_by_sku(self, db_session: AsyncSession):
        """Test get_or_create_product_item finds existing item by SKU."""
        admin_id = await self._create_super_admin(db_session)
        category_id = await self._create_category(db_session, admin_id)
        service = ItemService(db_session)

        created_item = await service.create_item(
            ItemCreate(
                category_id=category_id,
                sku_code="BULK-SKU-001",
                name="Existing Product",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("0.00"),
            ),
            created_by_id=admin_id,
        )

        item, created = await service.get_or_create_product_item(
            category_name="Other Cat",
            item_name="Other Name",
            sku="BULK-SKU-001",
            created_by_id=admin_id,
        )
        assert created is False
        assert item.id == created_item.id
        assert item.sku_code == "BULK-SKU-001"

    async def test_update_item_price_creates_history(self, db_session: AsyncSession):
        """Test that updating item price creates price history."""
        admin_id = await self._create_super_admin(db_session)
        category_id = await self._create_category(db_session, admin_id)
        service = ItemService(db_session)

        item = await service.create_item(
            ItemCreate(
                category_id=category_id,
                sku_code="TEST-001",
                name="Test Item",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )

        # Update price
        await service.update_item(
            item.id,
            ItemUpdate(price=Decimal("150.00")),
            updated_by_id=admin_id,
        )

        # Check price history
        history = await service.get_item_price_history(item.id)
        # Since no transactions, latest entry is updated (not new entry created)
        assert len(history) == 1
        assert history[0].price == Decimal("150.00")

    async def test_list_items_by_category(self, db_session: AsyncSession):
        """Test listing items filtered by category."""
        admin_id = await self._create_super_admin(db_session)
        service = ItemService(db_session)

        cat1 = await service.create_category(
            CategoryCreate(name="Category 1"),
            created_by_id=admin_id,
        )
        cat2 = await service.create_category(
            CategoryCreate(name="Category 2"),
            created_by_id=admin_id,
        )

        await service.create_item(
            ItemCreate(
                category_id=cat1.id,
                sku_code="CAT1-001",
                name="Item in Cat1",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )
        await service.create_item(
            ItemCreate(
                category_id=cat2.id,
                sku_code="CAT2-001",
                name="Item in Cat2",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("200.00"),
            ),
            created_by_id=admin_id,
        )

        items = await service.list_items(category_id=cat1.id)
        assert len(items) == 1
        assert items[0].sku_code == "CAT1-001"


class TestKitService:
    """Tests for Kit operations in ItemService."""

    async def _create_super_admin(self, db_session: AsyncSession) -> int:
        """Helper to create super admin."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="admin@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        return user.id

    async def _create_category_and_items(
        self, db_session: AsyncSession, admin_id: int
    ) -> tuple[int, int, int]:
        """Helper to create category and items."""
        service = ItemService(db_session)
        category = await service.create_category(
            CategoryCreate(name="Test Category"),
            created_by_id=admin_id,
        )

        item1 = await service.create_item(
            ItemCreate(
                category_id=category.id,
                sku_code="ITEM-001",
                name="Item 1",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("50.00"),
            ),
            created_by_id=admin_id,
        )
        item2 = await service.create_item(
            ItemCreate(
                category_id=category.id,
                sku_code="ITEM-002",
                name="Item 2",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("30.00"),
            ),
            created_by_id=admin_id,
        )

        return category.id, item1.id, item2.id

    async def test_create_kit(self, db_session: AsyncSession):
        """Test creating a kit."""
        admin_id = await self._create_super_admin(db_session)
        category_id, item1_id, item2_id = await self._create_category_and_items(db_session, admin_id)
        service = ItemService(db_session)

        kit = await service.create_kit(
            KitCreate(
                category_id=category_id,
                sku_code="KIT-001",
                name="Test Kit",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("70.00"),
                items=[
                    KitItemCreate(item_id=item1_id, quantity=1),
                    KitItemCreate(item_id=item2_id, quantity=2),
                ],
            ),
            created_by_id=admin_id,
        )

        assert kit.id is not None
        assert kit.sku_code == "KIT-001"
        assert kit.name == "Test Kit"
        assert kit.price == Decimal("70.00")
        assert kit.is_active is True

    async def test_create_kit_duplicate_sku(self, db_session: AsyncSession):
        """Test that duplicate kit SKU raises error."""
        admin_id = await self._create_super_admin(db_session)
        category_id, item1_id, _ = await self._create_category_and_items(db_session, admin_id)
        service = ItemService(db_session)

        await service.create_kit(
            KitCreate(
                category_id=category_id,
                sku_code="KIT-001",
                name="Kit 1",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
                items=[KitItemCreate(item_id=item1_id, quantity=1, source_type="item")],
            ),
            created_by_id=admin_id,
        )

        with pytest.raises(DuplicateError):
            await service.create_kit(
                KitCreate(
                    category_id=category_id,
                    sku_code="KIT-001",
                    name="Kit 2",
                    item_type=ItemType.PRODUCT,
                    price_type=PriceType.STANDARD,
                    price=Decimal("200.00"),
                    items=[KitItemCreate(item_id=item1_id, quantity=1, source_type="item")],
                ),
                created_by_id=admin_id,
            )

    async def test_get_kit_with_items(self, db_session: AsyncSession):
        """Test getting kit with items loaded."""
        admin_id = await self._create_super_admin(db_session)
        category_id, item1_id, item2_id = await self._create_category_and_items(db_session, admin_id)
        service = ItemService(db_session)

        kit = await service.create_kit(
            KitCreate(
                category_id=category_id,
                sku_code="KIT-001",
                name="Test Kit",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("70.00"),
                items=[
                    KitItemCreate(item_id=item1_id, quantity=1),
                    KitItemCreate(item_id=item2_id, quantity=2),
                ],
            ),
            created_by_id=admin_id,
        )

        kit = await service.get_kit_by_id(kit.id, with_items=True)
        assert len(kit.kit_items) == 2

        quantities = {ki.item_id: ki.quantity for ki in kit.kit_items}
        assert quantities[item1_id] == 1
        assert quantities[item2_id] == 2

    async def test_update_kit_items(self, db_session: AsyncSession):
        """Test updating kit items."""
        admin_id = await self._create_super_admin(db_session)
        category_id, item1_id, item2_id = await self._create_category_and_items(db_session, admin_id)
        service = ItemService(db_session)

        kit = await service.create_kit(
            KitCreate(
                category_id=category_id,
                sku_code="KIT-001",
                name="Test Kit",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("70.00"),
                items=[KitItemCreate(item_id=item1_id, quantity=1, source_type="item")],
            ),
            created_by_id=admin_id,
        )

        # Update to different items
        from src.modules.items.schemas import KitItemUpdate

        await service.update_kit(
            kit.id,
            KitUpdate(items=[KitItemUpdate(item_id=item2_id, quantity=3)]),
            updated_by_id=admin_id,
        )

        kit = await service.get_kit_by_id(kit.id, with_items=True)
        assert len(kit.kit_items) == 1
        assert kit.kit_items[0].item_id == item2_id
        assert kit.kit_items[0].quantity == 3

    async def test_create_kit_with_variant_component(self, db_session: AsyncSession):
        """Test creating a kit with a variant component (source_type='variant')."""
        admin_id = await self._create_super_admin(db_session)
        category_id, item1_id, item2_id = await self._create_category_and_items(db_session, admin_id)
        service = ItemService(db_session)

        # Create variant
        from src.modules.items.schemas import ItemVariantCreate
        variant = await service.create_variant(
            ItemVariantCreate(name="Shirt Sizes", item_ids=[item1_id, item2_id]),
            created_by_id=admin_id,
        )

        # Create kit with variant component
        from src.modules.items.schemas import KitItemCreate

        kit = await service.create_kit(
            KitCreate(
                category_id=category_id,
                sku_code="KIT-VARIANT",
                name="Kit with Variant",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
                items=[
                    KitItemCreate(
                        source_type="variant",
                        variant_id=variant.id,
                        default_item_id=item1_id,
                        quantity=1,
                    )
                ],
            ),
            created_by_id=admin_id,
        )

        kit = await service.get_kit_by_id(kit.id, with_items=True)
        assert len(kit.kit_items) == 1
        kit_item = kit.kit_items[0]
        assert kit_item.source_type == "variant"
        assert kit_item.variant_id == variant.id
        assert kit_item.default_item_id == item1_id
        assert kit_item.item_id is None  # Should be None for variant source_type


class TestItemEndpoints:
    """Tests for item API endpoints."""

    async def _get_admin_token(self, client: AsyncClient, db_session: AsyncSession) -> str:
        """Helper to get admin token."""
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="admin@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Password123"},
        )
        return response.json()["data"]["access_token"]

    async def test_create_category(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a category via API."""
        token = await self._get_admin_token(client, db_session)

        response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Category"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Test Category"

    async def test_create_item(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating an item via API."""
        token = await self._get_admin_token(client, db_session)

        # Create category first
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        # Create item
        response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "TEST-001",
                "name": "Test Item",
                "item_type": "product",
                "price_type": "standard",
                "price": "100.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["sku_code"] == "TEST-001"
        assert data["data"]["price"] == "100.00"

    async def test_list_items(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing items via API."""
        token = await self._get_admin_token(client, db_session)

        # Create category and item
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "TEST-001",
                "name": "Test Item",
                "item_type": "product",
                "price_type": "standard",
                "price": "100.00",
            },
        )

        # List items
        response = await client.get(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["sku_code"] == "TEST-001"

    async def test_create_kit(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a kit via API."""
        token = await self._get_admin_token(client, db_session)

        # Create category
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        # Create item
        item_response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "ITEM-001",
                "name": "Test Item",
                "item_type": "product",
                "price_type": "standard",
                "price": "50.00",
            },
        )
        item_id = item_response.json()["data"]["id"]

        # Create kit
        response = await client.post(
            "/api/v1/items/kits",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "KIT-001",
                "name": "Test Kit",
                "item_type": "product",
                "price_type": "standard",
                "price": "45.00",
                "items": [{"item_id": item_id, "quantity": 1, "source_type": "item"}],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["sku_code"] == "KIT-001"
        assert data["data"]["price"] == "45.00"
        assert len(data["data"]["items"]) == 1

    async def test_create_editable_kit(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating an editable kit with is_editable_components=True."""
        token = await self._get_admin_token(client, db_session)

        # Create category
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Uniform Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        # Create items
        item1_response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "SHIRT-S",
                "name": "Shirt Size S",
                "item_type": "product",
                "price_type": "standard",
                "price": "50.00",
            },
        )
        item1_id = item1_response.json()["data"]["id"]

        item2_response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "PANTS-S",
                "name": "Pants Size S",
                "item_type": "product",
                "price_type": "standard",
                "price": "40.00",
            },
        )
        item2_id = item2_response.json()["data"]["id"]

        # Create editable kit
        response = await client.post(
            "/api/v1/items/kits",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "UNIFORM-S",
                "name": "Uniform Kit S",
                "item_type": "product",
                "price_type": "standard",
                "price": "90.00",
                "is_editable_components": True,
                "items": [
                    {"item_id": item1_id, "quantity": 1, "source_type": "item"},
                    {"item_id": item2_id, "quantity": 1, "source_type": "item"},
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_editable_components"] is True
        assert len(data["data"]["items"]) == 2
