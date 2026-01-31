"""Tests for Reports API: GET aged-receivables, GET student-fees (Admin/SuperAdmin only)."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.terms.models import Term, TermStatus


async def _get_token(
    client: AsyncClient, db_session: AsyncSession, role: UserRole, suffix: str = ""
) -> str:
    """Create user with given role and return access token."""
    email = f"reports_{role.value.lower()}{suffix}@test.com"
    auth = AuthService(db_session)
    await auth.create_user(
        email=email,
        password="Pass123",
        full_name="Test User",
        role=role,
    )
    await db_session.commit()
    _, token, _ = await auth.authenticate(email, "Pass123")
    return token


class TestAgedReceivables:
    """Tests for GET /reports/aged-receivables."""

    async def test_aged_receivables_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get("/api/v1/reports/aged-receivables")
        assert response.status_code == 401

    async def test_aged_receivables_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can get aged receivables report."""
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/aged-receivables",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        d = data["data"]
        assert "as_at_date" in d
        assert "rows" in d
        assert "summary" in d
        assert "total" in d["summary"]
        assert "current" in d["summary"]
        assert "bucket_90_plus" in d["summary"]

    async def test_aged_receivables_superadmin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """SuperAdmin can get aged receivables report."""
        token = await _get_token(client, db_session, UserRole.SUPER_ADMIN, "_sa")
        response = await client.get(
            "/api/v1/reports/aged-receivables?as_at_date=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["as_at_date"] == "2026-01-31"

    async def test_aged_receivables_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access reports."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/aged-receivables",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_aged_receivables_accountant_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant role cannot access reports."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/reports/aged-receivables",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestStudentFees:
    """Tests for GET /reports/student-fees."""

    async def test_student_fees_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get("/api/v1/reports/student-fees?term_id=1")
        assert response.status_code == 401

    async def test_student_fees_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can get student fees report."""
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="reports_sf_admin@test.com",
            password="Pass123",
            full_name="Test Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()
        term = Term(
            year=2026,
            term_number=1,
            display_name="2026-T1",
            status=TermStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(term)
        await db_session.commit()
        _, token, _ = await auth.authenticate("reports_sf_admin@test.com", "Pass123")
        response = await client.get(
            f"/api/v1/reports/student-fees?term_id={term.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data["data"]["term_id"] == term.id
        assert data["data"]["term_display_name"] == "2026-T1"
        assert "rows" in data["data"]
        assert "summary" in data["data"]
        assert "students_count" in data["data"]["summary"]

    async def test_student_fees_404_if_term_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Returns 404 when term does not exist."""
        token = await _get_token(client, db_session, UserRole.ADMIN, "_404")
        response = await client.get(
            "/api/v1/reports/student-fees?term_id=99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_student_fees_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access student-fees report."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/student-fees?term_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_student_fees_accountant_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant role cannot access student-fees report."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/reports/student-fees?term_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestProfitLoss:
    """Tests for GET /reports/profit-loss."""

    async def test_profit_loss_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_profit_loss_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "revenue_lines" in d
        assert "gross_revenue" in d
        assert "total_discounts" in d
        assert "net_revenue" in d
        assert "expense_lines" in d
        assert "total_expenses" in d
        assert "net_profit" in d
        assert "profit_margin_percent" in d

    async def test_profit_loss_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_profit_loss_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestCashFlow:
    """Tests for GET /reports/cash-flow."""

    async def test_cash_flow_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/cash-flow?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_cash_flow_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/cash-flow?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "opening_balance" in d
        assert "inflow_lines" in d
        assert "total_inflows" in d
        assert "outflow_lines" in d
        assert "total_outflows" in d
        assert "net_cash_flow" in d
        assert "closing_balance" in d

    async def test_cash_flow_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/cash-flow?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_cash_flow_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/cash-flow?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestBalanceSheet:
    """Tests for GET /reports/balance-sheet."""

    async def test_balance_sheet_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/balance-sheet")
        assert response.status_code == 401

    async def test_balance_sheet_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/balance-sheet?as_at_date=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["as_at_date"] == "2026-01-31"
        assert "asset_lines" in d
        assert "total_assets" in d
        assert "liability_lines" in d
        assert "total_liabilities" in d
        assert "net_equity" in d
        assert "debt_to_asset_percent" in d
        assert "current_ratio" in d

    async def test_balance_sheet_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/balance-sheet",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestCollectionRate:
    """Tests for GET /reports/collection-rate."""

    async def test_collection_rate_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/collection-rate")
        assert response.status_code == 401

    async def test_collection_rate_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/collection-rate?months=6",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert "rows" in d
        assert len(d["rows"]) == 6
        assert "average_rate_percent" in d
        assert "target_rate_percent" in d
        assert "year_month" in d["rows"][0]
        assert "label" in d["rows"][0]
        assert "total_invoiced" in d["rows"][0]
        assert "total_paid" in d["rows"][0]
        assert "rate_percent" in d["rows"][0]

    async def test_collection_rate_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/collection-rate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestDiscountAnalysis:
    """Tests for GET /reports/discount-analysis."""

    async def test_discount_analysis_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/discount-analysis?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_discount_analysis_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/discount-analysis?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "rows" in d
        assert "summary" in d
        assert "students_count" in d["summary"]
        assert "total_discount_amount" in d["summary"]
        assert "total_revenue" in d["summary"]
        assert "percent_of_revenue" in d["summary"]

    async def test_discount_analysis_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/discount-analysis?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_discount_analysis_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/discount-analysis?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestTopDebtors:
    """Tests for GET /reports/top-debtors."""

    async def test_top_debtors_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/top-debtors")
        assert response.status_code == 401

    async def test_top_debtors_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/top-debtors?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert "as_at_date" in d
        assert d["limit"] == 10
        assert "rows" in d
        assert "total_debt" in d
        for row in d.get("rows", []):
            assert "student_id" in row
            assert "student_name" in row
            assert "grade_name" in row
            assert "total_debt" in row
            assert "invoice_count" in row
            assert "oldest_due_date" in row

    async def test_top_debtors_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/top-debtors",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
