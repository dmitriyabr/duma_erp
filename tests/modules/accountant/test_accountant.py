"""Tests for Accountant API: audit trail and exports."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit.service import create_audit_log
from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


async def _get_token(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> str:
    """Create user and return access token."""
    auth = AuthService(db_session)
    await auth.create_user(
        email="accountant_test@test.com",
        password="Pass123",
        full_name="Test User",
        role=role,
    )
    await db_session.commit()
    _, token, _ = await auth.authenticate("accountant_test@test.com", "Pass123")
    return token


class TestAccountantAuditTrail:
    """Tests for GET /accountant/audit-trail."""

    async def test_audit_trail_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get("/api/v1/accountant/audit-trail")
        assert response.status_code == 401

    async def test_audit_trail_accountant_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can list audit trail."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        await create_audit_log(
            db_session,
            action="CREATE",
            entity_type="Payment",
            entity_id=1,
            user_id=None,
            entity_identifier="PAY-2026-000001",
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/accountant/audit-trail",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["total"] >= 1
        assert len(data["data"]["items"]) >= 1
        item = data["data"]["items"][0]
        assert item["entity_type"] == "Payment"
        assert item["entity_identifier"] == "PAY-2026-000001"
        assert item["action"] == "CREATE"

    async def test_audit_trail_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can list audit trail."""
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/accountant/audit-trail",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_audit_trail_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access accountant audit trail."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/accountant/audit-trail",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestAccountantExportStudentPayments:
    """Tests for GET /accountant/export/student-payments."""

    async def test_export_student_payments_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv"
        )
        assert response.status_code == 401

    async def test_export_student_payments_accountant_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can export student payments as CSV."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        text = response.text
        assert "Receipt Date" in text
        assert "Receipt#" in text
        assert "Student Name" in text
        assert "Amount" in text

    async def test_export_student_payments_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access export."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_export_procurement_payments_accountant_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can export procurement payments as CSV."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/accountant/export/procurement-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        text = response.text
        assert "Payment Date" in text
        assert "Payment#" in text
        assert "Supplier" in text
        assert "PO#" in text
