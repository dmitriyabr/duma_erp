from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


class TestPurchaseOrderEndpoints:
    """Tests for purchase order endpoints."""

    async def _get_admin_token(self, client: AsyncClient, db_session: AsyncSession) -> str:
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="admin-proc@test.com",
            password="Password123",
            full_name="Admin Proc",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin-proc@test.com", "password": "Password123"},
        )
        return response.json()["data"]["access_token"]

    async def _create_product_item(self, client: AsyncClient, token: str) -> int:
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Proc Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        item_response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "PROC-001",
                "name": "Proc Item",
                "item_type": "product",
                "price_type": "standard",
                "price": "50.00",
            },
        )
        return item_response.json()["data"]["id"]

    async def _create_payment_purpose(self, client: AsyncClient, token: str) -> int:
        response = await client.post(
            "/api/v1/procurement/payment-purposes",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Procurement"},
        )
        return response.json()["data"]["id"]

    async def test_create_purchase_order(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)
        purpose_id = await self._create_payment_purpose(client, token)

        response = await client.post(
            "/api/v1/procurement/purchase-orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_name": "ABC Supplies",
                "supplier_contact": "+254700000000",
                "purpose_id": purpose_id,
                "lines": [
                    {
                        "item_id": item_id,
                        "description": "Test Item",
                        "quantity_expected": 2,
                        "unit_price": "50.00",
                    }
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] == "draft"
        assert data["expected_total"] == "100.00"
        assert data["forecast_debt"] == "100.00"

    async def test_submit_purchase_order(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)
        purpose_id = await self._create_payment_purpose(client, token)

        response = await client.post(
            "/api/v1/procurement/purchase-orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_name": "ABC Supplies",
                "purpose_id": purpose_id,
                "lines": [
                    {
                        "item_id": item_id,
                        "description": "Test Item",
                        "quantity_expected": 1,
                        "unit_price": "50.00",
                    }
                ],
            },
        )
        po_id = response.json()["data"]["id"]

        submit_response = await client.post(
            f"/api/v1/procurement/purchase-orders/{po_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert submit_response.status_code == 200
        assert submit_response.json()["data"]["status"] == "ordered"

    async def test_close_purchase_order(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)
        purpose_id = await self._create_payment_purpose(client, token)

        response = await client.post(
            "/api/v1/procurement/purchase-orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_name": "ABC Supplies",
                "purpose_id": purpose_id,
                "lines": [
                    {
                        "item_id": item_id,
                        "description": "Test Item",
                        "quantity_expected": 3,
                        "unit_price": "10.00",
                    }
                ],
            },
        )
        po_id = response.json()["data"]["id"]

        close_response = await client.post(
            f"/api/v1/procurement/purchase-orders/{po_id}/close",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert close_response.status_code == 200
        data = close_response.json()["data"]
        assert data["status"] == "closed"
        assert data["expected_total"] == "0.00"
        assert data["lines"][0]["quantity_cancelled"] == 3

    async def test_parse_po_lines_from_csv(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(client, db_session)
        await self._create_product_item(client, token)

        csv_content = (
            "sku,item_name,quantity_expected,unit_price\n"
            "PROC-001,Proc Item,10,25.50\n"
            ",Widget B (custom),5,10.00\n"
        )
        response = await client.post(
            "/api/v1/procurement/purchase-orders/bulk-upload/parse-lines",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("lines.csv", csv_content.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        lines = data["data"]["lines"]
        assert len(lines) == 2
        assert lines[0]["item_id"] is not None
        assert lines[0]["description"] == "Proc Item"
        assert lines[0]["quantity_expected"] == 10
        assert str(lines[0]["unit_price"]) == "25.50"
        assert lines[1]["item_id"] is None
        assert lines[1]["description"] == "Widget B (custom)"
        assert lines[1]["quantity_expected"] == 5

    async def test_parse_po_lines_with_sku_links_item(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(client, db_session)
        item_id = await self._create_product_item(client, token)

        csv_content = (
            "sku,item_name,quantity_expected,unit_price\n"
            "PROC-001,,2,50.00\n"
        )
        response = await client.post(
            "/api/v1/procurement/purchase-orders/bulk-upload/parse-lines",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("lines.csv", csv_content.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["lines"]) == 1
        assert data["data"]["lines"][0]["item_id"] == item_id
        assert data["data"]["lines"][0]["description"] == "Proc Item"

    async def test_parse_po_lines_validation_errors(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(client, db_session)

        csv_content = (
            "sku,item_name,quantity_expected,unit_price\n"
            ",Some item,,10.00\n"
        )
        response = await client.post(
            "/api/v1/procurement/purchase-orders/bulk-upload/parse-lines",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("lines.csv", csv_content.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["errors"]) >= 1
        messages = [e["message"] for e in data["data"]["errors"]]
        assert any("quantity" in m.lower() for m in messages)

    async def test_po_template_includes_example_and_items(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(client, db_session)
        await self._create_product_item(client, token)

        response = await client.get(
            "/api/v1/procurement/purchase-orders/bulk-upload/template",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        text = response.text
        assert "sku,item_name,quantity_expected,unit_price" in text or "sku," in text
        assert "EXAMPLE-001" in text
        assert "Example product" in text
        assert "PROC-001" in text
        assert "Proc Item" in text
