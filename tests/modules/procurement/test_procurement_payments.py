from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


class TestProcurementPayments:
    """Tests for procurement payments."""

    async def _get_admin_token(self, client: AsyncClient, db_session: AsyncSession) -> str:
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="admin-pay@test.com",
            password="Password123",
            full_name="Admin Pay",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin-pay@test.com", "password": "Password123"},
        )
        return response.json()["data"]["access_token"]

    async def _create_payment_purpose(self, client: AsyncClient, token: str, name: str) -> int:
        response = await client.post(
            "/api/v1/procurement/payment-purposes",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": name},
        )
        return response.json()["data"]["id"]

    async def _create_product_item(self, client: AsyncClient, token: str) -> int:
        cat_response = await client.post(
            "/api/v1/items/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Pay Category"},
        )
        category_id = cat_response.json()["data"]["id"]

        item_response = await client.post(
            "/api/v1/items",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category_id": category_id,
                "sku_code": "PAY-001",
                "name": "Pay Item",
                "item_type": "product",
                "price_type": "standard",
                "price": "10.00",
            },
        )
        return item_response.json()["data"]["id"]

    async def _create_po(
        self, client: AsyncClient, token: str, item_id: int, purpose_id: int
    ) -> dict:
        response = await client.post(
            "/api/v1/procurement/purchase-orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_name": "Pay Supplier",
                "purpose_id": purpose_id,
                "lines": [
                    {
                        "item_id": item_id,
                        "description": "Pay Item",
                        "quantity_expected": 1,
                        "unit_price": "10.00",
                    }
                ],
            },
        )
        return response.json()["data"]

    async def test_payment_without_po(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_admin_token(client, db_session)
        purpose_id = await self._create_payment_purpose(client, token, "Marketing")

        response = await client.post(
            "/api/v1/procurement/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "purpose_id": purpose_id,
                "payee_name": "Ads Vendor",
                "payment_date": "2026-01-25",
                "amount": "1000.00",
                "payment_method": "bank",
                "proof_text": "Receipt #123",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["po_id"] is None
        assert data["purpose_id"] == purpose_id

        claims_response = await client.get(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert claims_response.status_code == 200
        assert claims_response.json()["data"]["total"] == 0

    async def test_payment_with_po(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_admin_token(client, db_session)
        auth_service = AuthService(db_session)
        employee = await auth_service.create_user(
            email="employee@test.com",
            password="Password123",
            full_name="Employee",
            role=UserRole.USER,
        )
        await db_session.commit()
        purpose_id = await self._create_payment_purpose(client, token, "Procurement")
        item_id = await self._create_product_item(client, token)
        po_data = await self._create_po(client, token, item_id, purpose_id)

        employee_id = employee.id
        response = await client.post(
            "/api/v1/procurement/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_data["id"],
                "purpose_id": purpose_id,
                "payment_date": "2026-01-25",
                "amount": "10.00",
                "payment_method": "bank",
                "proof_text": "Proof",
                "employee_paid_id": employee_id,
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["po_id"] == po_data["id"]
        assert data["purpose_id"] == purpose_id

        claims_response = await client.get(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert claims_response.status_code == 200
        claims_data = claims_response.json()["data"]
        assert claims_data["total"] == 1
        assert claims_data["items"][0]["employee_id"] == employee_id

    async def test_cancel_payment_reopens_closed_po(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await self._get_admin_token(client, db_session)
        purpose_id = await self._create_payment_purpose(client, token, "Procurement")
        item_id = await self._create_product_item(client, token)

        po_data = await self._create_po(client, token, item_id, purpose_id)
        po_id = po_data["id"]
        po_line_id = po_data["lines"][0]["id"]

        # Fully receive the PO via GRN.
        grn_response = await client.post(
            "/api/v1/procurement/grns",
            headers={"Authorization": f"Bearer {token}"},
            json={"po_id": po_id, "lines": [{"po_line_id": po_line_id, "quantity_received": 1}]},
        )
        assert grn_response.status_code == 201
        grn_id = grn_response.json()["data"]["id"]

        approve_response = await client.post(
            f"/api/v1/procurement/grns/{grn_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approve_response.status_code == 200

        # Pay the received value -> PO becomes closed.
        pay_response = await client.post(
            "/api/v1/procurement/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_id": po_id,
                "purpose_id": purpose_id,
                "payment_date": "2026-01-25",
                "amount": "10.00",
                "payment_method": "bank",
                "proof_text": "Proof",
                "company_paid": True,
            },
        )
        assert pay_response.status_code == 201
        payment_id = pay_response.json()["data"]["id"]

        po_after_pay = await client.get(
            f"/api/v1/procurement/purchase-orders/{po_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert po_after_pay.status_code == 200
        assert po_after_pay.json()["data"]["status"] == "closed"

        cancel_response = await client.post(
            f"/api/v1/procurement/payments/{payment_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Test cancel"},
        )
        assert cancel_response.status_code == 200

        po_after_cancel = await client.get(
            f"/api/v1/procurement/purchase-orders/{po_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert po_after_cancel.status_code == 200
        assert po_after_cancel.json()["data"]["status"] == "received"
