"""Tests for Dashboard API: GET /api/v1/dashboard (Admin/SuperAdmin only)."""

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
        assert "total_revenue_this_year" in d
        assert "this_term_revenue" in d
        assert "student_debts_total" in d
        assert "supplier_debt" in d
        assert "pending_grn_count" in d
        assert "current_year" in d

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
