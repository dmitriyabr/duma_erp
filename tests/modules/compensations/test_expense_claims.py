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

    async def test_claim_with_transaction_fee_creates_fee_payment_and_reimburses_total(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-fee@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        user_id, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-fee@test.com",
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
                "payee_name": "Shop",
                "description": "Small purchase",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #123",
                "fee_amount": "1.00",
                "fee_proof_text": "M-Pesa fee SMS #FEE",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim = create_res.json()["data"]
        assert claim["employee_id"] == user_id
        assert claim["amount"] == "11.00"
        assert claim["expense_amount"] == "10.00"
        assert claim["fee_amount"] == "1.00"
        assert claim["fee_payment_id"] is not None

        main_payment_id = claim["payment_id"]
        fee_payment_id = claim["fee_payment_id"]

        main_payment_res = await client.get(
            f"/api/v1/procurement/payments/{main_payment_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert main_payment_res.status_code == 200
        main_payment = main_payment_res.json()["data"]
        assert main_payment["company_paid"] is False
        assert main_payment["employee_paid_id"] == user_id
        assert main_payment["payment_method"] == "employee"
        assert main_payment["status"] == "posted"

        fee_payment_res = await client.get(
            f"/api/v1/procurement/payments/{fee_payment_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert fee_payment_res.status_code == 200
        fee_payment = fee_payment_res.json()["data"]
        assert fee_payment["purpose_name"] == "Transaction Fees"
        assert fee_payment["company_paid"] is False
        assert fee_payment["employee_paid_id"] == user_id
        assert fee_payment["payment_method"] == "employee"
        assert fee_payment["status"] == "posted"

        reject_res = await client.post(
            f"/api/v1/compensations/claims/{claim['id']}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": False, "reason": "Not approved"},
        )
        assert reject_res.status_code == 200

        fee_payment_res2 = await client.get(
            f"/api/v1/procurement/payments/{fee_payment_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert fee_payment_res2.status_code == 200
        assert fee_payment_res2.json()["data"]["status"] == "cancelled"

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

    async def test_superadmin_can_send_claim_to_edit_with_comment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-edit@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-edit@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )
        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "20.00",
                "description": "Fuel",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #fuel",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        send_to_edit_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/send-to-edit",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"comment": "Please fix amount and attach correct receipt"},
        )
        assert send_to_edit_res.status_code == 200
        data = send_to_edit_res.json()["data"]
        assert data["status"] == "needs_edit"
        assert data["edit_comment"] == "Please fix amount and attach correct receipt"

    async def test_send_to_edit_requires_non_empty_comment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-edit-empty@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-edit-empty@test.com",
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
                "description": "Fuel",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #fuel",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        send_to_edit_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/send-to-edit",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"comment": ""},
        )
        assert send_to_edit_res.status_code == 422

    async def test_non_superadmin_cannot_send_claim_to_edit(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-edit-forbidden@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)

        _, admin_token = await _create_user_and_token(
            client,
            db_session,
            email="admin-claims-edit-forbidden@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-edit-forbidden@test.com",
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
                "description": "Fuel",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #fuel",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        send_to_edit_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/send-to-edit",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "Fix receipt"},
        )
        assert send_to_edit_res.status_code == 403

    async def test_send_to_edit_for_auto_created_claim_is_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-auto-edit@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)
        employee_id, _ = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-auto-edit@test.com",
            password="Password123",
            full_name="Employee",
            role=UserRole.USER,
        )

        payment_res = await client.post(
            "/api/v1/procurement/payments",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "purpose_id": purpose_id,
                "payment_date": "2026-02-09",
                "amount": "15.00",
                "payment_method": "bank",
                "proof_text": "Proof",
                "company_paid": False,
                "employee_paid_id": employee_id,
            },
        )
        assert payment_res.status_code == 201

        claims_res = await client.get(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {super_token}"},
            params={"employee_id": employee_id},
        )
        assert claims_res.status_code == 200
        claims = claims_res.json()["data"]["items"]
        auto_claim = next((c for c in claims if c["auto_created_from_payment"] is True), None)
        assert auto_claim is not None

        send_to_edit_res = await client.post(
            f"/api/v1/compensations/claims/{auto_claim['id']}/send-to-edit",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"comment": "Fix details"},
        )
        assert send_to_edit_res.status_code == 422

    async def test_owner_can_update_and_resubmit_claim_from_needs_edit(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-resubmit@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)
        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-resubmit@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "30.00",
                "description": "Repair",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #repair",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        send_to_edit_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/send-to-edit",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"comment": "Please correct description"},
        )
        assert send_to_edit_res.status_code == 200
        assert send_to_edit_res.json()["data"]["status"] == "needs_edit"

        update_res = await client.patch(
            f"/api/v1/compensations/claims/{claim_id}",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"description": "Repair and spare parts"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["data"]["status"] == "needs_edit"
        assert update_res.json()["data"]["description"] == "Repair and spare parts"
        assert update_res.json()["data"]["edit_comment"] == "Please correct description"

        submit_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/submit",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert submit_res.status_code == 200
        assert submit_res.json()["data"]["status"] == "pending_approval"
        assert submit_res.json()["data"]["edit_comment"] is None

    async def test_owner_can_update_claim_in_pending_approval(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-pending-edit@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)
        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-pending-edit@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "25.00",
                "description": "Fuel",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #fuel",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]
        assert create_res.json()["data"]["status"] == "pending_approval"

        update_res = await client.patch(
            f"/api/v1/compensations/claims/{claim_id}",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"description": "Fuel for school trip", "amount": "30.00"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["data"]["status"] == "pending_approval"
        assert update_res.json()["data"]["description"] == "Fuel for school trip"
        assert update_res.json()["data"]["expense_amount"] == "30.00"

    async def test_cannot_update_final_claim_statuses(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-final-update@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)
        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-final-update@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "12.00",
                "description": "Fuel",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #fuel",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        approve_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": True},
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["data"]["status"] == "approved"

        update_res = await client.patch(
            f"/api/v1/compensations/claims/{claim_id}",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"description": "Updated"},
        )
        assert update_res.status_code == 422

    async def test_cannot_approve_claim_when_not_pending_approval(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="superadmin-claims-not-pending@test.com",
            password="Password123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        purpose_id = await self._create_purpose(client, super_token)
        _, user_token = await _create_user_and_token(
            client,
            db_session,
            email="user-claims-not-pending@test.com",
            password="Password123",
            full_name="User",
            role=UserRole.USER,
        )

        create_res = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "purpose_id": purpose_id,
                "amount": "9.00",
                "description": "Supplies",
                "expense_date": "2026-02-09",
                "proof_text": "Receipt #sup",
                "submit": True,
            },
        )
        assert create_res.status_code == 201
        claim_id = create_res.json()["data"]["id"]

        send_to_edit_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/send-to-edit",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"comment": "Need corrections"},
        )
        assert send_to_edit_res.status_code == 200

        approve_res = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": True},
        )
        assert approve_res.status_code == 422
