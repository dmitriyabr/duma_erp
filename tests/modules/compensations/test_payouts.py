from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


class TestCompensationPayouts:
    """Tests for payouts."""

    async def _get_superadmin_token(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> str:
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="superadmin-payout@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "superadmin-payout@test.com", "password": "Password123"},
        )
        return response.json()["data"]["access_token"]

    async def _create_employee(self, db_session: AsyncSession) -> int:
        auth_service = AuthService(db_session)
        employee = await auth_service.create_user(
            email="employee-payout@test.com",
            password="Password123",
            full_name="Employee",
            role=UserRole.USER,
        )
        await db_session.commit()
        return employee.id

    async def _create_payment_purpose(self, client: AsyncClient, token: str) -> int:
        response = await client.post(
            "/api/v1/procurement/payment-purposes",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Compensation"},
        )
        return response.json()["data"]["id"]

    async def _create_employee_payment(
        self,
        client: AsyncClient,
        token: str,
        purpose_id: int,
        employee_id: int,
    ) -> int:
        response = await client.post(
            "/api/v1/procurement/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "purpose_id": purpose_id,
                "payment_date": "2026-01-25",
                "amount": "100.00",
                "payment_method": "cash",
                "proof_text": "Receipt",
                "employee_paid_id": employee_id,
            },
        )
        return response.json()["data"]["id"]

    async def test_payout_fifo(self, client: AsyncClient, db_session: AsyncSession):
        token = await self._get_superadmin_token(client, db_session)
        employee_id = await self._create_employee(db_session)
        purpose_id = await self._create_payment_purpose(client, token)

        await self._create_employee_payment(
            client, token, purpose_id=purpose_id, employee_id=employee_id
        )

        claims_response = await client.get(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        claim_id = claims_response.json()["data"]["items"][0]["id"]

        approve_response = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={"approve": True},
        )
        assert approve_response.status_code == 200

        payout_response = await client.post(
            "/api/v1/compensations/payouts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "employee_id": employee_id,
                "payout_date": "2026-01-26",
                "amount": "100.00",
                "payment_method": "cash",
                "proof_text": "Paid",
            },
        )
        assert payout_response.status_code == 200
        payout_data = payout_response.json()["data"]
        assert payout_data["allocations"][0]["claim_id"] == claim_id

        balance_response = await client.get(
            f"/api/v1/compensations/payouts/employees/{employee_id}/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert balance_response.status_code == 200
        assert balance_response.json()["data"]["balance"] == "0.00"
