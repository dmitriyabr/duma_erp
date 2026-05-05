"""Tests for Dashboard API: GET /api/v1/dashboard (Admin/SuperAdmin only)."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


async def _get_token(
    client: AsyncClient, db_session: AsyncSession, role: UserRole, suffix: str = ""
) -> str:
    """Create user with given role and return access token."""
    email = f"dashboard_{role.value.lower()}{suffix}@test.com"
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


class TestDashboardAccess:
    """Tests for GET /dashboard (main page summary)."""

    async def test_dashboard_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get("/api/v1/dashboard")
        assert response.status_code == 401

    async def test_dashboard_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can get dashboard summary."""
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        d = data["data"]
        assert "active_students_count" in d
        assert "total_revenue_this_year" in d
        assert "this_term_revenue" in d
        assert "student_debts_total" in d
        assert "supplier_debt" in d
        assert "pending_grn_count" in d
        assert "current_year" in d

    async def test_dashboard_revenue_is_net_of_refunds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        from src.modules.billing_accounts.models import BillingAccount
        from src.modules.payments.models import Payment, PaymentRefund
        from src.modules.students.models import Gender, Grade, Student, StudentStatus
        from src.modules.terms.models import Term, TermStatus

        auth = AuthService(db_session)
        user = await auth.create_user(
            email="dashboard_net_refund_admin@test.com",
            password="Pass123",
            full_name="Dashboard Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()

        grade = Grade(code="DBR", name="Dashboard Refund", display_order=1, is_active=True)
        account = BillingAccount(
            account_number="FAM-2026-DBR001",
            display_name="Dashboard Refund Family",
            primary_guardian_name="Refund Parent",
            primary_guardian_phone="+254700000110",
            created_by_id=user.id,
        )
        term = Term(
            year=2026,
            term_number=1,
            display_name="2026-T1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=TermStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add_all([grade, account, term])
        await db_session.flush()

        student = Student(
            student_number="STU-2026-DBR001",
            first_name="Dashboard",
            last_name="Refund",
            gender=Gender.MALE.value,
            billing_account_id=account.id,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Refund Parent",
            guardian_phone="+254700000110",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        payment = Payment(
            payment_number="PAY-2026-DBR001",
            receipt_number="RCP-2026-DBR001",
            student_id=student.id,
            billing_account_id=account.id,
            amount=Decimal("100.00"),
            payment_method="mpesa",
            payment_date=date(2026, 1, 10),
            status="completed",
            received_by_id=user.id,
        )
        db_session.add(payment)
        await db_session.flush()

        db_session.add(
            PaymentRefund(
                payment_id=payment.id,
                billing_account_id=account.id,
                amount=Decimal("30.00"),
                refund_date=date(2026, 1, 20),
                reason="Dashboard refund",
                refunded_by_id=user.id,
            )
        )
        await db_session.commit()

        _, token, _ = await auth.authenticate("dashboard_net_refund_admin@test.com", "Pass123")
        response = await client.get(
            "/api/v1/dashboard?year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert Decimal(data["total_revenue_this_year"]) == Decimal("70.00")
        assert Decimal(data["this_term_revenue"]) == Decimal("70.00")

    async def test_dashboard_superadmin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """SuperAdmin can get dashboard summary."""
        token = await _get_token(client, db_session, UserRole.SUPER_ADMIN, "_sa")
        response = await client.get(
            "/api/v1/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json().get("success") is True

    async def test_dashboard_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access dashboard summary."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_dashboard_accountant_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant role cannot access dashboard summary."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
