"""Tests for Reports API: GET aged-receivables, GET student-fees (Admin/SuperAdmin only)."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.invoices.models import Invoice, InvoiceStatus
from src.modules.students.models import Gender, Grade, Student, StudentStatus
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

    async def test_aged_receivables_respects_as_at_date_snapshot(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Aged receivables is a snapshot as at date:
        - invoices issued after as_at_date must be excluded
        - last_payment_date must be <= as_at_date
        """
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="reports_ar_snapshot_admin@test.com",
            password="Pass123",
            full_name="Test Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()

        grade = Grade(code="G2", name="Grade 2", display_order=2, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-2026-008888",
            first_name="Aged",
            last_name="Snapshot",
            gender=Gender.FEMALE.value,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Parent",
            guardian_phone="+254700000001",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        # Invoice issued after as_at_date (should not appear)
        future_inv = Invoice(
            invoice_number="INV-2026-888888",
            student_id=student.id,
            term_id=None,
            invoice_type="school_fee",
            status=InvoiceStatus.ISSUED.value,
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 2, 10),
            subtotal=Decimal("200.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("200.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("200.00"),
            created_by_id=user.id,
        )
        db_session.add(future_inv)

        # Future payment (should not be used as last_payment_date for as_at_date=2026-01-31)
        from src.modules.payments.models import Payment

        future_pay = Payment(
            payment_number="PAY-2026-888888",
            receipt_number="RCP-2026-888888",
            student_id=student.id,
            amount=Decimal("50.00"),
            payment_method="mpesa",
            payment_date=date(2026, 2, 5),
            status="completed",
            received_by_id=user.id,
        )
        db_session.add(future_pay)
        await db_session.commit()

        _, token, _ = await auth.authenticate("reports_ar_snapshot_admin@test.com", "Pass123")
        response = await client.get(
            "/api/v1/reports/aged-receivables?as_at_date=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["as_at_date"] == "2026-01-31"
        assert d["rows"] == []

    async def test_aged_receivables_format_xlsx_returns_excel(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """With format=xlsx returns Excel file (binary) and Content-Disposition."""
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/aged-receivables",
            params={"format": "xlsx"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "").lower()
        assert "aged-receivables.xlsx" in response.headers.get("content-disposition", "")
        body = response.content
        assert len(body) > 100
        # XLSX is a zip; first bytes are PK
        assert body[:2] == b"PK"

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

    async def test_profit_loss_math_uses_gross_less_discounts(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Validate Profit & Loss math:
        gross_revenue = sum(invoice.subtotal)
        total_discounts = sum(invoice.discount_total)
        net_revenue = gross - discounts (= sum(invoice.total))
        """
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="reports_pl_math_admin@test.com",
            password="Pass123",
            full_name="Test Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()

        grade = Grade(code="G1", name="Grade 1", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-2026-009999",
            first_name="John",
            last_name="Doe",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Parent",
            guardian_phone="+254700000000",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        inv = Invoice(
            invoice_number="INV-2026-999999",
            student_id=student.id,
            term_id=None,
            invoice_type="school_fee",
            status=InvoiceStatus.ISSUED.value,
            issue_date=date(2026, 1, 15),
            due_date=date(2026, 1, 31),
            subtotal=Decimal("100.00"),
            discount_total=Decimal("10.00"),
            total=Decimal("90.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("90.00"),
            created_by_id=user.id,
        )
        db_session.add(inv)
        await db_session.commit()

        _, token, _ = await auth.authenticate("reports_pl_math_admin@test.com", "Pass123")
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]

        assert Decimal(d["gross_revenue"]) == Decimal("100.00")
        assert Decimal(d["total_discounts"]) == Decimal("10.00")
        assert Decimal(d["net_revenue"]) == Decimal("90.00")
        assert Decimal(d["total_expenses"]) == Decimal("0.00")
        assert Decimal(d["net_profit"]) == Decimal("90.00")
        assert any(
            r["label"] == "School Fee" and Decimal(r["amount"]) == Decimal("100.00")
            for r in d["revenue_lines"]
        )

    async def test_profit_loss_expenses_breakdown_by_purpose(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Expenses should be broken down by ProcurementPayment purpose/category."""
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="reports_pl_exp_admin@test.com",
            password="Pass123",
            full_name="Test Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()

        from src.modules.procurement.models import PaymentPurpose, ProcurementPayment

        uniforms = PaymentPurpose(name="Uniforms", purpose_type="expense", is_active=True)
        stationery = PaymentPurpose(name="Stationery", purpose_type="expense", is_active=True)
        db_session.add_all([uniforms, stationery])
        await db_session.flush()

        p1 = ProcurementPayment(
            payment_number="PP-2026-000001",
            po_id=None,
            purpose_id=uniforms.id,
            payee_name="ABC",
            payment_date=date(2026, 1, 10),
            amount=Decimal("1000.00"),
            payment_method="bank",
            company_paid=True,
            status="posted",
            created_by_id=user.id,
        )
        p2 = ProcurementPayment(
            payment_number="PP-2026-000002",
            po_id=None,
            purpose_id=stationery.id,
            payee_name="XYZ",
            payment_date=date(2026, 1, 11),
            amount=Decimal("250.00"),
            payment_method="mpesa",
            company_paid=True,
            status="posted",
            created_by_id=user.id,
        )
        db_session.add_all([p1, p2])
        await db_session.commit()

        _, token, _ = await auth.authenticate("reports_pl_exp_admin@test.com", "Pass123")
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]

        exp = {r["label"]: Decimal(r["amount"]) for r in d["expense_lines"]}
        assert exp["Stationery"] == Decimal("250.00")
        assert exp["Uniforms"] == Decimal("1000.00")
        assert Decimal(d["total_expenses"]) == Decimal("1250.00")

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

    async def test_profit_loss_breakdown_monthly(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/profit-loss?date_from=2026-01-01&date_to=2026-03-31&breakdown=monthly",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["months"] == ["2026-01", "2026-02", "2026-03"]
        assert "gross_revenue_monthly" in d
        assert "net_profit_monthly" in d
        assert all(len(r.get("monthly") or {}) == 3 for r in d["revenue_lines"])
        assert all(len(e.get("monthly") or {}) == 3 for e in d["expense_lines"])


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

    async def test_balance_sheet_breakdown_monthly(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/balance-sheet?as_at_date=2026-03-31&date_from=2026-01-01&date_to=2026-03-31&breakdown=monthly",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["months"] == ["2026-01", "2026-02", "2026-03"]
        assert "debt_to_asset_percent_monthly" in d
        assert "current_ratio_monthly" in d

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


class TestProcurementSummary:
    """Tests for GET /reports/procurement-summary."""

    async def test_procurement_summary_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/procurement-summary?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_procurement_summary_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/procurement-summary?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "rows" in d
        assert "total_po_count" in d
        assert "total_amount" in d
        assert "total_paid" in d
        assert "total_outstanding" in d
        assert "outstanding_breakdown" in d
        assert "current_0_30" in d["outstanding_breakdown"]
        assert "bucket_31_60" in d["outstanding_breakdown"]
        assert "bucket_61_plus" in d["outstanding_breakdown"]

    async def test_procurement_summary_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/procurement-summary?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_procurement_summary_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/procurement-summary?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestInventoryValuation:
    """Tests for GET /reports/inventory-valuation."""

    async def test_inventory_valuation_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/inventory-valuation")
        assert response.status_code == 401

    async def test_inventory_valuation_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/inventory-valuation?as_at_date=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["as_at_date"] == "2026-01-31"
        assert "rows" in d
        assert "total_items" in d
        assert "total_quantity" in d
        assert "total_value" in d

    async def test_inventory_valuation_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/inventory-valuation",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestLowStockAlert:
    """Tests for GET /reports/low-stock-alert."""

    async def test_low_stock_alert_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/low-stock-alert")
        assert response.status_code == 401

    async def test_low_stock_alert_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/low-stock-alert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert "rows" in d
        assert "total_low_count" in d
        for row in d.get("rows", []):
            assert "item_id" in row
            assert "item_name" in row
            assert "current" in row
            assert "min_level" in row
            assert "status" in row

    async def test_low_stock_alert_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/low-stock-alert",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestStockMovement:
    """Tests for GET /reports/stock-movement."""

    async def test_stock_movement_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/stock-movement?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_stock_movement_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/stock-movement?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "rows" in d
        for row in d.get("rows", []):
            assert "movement_id" in row
            assert "movement_date" in row
            assert "movement_type" in row
            assert "item_name" in row
            assert "quantity" in row
            assert "balance_after" in row
            assert "created_by_name" in row

    async def test_stock_movement_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/stock-movement?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_stock_movement_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/stock-movement?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestCompensationSummary:
    """Tests for GET /reports/compensation-summary."""

    async def test_compensation_summary_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/compensation-summary?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_compensation_summary_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/compensation-summary?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "rows" in d
        assert "summary" in d
        assert "total_claims" in d["summary"]
        assert "total_amount" in d["summary"]
        assert "pending_approval_count" in d["summary"]
        assert "approved_unpaid_count" in d["summary"]

    async def test_compensation_summary_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/compensation-summary?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_compensation_summary_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/compensation-summary?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestExpenseClaimsByCategory:
    """Tests for GET /reports/expense-claims-by-category."""

    async def test_expense_claims_by_category_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/expense-claims-by-category?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_expense_claims_by_category_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/expense-claims-by-category?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "rows" in d
        assert "total_amount" in d

    async def test_expense_claims_by_category_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/expense-claims-by-category?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_expense_claims_by_category_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/expense-claims-by-category?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestRevenueTrend:
    """Tests for GET /reports/revenue-trend."""

    async def test_revenue_trend_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/revenue-trend")
        assert response.status_code == 401

    async def test_revenue_trend_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/revenue-trend?years=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert "rows" in d
        assert len(d["rows"]) == 3
        assert "growth_percent" in d
        assert "years_included" in d

    async def test_revenue_trend_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/revenue-trend",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestPaymentMethodDistribution:
    """Tests for GET /reports/payment-method-distribution."""

    async def test_payment_method_distribution_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/payment-method-distribution?date_from=2026-01-01&date_to=2026-01-31"
        )
        assert response.status_code == 401

    async def test_payment_method_distribution_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/payment-method-distribution?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["date_from"] == "2026-01-01"
        assert d["date_to"] == "2026-01-31"
        assert "rows" in d
        assert "total_amount" in d

    async def test_payment_method_distribution_400_if_date_from_after_date_to(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/payment-method-distribution?date_from=2026-01-31&date_to=2026-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_payment_method_distribution_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/payment-method-distribution?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestTermComparison:
    """Tests for GET /reports/term-comparison."""

    async def test_term_comparison_requires_auth(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/reports/term-comparison?term1_id=1&term2_id=2"
        )
        assert response.status_code == 401

    async def test_term_comparison_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        from src.core.auth.service import AuthService
        from src.modules.terms.models import Term, TermStatus
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="reports_tc_admin@test.com",
            password="Pass123",
            full_name="Test Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()
        t1 = Term(
            year=2025,
            term_number=1,
            display_name="2025-T1",
            status=TermStatus.CLOSED.value,
            created_by_id=user.id,
        )
        t2 = Term(
            year=2025,
            term_number=2,
            display_name="2025-T2",
            status=TermStatus.CLOSED.value,
            created_by_id=user.id,
        )
        db_session.add(t1)
        db_session.add(t2)
        await db_session.flush()
        token = await _get_token(client, db_session, UserRole.ADMIN, "_tc")
        response = await client.get(
            f"/api/v1/reports/term-comparison?term1_id={t1.id}&term2_id={t2.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert d["term1_display_name"] == "2025-T1"
        assert d["term2_display_name"] == "2025-T2"
        assert "metrics" in d
        assert len(d["metrics"]) >= 1

    async def test_term_comparison_404_if_term_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/term-comparison?term1_id=99999&term2_id=99998",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_term_comparison_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/term-comparison?term1_id=1&term2_id=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestKpis:
    """Tests for GET /reports/kpis."""

    async def test_kpis_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/reports/kpis")
        assert response.status_code == 401

    async def test_kpis_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/reports/kpis?year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        d = response.json()["data"]
        assert "period_type" in d
        assert "active_students_count" in d
        assert "total_revenue" in d
        assert "total_invoiced" in d
        assert "collection_rate_percent" in d
        assert "total_expenses" in d
        assert "student_debt" in d
        assert "supplier_debt" in d

    async def test_kpis_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/reports/kpis",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
