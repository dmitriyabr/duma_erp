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
