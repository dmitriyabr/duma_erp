from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


class TestGoodsReceivedEndpoints:
    """Tests for GRN endpoints."""

    async def _get_admin_token(
        self, client: AsyncClient, db_session: AsyncSession, role: UserRole = UserRole.ADMIN
    ) -> str:
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email=f"{role.value}-grn@test.com",
            password="Password123",
            full_name="GRN User",
            role=role,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": f"{role.value}-grn@test.com", "password": "Password123"},
        )
        return response.json()["data"]["access_token"]

    async def _create_product_item(self, client: AsyncClient, token: str) -> int:
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "GRN Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        item_response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "GRN-001",
                "name": "GRN Item",
                "item_type": "product",
                "price_type": "standard",
                "price": "25.00",
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

    async def _create_po(
        self,
        client: AsyncClient,
        token: str,
        item_id: int,
        track_to_warehouse: bool = True,
        quantity_expected: int = 3,
    ) -> dict:
        purpose_id = await self._create_payment_purpose(client, token)
        response = await client.post(
            "/api/v1/procurement/purchase-orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_name": "GRN Supplier",
                "track_to_warehouse": track_to_warehouse,
                "purpose_id": purpose_id,
                "lines": [
                    {
                        "item_id": item_id,
                        "description": "GRN Item",
                        "quantity_expected": quantity_expected,
                        "unit_price": "25.00",
                    }
                ],
            },
        )
        return response.json()["data"]

    async def test_create_and_approve_grn(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_admin_token(client, db_session, role=UserRole.SUPER_ADMIN)
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(client, token, item_id, track_to_warehouse=True)
        po_id = po_data["id"]
        po_line_id = po_data["lines"][0]["id"]

        grn_response = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "lines": [
                    {"po_line_id": po_line_id, "quantity_received": 2},
                ],
            },
        )
        assert grn_response.status_code == 201
        grn_id = grn_response.json()["data"]["id"]

        approve_response = await client.post(
            f"/api/v1/procurement/grns/{grn_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["data"]["status"] == "approved"

        stock_response = await client.get(
            f"/api/v1/inventory/stock/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stock_response.status_code == 200
        assert stock_response.json()["data"]["quantity_on_hand"] == 2

    async def test_admin_cannot_approve_own_grn(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        setup_token = await self._get_admin_token(
            client, db_session, role=UserRole.SUPER_ADMIN
        )
        admin_token = await self._get_admin_token(
            client, db_session, role=UserRole.ADMIN
        )
        item_id = await self._create_product_item(client, setup_token)
        po_data = await self._create_po(client, setup_token, item_id)
        po_id = po_data["id"]
        po_line_id = po_data["lines"][0]["id"]

        grn_response = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "po_id": po_id,
                "lines": [
                    {"po_line_id": po_line_id, "quantity_received": 1},
                ],
            },
        )
        grn_id = grn_response.json()["data"]["id"]

        approve_response = await client.post(
            f"/api/v1/procurement/grns/{grn_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approve_response.status_code == 422

    async def test_grn_without_warehouse_tracking(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(client, db_session, role=UserRole.SUPER_ADMIN)
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(client, token, item_id, track_to_warehouse=False)
        po_id = po_data["id"]
        po_line_id = po_data["lines"][0]["id"]

        grn_response = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "lines": [
                    {"po_line_id": po_line_id, "quantity_received": 1},
                ],
            },
        )
        grn_id = grn_response.json()["data"]["id"]

        approve_response = await client.post(
            f"/api/v1/procurement/grns/{grn_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve_response.status_code == 200

        stock_response = await client.get(
            f"/api/v1/inventory/stock/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stock_response.status_code == 200
        assert stock_response.json()["data"]["quantity_on_hand"] == 0
