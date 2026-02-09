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
        assert claim["payment_id"] is None
        assert claim["auto_created_from_payment"] is False
        assert claim["status"] == "pending_approval"
        assert claim["proof_text"] == "Receipt #ABC"

        claim_id = claim["id"]

        get_res = await client.get(
            f"/api/v1/compensations/claims/{claim_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert get_res.status_code == 200

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
