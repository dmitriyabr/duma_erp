"""Tests for Reports API: GET /api/v1/reports/aged-receivables (Admin/SuperAdmin only)."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


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
