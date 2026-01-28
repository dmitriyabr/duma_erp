"""Tests for Inventory module."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.inventory.models import IssuanceType, MovementType, RecipientType
from src.modules.inventory.schemas import (
    AdjustStockRequest,
    InternalIssuanceCreate,
    IssuanceItemCreate,
    IssueStockRequest,
    ReceiveStockRequest,
)
from src.modules.inventory.service import InventoryService
from src.modules.items.models import ItemType, PriceType
from src.modules.items.schemas import CategoryCreate, ItemCreate
from src.modules.items.service import ItemService


class TestInventoryService:
    """Tests for InventoryService."""

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

    async def _create_product_item(self, db_session: AsyncSession, admin_id: int) -> int:
        """Helper to create a product item."""
        item_service = ItemService(db_session)

        # Create category
        category = await item_service.create_category(
            CategoryCreate(name="Test Category"),
            created_by_id=admin_id,
        )

        # Create product item
        item = await item_service.create_item(
            ItemCreate(
                category_id=category.id,
                sku_code="PROD-001",
                name="Test Product",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )
        return item.id

    async def test_receive_stock(self, db_session: AsyncSession):
        """Test receiving stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        movement = await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
                notes="Initial stock",
            ),
            received_by_id=admin_id,
        )

        assert movement.id is not None
        assert movement.movement_type == MovementType.RECEIPT.value
        assert movement.quantity == 100
        assert movement.quantity_after == 100

        # Check stock
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 100
        assert stock.average_cost == Decimal("50.00")

    async def test_receive_stock_updates_average_cost(self, db_session: AsyncSession):
        """Test that receiving stock updates weighted average cost."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # First receipt: 100 units at 50.00
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Second receipt: 100 units at 70.00
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("70.00"),
            ),
            received_by_id=admin_id,
        )

        # Average should be (100*50 + 100*70) / 200 = 60.00
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 200
        assert stock.average_cost == Decimal("60.00")

    async def test_issue_stock(self, db_session: AsyncSession):
        """Test issuing stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive stock first
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Issue stock
        movement = await service.issue_stock(
            IssueStockRequest(
                item_id=item_id,
                quantity=30,
                notes="Issued to student",
            ),
            issued_by_id=admin_id,
        )

        assert movement.movement_type == MovementType.ISSUE.value
        assert movement.quantity == -30  # Negative for outgoing
        assert movement.quantity_after == 70

        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 70

    async def test_issue_stock_insufficient(self, db_session: AsyncSession):
        """Test that issuing more than available raises error."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive stock first
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=10,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Try to issue more than available
        with pytest.raises(ValidationError) as exc_info:
            await service.issue_stock(
                IssueStockRequest(
                    item_id=item_id,
                    quantity=20,
                ),
                issued_by_id=admin_id,
            )
        assert "Insufficient stock" in str(exc_info.value)

    async def test_adjust_stock_positive(self, db_session: AsyncSession):
        """Test positive stock adjustment."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive initial stock
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=50,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Positive adjustment
        movement = await service.adjust_stock(
            AdjustStockRequest(
                item_id=item_id,
                quantity=10,
                reason="Found extra units during inventory count",
            ),
            adjusted_by_id=admin_id,
        )

        assert movement.movement_type == MovementType.ADJUSTMENT.value
        assert movement.quantity == 10
        assert movement.quantity_after == 60

    async def test_adjust_stock_negative(self, db_session: AsyncSession):
        """Test negative stock adjustment (write-off)."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive initial stock
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=50,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Negative adjustment
        movement = await service.adjust_stock(
            AdjustStockRequest(
                item_id=item_id,
                quantity=-5,
                reason="Damaged items",
            ),
            adjusted_by_id=admin_id,
        )

        assert movement.quantity == -5
        assert movement.quantity_after == 45

    async def test_adjust_stock_negative_exceeds_available(self, db_session: AsyncSession):
        """Test that negative adjustment cannot exceed available quantity."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive initial stock
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=10,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Try to adjust more than available
        with pytest.raises(ValidationError) as exc_info:
            await service.adjust_stock(
                AdjustStockRequest(
                    item_id=item_id,
                    quantity=-20,
                    reason="Write-off",
                ),
                adjusted_by_id=admin_id,
            )
        assert "negative stock" in str(exc_info.value)

    async def test_reserve_stock(self, db_session: AsyncSession):
        """Test reserving stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive stock
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Reserve stock
        movement = await service.reserve_stock(
            item_id=item_id,
            quantity=30,
            reference_type="invoice",
            reference_id=1,
            reserved_by_id=admin_id,
        )

        assert movement.movement_type == MovementType.RESERVE.value

        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 100  # Unchanged
        assert stock.quantity_reserved == 30
        assert stock.quantity_available == 70

    async def test_issue_reserved_stock(self, db_session: AsyncSession):
        """Test issuing reserved stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive and reserve
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )
        await service.reserve_stock(
            item_id=item_id,
            quantity=30,
            reference_type="invoice",
            reference_id=1,
            reserved_by_id=admin_id,
        )

        # Issue reserved stock
        movement = await service.issue_reserved_stock(
            item_id=item_id,
            quantity=20,
            reference_type="issuance",
            reference_id=1,
            issued_by_id=admin_id,
        )

        assert movement.movement_type == MovementType.ISSUE.value

        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 80  # 100 - 20
        assert stock.quantity_reserved == 10  # 30 - 20
        assert stock.quantity_available == 70  # 80 - 10

    async def test_cannot_stock_service_item(self, db_session: AsyncSession):
        """Test that service items cannot have stock."""
        admin_id = await self._create_super_admin(db_session)
        item_service = ItemService(db_session)

        # Create service item
        category = await item_service.create_category(
            CategoryCreate(name="Services"),
            created_by_id=admin_id,
        )
        item = await item_service.create_item(
            ItemCreate(
                category_id=category.id,
                sku_code="SERVICE-001",
                name="Service Item",
                item_type=ItemType.SERVICE,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )

        # Try to receive stock for service
        inventory_service = InventoryService(db_session)
        with pytest.raises(ValidationError) as exc_info:
            await inventory_service.receive_stock(
                ReceiveStockRequest(
                    item_id=item.id,
                    quantity=10,
                    unit_cost=Decimal("50.00"),
                ),
                received_by_id=admin_id,
            )
        assert "not a product" in str(exc_info.value)

    async def test_list_movements(self, db_session: AsyncSession):
        """Test listing stock movements."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Create multiple movements
        await service.receive_stock(
            ReceiveStockRequest(item_id=item_id, quantity=100, unit_cost=Decimal("50.00")),
            received_by_id=admin_id,
        )
        await service.issue_stock(
            IssueStockRequest(item_id=item_id, quantity=20),
            issued_by_id=admin_id,
        )
        await service.adjust_stock(
            AdjustStockRequest(item_id=item_id, quantity=-5, reason="Damaged"),
            adjusted_by_id=admin_id,
        )

        movements, total = await service.get_movements(item_id=item_id)
        assert total == 3
        assert len(movements) == 3

        # Most recent first
        assert movements[0].movement_type == MovementType.ADJUSTMENT.value
        assert movements[1].movement_type == MovementType.ISSUE.value
        assert movements[2].movement_type == MovementType.RECEIPT.value

    async def test_export_stock_to_csv(self, db_session: AsyncSession):
        """Test export_stock_to_csv returns CSV with header and rows."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        await service.receive_stock(
            ReceiveStockRequest(item_id=item_id, quantity=50, unit_cost=Decimal("10.00")),
            received_by_id=admin_id,
        )
        await db_session.commit()

        csv_bytes = await service.export_stock_to_csv()
        assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        text = csv_bytes.decode("utf-8-sig")
        lines = text.strip().split("\r\n") if "\r\n" in text else text.strip().split("\n")
        assert lines[0] == "category,item_name,sku,quantity,unit_cost"
        assert len(lines) >= 2  # header + at least one row

    async def test_bulk_upload_from_csv_update(self, db_session: AsyncSession):
        """Test bulk_upload_from_csv in update mode sets quantity from CSV."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        await service.receive_stock(
            ReceiveStockRequest(item_id=item_id, quantity=10, unit_cost=Decimal("5.00")),
            received_by_id=admin_id,
        )
        await db_session.commit()

        csv_content = "category,item_name,sku,quantity\nTest Category,Test Product,PROD-001,25\n"
        result = await service.bulk_upload_from_csv(csv_content.encode("utf-8"), "update", admin_id)

        assert result["rows_processed"] == 1
        assert result["items_created"] == 0
        assert len(result["errors"]) == 0
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 25

    async def test_bulk_upload_from_csv_overwrite(self, db_session: AsyncSession):
        """Test bulk_upload_from_csv in overwrite mode zeros then sets from CSV."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        await service.receive_stock(
            ReceiveStockRequest(item_id=item_id, quantity=100, unit_cost=Decimal("10.00")),
            received_by_id=admin_id,
        )
        await db_session.commit()

        csv_content = "category,item_name,sku,quantity\nTest Category,Test Product,PROD-001,30\n"
        result = await service.bulk_upload_from_csv(csv_content.encode("utf-8"), "overwrite", admin_id)

        assert result["rows_processed"] == 1
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 30

    async def test_bulk_upload_from_csv_overwrite_fails_with_reserved(self, db_session: AsyncSession):
        """Test overwrite mode raises when any product has reserved stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        await service.receive_stock(
            ReceiveStockRequest(item_id=item_id, quantity=50, unit_cost=Decimal("5.00")),
            received_by_id=admin_id,
        )
        await service.reserve_stock(
            item_id=item_id,
            quantity=10,
            reference_type="invoice",
            reference_id=1,
            reserved_by_id=admin_id,
        )
        await db_session.commit()

        csv_content = "category,item_name,sku,quantity\nTest Category,Test Product,PROD-001,20\n"
        with pytest.raises(ValidationError) as exc_info:
            await service.bulk_upload_from_csv(csv_content.encode("utf-8"), "overwrite", admin_id)
        assert "reserved" in str(exc_info.value).lower()

    async def test_bulk_upload_from_csv_creates_items(self, db_session: AsyncSession):
        """Test bulk upload creates new category and product when not present."""
        admin_id = await self._create_super_admin(db_session)
        service = InventoryService(db_session)

        csv_content = (
            "category,item_name,sku,quantity\n"
            "New Category,New Product,,15\n"
        )
        result = await service.bulk_upload_from_csv(csv_content.encode("utf-8"), "update", admin_id)

        assert result["rows_processed"] == 1
        assert result["items_created"] == 1
        stocks, _ = await service.list_stock(include_zero=True)
        names = [s.item.name for s in stocks if s.item]
        assert "New Product" in names
        stock = next(s for s in stocks if s.item and s.item.name == "New Product")
        assert stock.quantity_on_hand == 15

    async def test_bulk_upload_from_csv_invalid_quantity_errors(self, db_session: AsyncSession):
        """Test bulk upload collects errors for invalid quantity rows."""
        admin_id = await self._create_super_admin(db_session)
        service = InventoryService(db_session)

        csv_content = (
            "category,item_name,quantity\n"
            "Cat A,Item A,10\n"
            "Cat B,Item B,not_a_number\n"
            "Cat C,Item C,-1\n"
        )
        result = await service.bulk_upload_from_csv(csv_content.encode("utf-8"), "update", admin_id)

        assert result["rows_processed"] == 1
        assert len(result["errors"]) >= 2
        row_messages = {e["row"]: e["message"] for e in result["errors"]}
        assert any("invalid quantity" in row_messages.get(r, "") for r in row_messages)
        assert any(">= 0" in row_messages.get(r, "") or "must be" in row_messages.get(r, "") for r in row_messages)


class TestInventoryEndpoints:
    """Tests for inventory API endpoints."""

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

    async def _create_product_item(
        self, client: AsyncClient, token: str
    ) -> int:
        """Helper to create a product item via API."""
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
                "sku_code": "PROD-001",
                "name": "Test Product",
                "item_type": "product",
                "price_type": "standard",
                "price": "100.00",
            },
        )
        return item_response.json()["data"]["id"]

    async def test_receive_stock_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test receive stock via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        response = await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "item_id": item_id,
                "quantity": 100,
                "unit_cost": "50.00",
                "notes": "Initial stock",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["quantity"] == 100
        assert data["data"]["quantity_after"] == 100

    async def test_get_stock_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test get stock via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        # Receive stock
        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 100, "unit_cost": "50.00"},
        )

        # Get stock
        response = await client.get(
            f"/api/v1/inventory/stock/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["quantity_on_hand"] == 100
        assert data["data"]["average_cost"] == "50.00"

    async def test_list_stock_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test list stock via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        # Receive stock
        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 100, "unit_cost": "50.00"},
        )

        # List stock
        response = await client.get(
            "/api/v1/inventory/stock",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1

    async def test_export_stock_csv_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test GET /inventory/bulk-upload/export returns CSV."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)
        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 50, "unit_cost": "10.00"},
        )

        response = await client.get(
            "/api/v1/inventory/bulk-upload/export",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "").lower()
        content = response.content
        assert content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        assert b"category,item_name,sku,quantity,unit_cost" in content

    async def test_bulk_upload_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test POST /inventory/bulk-upload with CSV file and mode."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)
        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 10, "unit_cost": "5.00"},
        )

        csv_content = b"category,item_name,sku,quantity\nTest Category,Test Product,PROD-001,22\n"
        response = await client.post(
            "/api/v1/inventory/bulk-upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"mode": "update"},
            files={"file": ("stock.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["rows_processed"] == 1
        assert data["data"]["items_created"] == 0
        assert len(data["data"]["errors"]) == 0
        stock_resp = await client.get(
            f"/api/v1/inventory/stock/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stock_resp.json()["data"]["quantity_on_hand"] == 22

    async def test_adjust_stock_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test adjust stock via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        # Receive stock
        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 100, "unit_cost": "50.00"},
        )

        # Adjust stock
        response = await client.post(
            "/api/v1/inventory/adjust",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "item_id": item_id,
                "quantity": -10,
                "reason": "Damaged items",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["quantity"] == -10
        assert data["data"]["quantity_after"] == 90

    async def test_writeoff_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test write-off via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 20, "unit_cost": "50.00"},
        )

        response = await client.post(
            "/api/v1/inventory/writeoff",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [
                    {
                        "item_id": item_id,
                        "quantity": 5,
                        "reason_category": "damage",
                        "reason_detail": "Broken",
                    }
                ]
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["movements"][0]["quantity"] == -5

    async def test_inventory_count_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test inventory count via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 20, "unit_cost": "50.00"},
        )

        response = await client.post(
            "/api/v1/inventory/inventory-count",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [
                    {
                        "item_id": item_id,
                        "actual_quantity": 18,
                    }
                ]
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["adjustments_created"] == 1
        assert data["total_variance"] == -2


class TestIssuanceService:
    """Tests for Issuance operations in InventoryService."""

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

    async def _create_product_item(self, db_session: AsyncSession, admin_id: int) -> int:
        """Helper to create a product item."""
        item_service = ItemService(db_session)

        category = await item_service.create_category(
            CategoryCreate(name="Test Category"),
            created_by_id=admin_id,
        )

        item = await item_service.create_item(
            ItemCreate(
                category_id=category.id,
                sku_code="PROD-001",
                name="Test Product",
                item_type=ItemType.PRODUCT,
                price_type=PriceType.STANDARD,
                price=Decimal("100.00"),
            ),
            created_by_id=admin_id,
        )
        return item.id

    async def test_create_internal_issuance(self, db_session: AsyncSession):
        """Test creating an internal issuance."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive stock first
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Create issuance
        issuance = await service.create_internal_issuance(
            InternalIssuanceCreate(
                recipient_type=RecipientType.EMPLOYEE,
                recipient_id=admin_id,
                recipient_name="Admin User",
                items=[IssuanceItemCreate(item_id=item_id, quantity=10)],
                notes="Test issuance",
            ),
            issued_by_id=admin_id,
        )

        assert issuance.id is not None
        assert issuance.issuance_number.startswith("ISS-")
        assert issuance.issuance_type == IssuanceType.INTERNAL.value
        assert issuance.recipient_type == RecipientType.EMPLOYEE.value
        assert issuance.status == "completed"

        # Check stock was reduced
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 90

    async def test_create_internal_issuance_insufficient_stock(self, db_session: AsyncSession):
        """Test that issuance fails with insufficient stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive limited stock
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=5,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Try to issue more than available
        with pytest.raises(ValidationError) as exc_info:
            await service.create_internal_issuance(
                InternalIssuanceCreate(
                    recipient_type=RecipientType.EMPLOYEE,
                    recipient_id=admin_id,
                    recipient_name="Admin User",
                    items=[IssuanceItemCreate(item_id=item_id, quantity=10)],
                ),
                issued_by_id=admin_id,
            )
        assert "Insufficient stock" in str(exc_info.value)

    async def test_cancel_issuance(self, db_session: AsyncSession):
        """Test cancelling an issuance returns stock."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive stock and create issuance
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        issuance = await service.create_internal_issuance(
            InternalIssuanceCreate(
                recipient_type=RecipientType.DEPARTMENT,
                recipient_id=1,
                recipient_name="Kitchen",
                items=[IssuanceItemCreate(item_id=item_id, quantity=20)],
            ),
            issued_by_id=admin_id,
        )

        # Verify stock reduced
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 80

        # Cancel issuance
        cancelled = await service.cancel_issuance(issuance.id, admin_id)
        assert cancelled.status == "cancelled"

        # Verify stock returned
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 100

    async def test_list_issuances(self, db_session: AsyncSession):
        """Test listing issuances."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        # Receive stock
        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        # Create multiple issuances
        await service.create_internal_issuance(
            InternalIssuanceCreate(
                recipient_type=RecipientType.EMPLOYEE,
                recipient_id=admin_id,
                recipient_name="Employee 1",
                items=[IssuanceItemCreate(item_id=item_id, quantity=5)],
            ),
            issued_by_id=admin_id,
        )
        await service.create_internal_issuance(
            InternalIssuanceCreate(
                recipient_type=RecipientType.DEPARTMENT,
                recipient_id=1,
                recipient_name="Kitchen",
                items=[IssuanceItemCreate(item_id=item_id, quantity=10)],
            ),
            issued_by_id=admin_id,
        )

        # List all
        issuances, total = await service.list_issuances()
        assert total == 2

        # Filter by recipient type (recipient_name resolved from User on create)
        issuances, total = await service.list_issuances(
            recipient_type=RecipientType.EMPLOYEE
        )
        assert total == 1
        assert issuances[0].recipient_name == "Admin"

    async def test_create_internal_issuance_recipient_other(self, db_session: AsyncSession):
        """Test internal issuance with recipient_type=other (free text, no recipient_id)."""
        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        issuance = await service.create_internal_issuance(
            InternalIssuanceCreate(
                recipient_type=RecipientType.OTHER,
                recipient_name="Kitchen",
                items=[IssuanceItemCreate(item_id=item_id, quantity=5)],
            ),
            issued_by_id=admin_id,
        )

        assert issuance.recipient_type == RecipientType.OTHER.value
        assert issuance.recipient_id is None
        assert issuance.recipient_name == "Kitchen"
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 95

    async def test_create_internal_issuance_recipient_student(self, db_session: AsyncSession):
        """Test internal issuance with recipient_type=student (manual issue to student)."""
        from src.modules.students.models import Grade, Student, StudentStatus

        admin_id = await self._create_super_admin(db_session)
        item_id = await self._create_product_item(db_session, admin_id)
        service = InventoryService(db_session)

        grade = Grade(code="G1", name="Grade 1", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()
        student = Student(
            student_number="STU-2026-000001",
            first_name="John",
            last_name="Doe",
            gender="male",
            guardian_name="Jane Doe",
            guardian_phone="+254700000000",
            grade_id=grade.id,
            status=StudentStatus.ACTIVE.value,
            created_by_id=admin_id,
        )
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(student)

        await service.receive_stock(
            ReceiveStockRequest(
                item_id=item_id,
                quantity=100,
                unit_cost=Decimal("50.00"),
            ),
            received_by_id=admin_id,
        )

        issuance = await service.create_internal_issuance(
            InternalIssuanceCreate(
                recipient_type=RecipientType.STUDENT,
                recipient_id=student.id,
                recipient_name="John Doe",
                items=[IssuanceItemCreate(item_id=item_id, quantity=3)],
            ),
            issued_by_id=admin_id,
        )

        assert issuance.recipient_type == RecipientType.STUDENT.value
        assert issuance.recipient_id == student.id
        assert issuance.recipient_name == "John Doe"  # first_name + last_name from service
        stock = await service.get_stock_by_item_id(item_id)
        assert stock.quantity_on_hand == 97


class TestIssuanceEndpoints:
    """Tests for issuance API endpoints."""

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

    async def _create_product_and_stock(
        self, client: AsyncClient, token: str
    ) -> int:
        """Helper to create product and receive stock."""
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
                "sku_code": "PROD-001",
                "name": "Test Product",
                "item_type": "product",
                "price_type": "standard",
                "price": "100.00",
            },
        )
        item_id = item_response.json()["data"]["id"]

        # Receive stock
        await client.post(
            "/api/v1/inventory/receive",
            headers={"Authorization": f"Bearer {token}"},
            json={"item_id": item_id, "quantity": 100, "unit_cost": "50.00"},
        )

        return item_id

    async def test_create_issuance_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating issuance via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_and_stock(client, token)

        response = await client.post(
            "/api/v1/inventory/issuances",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "recipient_type": "employee",
                "recipient_id": 1,
                "recipient_name": "Test Employee",
                "items": [{"item_id": item_id, "quantity": 10}],
                "notes": "Test issuance via API",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["issuance_number"].startswith("ISS-")
        assert len(data["data"]["items"]) == 1

    async def test_create_issuance_endpoint_recipient_other(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating issuance via API with recipient_type=other (no recipient_id)."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_and_stock(client, token)

        response = await client.post(
            "/api/v1/inventory/issuances",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "recipient_type": "other",
                "recipient_name": "Kitchen",
                "items": [{"item_id": item_id, "quantity": 5}],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["recipient_type"] == "other"
        assert data["data"]["recipient_id"] is None
        assert data["data"]["recipient_name"] == "Kitchen"

    async def test_list_issuances_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing issuances via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_and_stock(client, token)

        # Create issuance
        await client.post(
            "/api/v1/inventory/issuances",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "recipient_type": "department",
                "recipient_id": 1,
                "recipient_name": "Kitchen",
                "items": [{"item_id": item_id, "quantity": 5}],
            },
        )

        # List issuances
        response = await client.get(
            "/api/v1/inventory/issuances",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1

    async def test_cancel_issuance_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test cancelling issuance via API."""
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_and_stock(client, token)

        # Create issuance
        create_response = await client.post(
            "/api/v1/inventory/issuances",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "recipient_type": "employee",
                "recipient_id": 1,
                "recipient_name": "Employee",
                "items": [{"item_id": item_id, "quantity": 10}],
            },
        )
        issuance_id = create_response.json()["data"]["id"]

        # Cancel
        response = await client.post(
            f"/api/v1/inventory/issuances/{issuance_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "cancelled"
