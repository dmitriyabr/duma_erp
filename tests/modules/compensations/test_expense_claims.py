from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


async def _create_user_and_token(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
) -> tuple[int, str]:
    auth_service = AuthService(db_session)
    user = await auth_service.create_user(
        email=email,
        password=password,
        full_name=full_name,
        role=role,
    )
    await db_session.commit()

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = res.json()["data"]["access_token"]
    return user.id, token


class TestExpenseClaimsOutOfPocket:
    async def _create_purpose(self, client: AsyncClient, token: str) -> int:
        res = await client.post(
            "/api/v1/procurement/payment-purposes",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Fuel"},
        )
        assert res.status_code in (200, 201)
        return res.json()["data"]["id"]

    async def test_user_can_create_own_claim(self, client: AsyncClient, db_session: AsyncSession):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        user_id, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "123.45",
                "payee_name": "Shell",
                "description": "Fuel for school van",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #ABC",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim = create_res.json()["data"]
        assert claim["employee_id"] == user_id
        assert claim["employee_name"] == "User"
        assert claim["payment_id"] is not None
        assert claim["auto_created_from_payment"] is False
        assert claim["status"] == "pending_approval"
        assert claim["proof_text"] == "Receipt #ABC"

        claim_id = claim["id"]
        payment_id = claim["payment_id"]

        get_res = await client.get(
            f"/api/v1/compensations/claims/{claim_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert get_res.status_code == 200

        payment_res = await client.get(
            f"/api/v1/procurement/payments/{payment_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert payment_res.status_code == 200
        payment = payment_res.json()["data"]
        assert payment["company_paid"] is False
        assert payment["employee_paid_id"] == user_id
        assert payment["status"] == "posted"

    async def test_user_cannot_view_other_users_claim(self, client: AsyncClient, db_session: AsyncSession):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims2@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        user1_id, user1_token = await _create_user_and_token(
            client,
            db_session,
            email="user1-claims@test.com",
            password="Password123",
            full_name="User One",
            role=UserRole.USER,
        )
        _, user2_token = await _create_user_and_token(
            client,
            db_session,
            email="user2-claims@test.com",
            password="Password123",
            full_name="User Two",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user1_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "10.00",
                "description": "Snacks",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #1",
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        get_other = await client.get(
            f"/api/v1/compensations/claims/{claim_id}",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert get_other.status_code == 403

        list_res = await client.get(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user1_token}"},
            params={"employee_id": user1_id + 9999},  # should be ignored for USER
        )
        assert list_res.status_code == 200
        items = list_res.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["employee_id"] == user1_id
        assert items[0]["employee_name"] == "User One"

    async def test_proof_required_on_submit(self, client: AsyncClient, db_session: AsyncSession):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims3@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user3-claims@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "1.00",
                "description": "Fuel",
                "expense_date": "2026-02-09",
                "submit": True,
            },
        )
        assert res.status_code == 422

    async def test_reject_claim_cancels_linked_payment(self, client: AsyncClient, db_session: AsyncSession):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims4@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        user_id, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user4-claims@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "10.00",
                "description": "Snacks",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #snacks",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim = create_res.json()["data"]
        claim_id = claim["id"]
        payment_id = claim["payment_id"]

        reject_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": False, "reason": "Not a company expense"},
        )
        assert reject_res.status_code == 200
        rejected = reject_res.json()["data"]
        assert rejected["status"] == "rejected"
        assert rejected["rejection_reason"] == "Not a company expense"
        assert rejected["remaining_amount"] == "0.00"

        payment_res = await client.get(
            f"/api/v1/procurement/payments/{payment_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert payment_res.status_code == 200
        payment = payment_res.json()["data"]
        assert payment["status"] == "cancelled"
        assert payment["cancelled_reason"] == "Not a company expense"
        assert payment["employee_paid_id"] == user_id

    async def test_employee_claim_totals_include_pending_and_balance(self, client: AsyncClient, db_session: AsyncSession):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-totals@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        user1_id, user1_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-totals1@test.com",
            password="Password123",
            full_name="User One",
            role=UserRole.USER,
        )
        _, user2_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-totals2@test.com",
            password="Password123",
            full_name="User Two",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user1_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "10.00",
                "description": "Snacks",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #snacks",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        totals_res = await client.get(
            f"/api/v1/compensations/claims/employees/{user1_id}/totals",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert totals_res.status_code == 200
        totals = totals_res.json()["data"]
        assert totals["employee_id"] == user1_id
        assert totals["total_submitted"] == "10.00"
        assert totals["count_submitted"] == 1
        assert totals["total_pending_approval"] == "10.00"
        assert totals["count_pending_approval"] == 1
        assert totals["total_approved"] == "0.00"
        assert totals["total_paid"] == "0.00"
        assert totals["balance"] == "0.00"

        other_totals = await client.get(
            f"/api/v1/compensations/claims/employees/{user1_id}/totals",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert other_totals.status_code == 403

        approve_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": True},
        )
        assert approve_res.status_code == 200

        totals_res2 = await client.get(
            f"/api/v1/compensations/claims/employees/{user1_id}/totals",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert totals_res2.status_code == 200
        totals2 = totals_res2.json()["data"]
        assert totals2["total_pending_approval"] == "0.00"
        assert totals2["count_pending_approval"] == 0
        assert totals2["total_approved"] == "10.00"
        assert totals2["total_paid"] == "0.00"
        assert totals2["balance"] == "10.00"

        payout_res = await client.post(
            "/api/v1/compensations/payouts",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "employee_id": user1_id,
                "payout_date": "2026-02-10",
                "amount": "4.00",
                "payment_method": "cash",
                "reference_number": "Payout-1",
                "proof_text": "Cash payout",
            },
        )
        assert payout_res.status_code == 200

        totals_res3 = await client.get(
            f"/api/v1/compensations/claims/employees/{user1_id}/totals",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert totals_res3.status_code == 200
        totals3 = totals_res3.json()["data"]
        assert totals3["total_approved"] == "10.00"
        assert totals3["total_paid"] == "4.00"
        assert totals3["balance"] == "6.00"
