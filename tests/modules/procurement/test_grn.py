from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.inventory.models import MovementType, StockMovement


class TestGoodsReceivedEndpoints:
    """Tests for GRN endpoints."""

    async def _get_admin_token(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        role: UserRole = UserRole.ADMIN,
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
            json={
                "email": f"{role.value}-grn@test.com",
                "password": "Password123",
            },
        )
        return response.json()["data"]["access_token"]

    async def _create_product_item(
        self, client: AsyncClient, token: str
    ) -> int:
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

    async def _create_payment_purpose(
        self, client: AsyncClient, token: str
    ) -> int:
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

    async def test_create_and_approve_grn(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(
            client, db_session, role=UserRole.SUPER_ADMIN
        )
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(
            client, token, item_id, track_to_warehouse=True
        )
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

    async def test_superadmin_can_rollback_po_receiving(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(
            client, db_session, role=UserRole.SUPER_ADMIN
        )
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(
            client,
            token,
            item_id,
            track_to_warehouse=True,
            quantity_expected=2,
        )
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

        payment_response = await client.post(
            "/api/v1/procurement/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "payment_date": "2026-02-01",
                "amount": "25.00",
                "payment_method": "bank_transfer",
                "proof_text": "Advance payment before receiving rollback",
            },
        )
        assert payment_response.status_code == 201

        stock_response = await client.get(
            f"/api/v1/inventory/stock/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stock_response.status_code == 200
        assert stock_response.json()["data"]["quantity_on_hand"] == 2

        rollback_response = await client.post(
            f"/api/v1/procurement/grns/{grn_id}/rollback",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Wrong items received"},
        )
        assert rollback_response.status_code == 200
        assert rollback_response.json()["data"]["status"] == "cancelled"

        po_after = await client.get(
            f"/api/v1/procurement/purchase-orders/{po_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert po_after.status_code == 200
        assert po_after.json()["data"]["status"] == "ordered"
        assert po_after.json()["data"]["lines"][0]["quantity_received"] == 0
        assert po_after.json()["data"]["paid_total"] == "25.00"

        stock_after = await client.get(
            f"/api/v1/inventory/stock/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stock_after.status_code == 200
        assert stock_after.json()["data"]["quantity_on_hand"] == 0

        grn_after = await client.get(
            f"/api/v1/procurement/grns/{grn_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert grn_after.status_code == 200
        assert grn_after.json()["data"]["status"] == "cancelled"

    async def test_rollback_grn_error_includes_blocking_receipt_details(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(
            client, db_session, role=UserRole.SUPER_ADMIN
        )
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(
            client,
            token,
            item_id,
            track_to_warehouse=True,
            quantity_expected=10,
        )
        po_id = po_data["id"]
        po_line_id = po_data["lines"][0]["id"]

        # GRN #1 (approved)
        grn1 = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "lines": [{"po_line_id": po_line_id, "quantity_received": 2}],
            },
        )
        assert grn1.status_code == 201
        grn1_id = grn1.json()["data"]["id"]
        approve1 = await client.post(
            f"/api/v1/procurement/grns/{grn1_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve1.status_code == 200

        # GRN #2 (approved) for same item → creates a later receipt movement
        grn2 = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "lines": [{"po_line_id": po_line_id, "quantity_received": 1}],
            },
        )
        assert grn2.status_code == 201
        grn2_id = grn2.json()["data"]["id"]
        approve2 = await client.post(
            f"/api/v1/procurement/grns/{grn2_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve2.status_code == 200

        # Make ordering deterministic: ensure GRN #2 receipt movement is
        # "later" than GRN #1 receipt movement by created_at.
        m1 = await db_session.scalar(
            select(StockMovement)
            .where(StockMovement.item_id == item_id)
            .where(StockMovement.movement_type == MovementType.RECEIPT.value)
            .where(StockMovement.reference_type == "grn")
            .where(StockMovement.reference_id == grn1_id)
            .order_by(StockMovement.created_at.asc(), StockMovement.id.asc())
            .limit(1)
        )
        m2 = await db_session.scalar(
            select(StockMovement)
            .where(StockMovement.item_id == item_id)
            .where(StockMovement.movement_type == MovementType.RECEIPT.value)
            .where(StockMovement.reference_type == "grn")
            .where(StockMovement.reference_id == grn2_id)
            .order_by(StockMovement.created_at.asc(), StockMovement.id.asc())
            .limit(1)
        )
        assert m1 is not None
        assert m2 is not None
        await db_session.execute(
            update(StockMovement)
            .where(StockMovement.id == m2.id)
            .values(created_at=m1.created_at + timedelta(seconds=5))
        )
        await db_session.commit()

        # Now rolling back GRN #1 must fail and include details about the
        # later receipt.
        rollback1 = await client.post(
            f"/api/v1/procurement/grns/{grn1_id}/rollback",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Need to rollback older GRN"},
        )
        assert rollback1.status_code == 422
        msg = (rollback1.json().get("message") or "").lower()
        assert "later receipt movement" in msg
        assert "ref=grn" in msg

    async def test_rollback_ignores_receipts_from_cancelled_grns(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(
            client, db_session, role=UserRole.SUPER_ADMIN
        )
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(
            client,
            token,
            item_id,
            track_to_warehouse=True,
            quantity_expected=10,
        )
        po_id = po_data["id"]
        po_line_id = po_data["lines"][0]["id"]

        # GRN #1 approved
        grn1 = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "lines": [{"po_line_id": po_line_id, "quantity_received": 2}],
            },
        )
        assert grn1.status_code == 201
        grn1_id = grn1.json()["data"]["id"]
        approve1 = await client.post(
            f"/api/v1/procurement/grns/{grn1_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve1.status_code == 200

        # GRN #2 approved then rolled back (becomes cancelled)
        grn2 = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "lines": [{"po_line_id": po_line_id, "quantity_received": 1}],
            },
        )
        assert grn2.status_code == 201
        grn2_id = grn2.json()["data"]["id"]
        approve2 = await client.post(
            f"/api/v1/procurement/grns/{grn2_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve2.status_code == 200

        rollback2 = await client.post(
            f"/api/v1/procurement/grns/{grn2_id}/rollback",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Rollback later GRN first"},
        )
        assert rollback2.status_code == 200
        assert rollback2.json()["data"]["status"] == "cancelled"

        # Now rollback of GRN #1 should succeed
        # (cancelled GRN #2 receipts ignored).
        rollback1 = await client.post(
            f"/api/v1/procurement/grns/{grn1_id}/rollback",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Rollback older GRN after later cancelled"},
        )
        assert rollback1.status_code == 200
        assert rollback1.json()["data"]["status"] == "cancelled"

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
        token = await self._get_admin_token(
            client, db_session, role=UserRole.SUPER_ADMIN
        )
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(
            client, token, item_id, track_to_warehouse=False
        )
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
