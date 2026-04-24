from decimal import Decimal

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
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return user.id, response.json()["data"]["access_token"]


class TestBudgets:
    async def _create_purpose(self, client: AsyncClient, token: str, name: str = "Kitchen") -> int:
        response = await client.post(
            "/api/v1/procurement/payment-purposes",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": name},
        )
        assert response.status_code in (200, 201)
        return response.json()["data"]["id"]

    async def test_budget_funded_claim_reserves_and_settles_against_advance(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-super@test.com",
            password="Pass123!",
            full_name="Budget Super",
            role=UserRole.SUPER_ADMIN,
        )
        employee_id, employee_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-employee@test.com",
            password="Pass123!",
            full_name="Budget Employee",
            role=UserRole.USER,
        )
        purpose_id = await self._create_purpose(client, super_token, "Kitchen Supplies")

        create_budget = await client.post(
            "/api/v1/budgets",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "name": "Kitchen April",
                "purpose_id": purpose_id,
                "period_from": "2026-04-01",
                "period_to": "2026-04-30",
                "limit_amount": "5000.00",
            },
        )
        assert create_budget.status_code == 201
        budget_id = create_budget.json()["data"]["id"]

        activate_budget = await client.post(
            f"/api/v1/budgets/{budget_id}/activate",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert activate_budget.status_code == 200
        assert activate_budget.json()["data"]["status"] == "active"

        create_draft_advance = await client.post(
            "/api/v1/budgets/advances",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "budget_id": budget_id,
                "employee_id": employee_id,
                "issue_date": "2026-04-24",
                "amount_issued": "5000.00",
                "payment_method": "bank",
                "reference_number": "ADV-APR-01",
                "settlement_due_date": "2026-04-30",
                "issue_now": False,
            },
        )
        assert create_draft_advance.status_code == 201
        advance_id = create_draft_advance.json()["data"]["id"]
        assert create_draft_advance.json()["data"]["status"] == "draft"

        budget_before_issue = await client.get(
            f"/api/v1/budgets/{budget_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert Decimal(budget_before_issue.json()["data"]["committed_total"]) == Decimal("0.00")

        issue_advance = await client.post(
            f"/api/v1/budgets/advances/{advance_id}/issue",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "reference_number": "ADV-APR-01",
                "proof_text": "Bank transfer confirmation",
            },
        )
        assert issue_advance.status_code == 200
        assert issue_advance.json()["data"]["status"] == "issued"
        assert Decimal(issue_advance.json()["data"]["available_unreserved_amount"]) == Decimal("5000.00")

        my_budgets = await client.get(
            "/api/v1/budgets/my/budgets",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert my_budgets.status_code == 200
        assert len(my_budgets.json()["data"]) == 1
        assert my_budgets.json()["data"][0]["id"] == budget_id
        assert Decimal(my_budgets.json()["data"][0]["available_unreserved_total"]) == Decimal("5000.00")

        my_advances = await client.get(
            "/api/v1/budgets/my/advances",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert my_advances.status_code == 200
        assert my_advances.json()["data"]["total"] == 1

        create_claim = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "budget_id": budget_id,
                "funding_source": "budget",
                "purpose_id": purpose_id,
                "amount": "1200.00",
                "payee_name": "Local shop",
                "description": "Kitchen groceries",
                "expense_date": "2026-04-24",
                "proof_text": "Receipt #APR-1",
                "submit": True,
            },
        )
        assert create_claim.status_code == 201
        claim = create_claim.json()["data"]
        assert claim["funding_source"] == "budget"
        assert claim["budget_id"] == budget_id
        assert claim["budget_funding_status"] == "reserved"
        assert claim["status"] == "pending_approval"
        assert len(claim["budget_allocations"]) == 1
        assert Decimal(claim["budget_allocations"][0]["allocated_amount"]) == Decimal("1200.00")

        advance_after_reserve = await client.get(
            f"/api/v1/budgets/advances/{advance_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert advance_after_reserve.status_code == 200
        advance_data = advance_after_reserve.json()["data"]
        assert Decimal(advance_data["reserved_amount"]) == Decimal("1200.00")
        assert Decimal(advance_data["available_unreserved_amount"]) == Decimal("3800.00")
        assert Decimal(advance_data["open_balance"]) == Decimal("5000.00")

        approve_claim = await client.post(
            f"/api/v1/compensations/claims/{claim['id']}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": True},
        )
        assert approve_claim.status_code == 200
        approved = approve_claim.json()["data"]
        assert approved["status"] == "paid"
        assert approved["budget_funding_status"] == "settled"
        assert Decimal(approved["paid_amount"]) == Decimal("1200.00")
        assert Decimal(approved["remaining_amount"]) == Decimal("0.00")

        advance_after_approve = await client.get(
            f"/api/v1/budgets/advances/{advance_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        advance_data = advance_after_approve.json()["data"]
        assert Decimal(advance_data["reserved_amount"]) == Decimal("0.00")
        assert Decimal(advance_data["settled_amount"]) == Decimal("1200.00")
        assert Decimal(advance_data["open_balance"]) == Decimal("3800.00")
        assert Decimal(advance_data["available_unreserved_amount"]) == Decimal("3800.00")

        totals = await client.get(
            f"/api/v1/compensations/claims/employees/{employee_id}/totals",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert totals.status_code == 200
        totals_data = totals.json()["data"]
        assert totals_data["total_paid"] == "1200.00"
        assert totals_data["balance"] == "0.00"

    async def test_send_to_edit_releases_budget_reservations_and_resubmit_re_reserves(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-edit-super@test.com",
            password="Pass123!",
            full_name="Budget Super",
            role=UserRole.SUPER_ADMIN,
        )
        employee_id, employee_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-edit-employee@test.com",
            password="Pass123!",
            full_name="Budget Employee",
            role=UserRole.USER,
        )
        purpose_id = await self._create_purpose(client, super_token, "Office Snacks")

        budget = await client.post(
            "/api/v1/budgets",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "name": "Office April",
                "purpose_id": purpose_id,
                "period_from": "2026-04-01",
                "period_to": "2026-04-30",
                "limit_amount": "1000.00",
            },
        )
        budget_id = budget.json()["data"]["id"]
        await client.post(
            f"/api/v1/budgets/{budget_id}/activate",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        advance = await client.post(
            "/api/v1/budgets/advances",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "budget_id": budget_id,
                "employee_id": employee_id,
                "issue_date": "2026-04-24",
                "amount_issued": "300.00",
                "payment_method": "cash",
                "reference_number": "ADV-EDIT-1",
                "proof_text": "Cash issue note",
                "settlement_due_date": "2026-04-30",
            },
        )
        advance_id = advance.json()["data"]["id"]

        create_claim = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "budget_id": budget_id,
                "funding_source": "budget",
                "purpose_id": purpose_id,
                "amount": "100.00",
                "description": "Snacks",
                "expense_date": "2026-04-24",
                "proof_text": "Receipt #EDIT",
                "submit": True,
            },
        )
        assert create_claim.status_code == 201
        claim_id = create_claim.json()["data"]["id"]

        send_to_edit = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/send-to-edit",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"comment": "Please attach clearer receipt"},
        )
        assert send_to_edit.status_code == 200
        edited = send_to_edit.json()["data"]
        assert edited["status"] == "needs_edit"
        assert edited["budget_funding_status"] == "released"

        advance_after_release = await client.get(
            f"/api/v1/budgets/advances/{advance_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert Decimal(advance_after_release.json()["data"]["reserved_amount"]) == Decimal("0.00")
        assert Decimal(advance_after_release.json()["data"]["available_unreserved_amount"]) == Decimal("300.00")

        resubmit = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/submit",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert resubmit.status_code == 200
        assert resubmit.json()["data"]["status"] == "pending_approval"
        assert resubmit.json()["data"]["budget_funding_status"] == "reserved"

        advance_after_resubmit = await client.get(
            f"/api/v1/budgets/advances/{advance_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert Decimal(advance_after_resubmit.json()["data"]["reserved_amount"]) == Decimal("100.00")

    async def test_returns_transfers_and_closure_work_end_to_end(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-close-super@test.com",
            password="Pass123!",
            full_name="Budget Super",
            role=UserRole.SUPER_ADMIN,
        )
        employee_id, employee_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-close-employee@test.com",
            password="Pass123!",
            full_name="Budget Employee",
            role=UserRole.USER,
        )
        purpose_id = await self._create_purpose(client, super_token, "Kitchen Monthly")

        april_budget = await client.post(
            "/api/v1/budgets",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "name": "Kitchen April",
                "purpose_id": purpose_id,
                "period_from": "2026-04-01",
                "period_to": "2026-04-30",
                "limit_amount": "1000.00",
            },
        )
        april_budget_id = april_budget.json()["data"]["id"]
        await client.post(
            f"/api/v1/budgets/{april_budget_id}/activate",
            headers={"Authorization": f"Bearer {super_token}"},
        )

        may_budget = await client.post(
            "/api/v1/budgets",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "name": "Kitchen May",
                "purpose_id": purpose_id,
                "period_from": "2026-05-01",
                "period_to": "2026-05-31",
                "limit_amount": "1000.00",
            },
        )
        may_budget_id = may_budget.json()["data"]["id"]
        await client.post(
            f"/api/v1/budgets/{may_budget_id}/activate",
            headers={"Authorization": f"Bearer {super_token}"},
        )

        advance = await client.post(
            "/api/v1/budgets/advances",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "budget_id": april_budget_id,
                "employee_id": employee_id,
                "issue_date": "2026-04-24",
                "amount_issued": "500.00",
                "payment_method": "bank",
                "reference_number": "ADV-CLOSE-1",
                "proof_text": "Transfer note",
                "settlement_due_date": "2026-04-30",
            },
        )
        advance_id = advance.json()["data"]["id"]

        claim = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "budget_id": april_budget_id,
                "funding_source": "budget",
                "purpose_id": purpose_id,
                "amount": "100.00",
                "description": "Kitchen milk",
                "expense_date": "2026-04-24",
                "proof_text": "Receipt #CLOSE",
                "submit": True,
            },
        )
        claim_id = claim.json()["data"]["id"]
        approve = await client.post(
            f"/api/v1/compensations/claims/{claim_id}/approve",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"approve": True},
        )
        assert approve.status_code == 200

        create_return = await client.post(
            f"/api/v1/budgets/advances/{advance_id}/returns",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "return_date": "2026-04-25",
                "amount": "100.00",
                "return_method": "cash",
                "reference_number": "RET-APR-1",
                "proof_text": "Cash returned",
            },
        )
        assert create_return.status_code == 201

        transfer = await client.post(
            f"/api/v1/budgets/advances/{advance_id}/transfer",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "to_budget_id": may_budget_id,
                "to_employee_id": employee_id,
                "transfer_date": "2026-05-01",
                "amount": "300.00",
                "transfer_type": "rollover",
                "reason": "Carry forward kitchen float",
                "settlement_due_date": "2026-05-31",
            },
        )
        assert transfer.status_code == 201
        transfer_data = transfer.json()["data"]
        assert transfer_data["to_budget_id"] == may_budget_id
        target_advance_id = transfer_data["created_to_advance_id"]

        source_advance = await client.get(
            f"/api/v1/budgets/advances/{advance_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        source_data = source_advance.json()["data"]
        assert Decimal(source_data["settled_amount"]) == Decimal("100.00")
        assert Decimal(source_data["returned_amount"]) == Decimal("100.00")
        assert Decimal(source_data["transferred_out_amount"]) == Decimal("300.00")
        assert Decimal(source_data["open_balance"]) == Decimal("0.00")
        assert source_data["status"] == "settled"

        close_advance = await client.post(
            f"/api/v1/budgets/advances/{advance_id}/close",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert close_advance.status_code == 200
        assert close_advance.json()["data"]["status"] == "closed"

        closure = await client.get(
            f"/api/v1/budgets/{april_budget_id}/closure",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert closure.status_code == 200
        closure_data = closure.json()["data"]
        assert closure_data["can_close"] is True
        assert closure_data["open_advances_count"] == 0
        assert closure_data["unresolved_claims_count"] == 0

        close_budget = await client.post(
            f"/api/v1/budgets/{april_budget_id}/close",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert close_budget.status_code == 200
        assert close_budget.json()["data"]["status"] == "closed"

        target_advance = await client.get(
            f"/api/v1/budgets/advances/{target_advance_id}",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert target_advance.status_code == 200
        target_data = target_advance.json()["data"]
        assert target_data["source_type"] == "transfer_in"
        assert Decimal(target_data["amount_issued"]) == Decimal("300.00")
        assert Decimal(target_data["open_balance"]) == Decimal("300.00")

        may_balance = await client.get(
            f"/api/v1/budgets/{may_budget_id}/my-available-balance",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert may_balance.status_code == 200
        assert Decimal(may_balance.json()["data"]["available_unreserved_total"]) == Decimal("300.00")

    async def test_budget_funded_claim_requires_matching_budget_purpose(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, super_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-purpose-super@test.com",
            password="Pass123!",
            full_name="Budget Super",
            role=UserRole.SUPER_ADMIN,
        )
        employee_id, employee_token = await _create_user_and_token(
            client,
            db_session,
            email="budget-purpose-employee@test.com",
            password="Pass123!",
            full_name="Budget Employee",
            role=UserRole.USER,
        )
        kitchen_purpose_id = await self._create_purpose(client, super_token, "Kitchen")
        office_purpose_id = await self._create_purpose(client, super_token, "Office")

        budget = await client.post(
            "/api/v1/budgets",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "name": "Kitchen April",
                "purpose_id": kitchen_purpose_id,
                "period_from": "2026-04-01",
                "period_to": "2026-04-30",
                "limit_amount": "1000.00",
            },
        )
        assert budget.status_code == 201
        budget_id = budget.json()["data"]["id"]

        activate_budget = await client.post(
            f"/api/v1/budgets/{budget_id}/activate",
            headers={"Authorization": f"Bearer {super_token}"},
        )
        assert activate_budget.status_code == 200

        advance = await client.post(
            "/api/v1/budgets/advances",
            headers={"Authorization": f"Bearer {super_token}"},
            json={
                "budget_id": budget_id,
                "employee_id": employee_id,
                "issue_date": "2026-04-24",
                "amount_issued": "500.00",
                "payment_method": "bank",
                "reference_number": "ADV-PURPOSE-1",
                "proof_text": "Transfer proof",
                "settlement_due_date": "2026-04-30",
            },
        )
        assert advance.status_code == 201

        create_claim = await client.post(
            "/api/v1/compensations/claims",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={
                "budget_id": budget_id,
                "funding_source": "budget",
                "purpose_id": office_purpose_id,
                "amount": "100.00",
                "payee_name": "Local shop",
                "description": "Wrong purpose",
                "expense_date": "2026-04-24",
                "proof_text": "Receipt #1",
                "submit": True,
            },
        )
        assert create_claim.status_code == 422
        assert "purpose" in create_claim.json()["message"].lower()
