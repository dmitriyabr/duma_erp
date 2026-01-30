"""Tests for school settings API and service."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.school_settings.service import get_school_settings, update_school_settings
from src.core.school_settings.schemas import SchoolSettingsUpdate


async def _get_token(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> str:
    """Create user and return access token."""
    auth = AuthService(db_session)
    await auth.create_user(
        email="school_settings@test.com",
        password="Pass123",
        full_name="Test User",
        role=role,
    )
    await db_session.commit()
    _, token, _ = await auth.authenticate("school_settings@test.com", "Pass123")
    return token


class TestSchoolSettingsService:
    """Tests for school settings service."""

    async def test_get_school_settings_creates_default_row(self, db_session: AsyncSession):
        """get_school_settings creates a row with defaults when table is empty."""
        row = await get_school_settings(db_session)
        assert row.id is not None
        assert row.school_name == "" or row.school_name is None
        assert row.use_paybill is True
        assert row.use_bank_transfer is False
        assert row.logo_attachment_id is None
        assert row.stamp_attachment_id is None

    async def test_get_school_settings_returns_same_row(self, db_session: AsyncSession):
        """get_school_settings returns the same row on second call (no duplicate)."""
        row1 = await get_school_settings(db_session)
        await db_session.commit()
        row2 = await get_school_settings(db_session)
        assert row1.id == row2.id

    async def test_update_school_settings_partial(self, db_session: AsyncSession):
        """update_school_settings updates only provided fields."""
        row = await get_school_settings(db_session)
        await db_session.commit()
        updated = await update_school_settings(
            db_session,
            SchoolSettingsUpdate(school_name="Test School", use_bank_transfer=True),
        )
        await db_session.commit()
        assert updated.id == row.id
        assert updated.school_name == "Test School"
        assert updated.use_bank_transfer is True
        assert updated.use_paybill is True  # unchanged default
        assert updated.bank_name == "" or updated.bank_name is None  # unchanged

    async def test_update_school_settings_all_fields(self, db_session: AsyncSession):
        """update_school_settings can set all text and flag fields."""
        await get_school_settings(db_session)
        await db_session.commit()
        data = SchoolSettingsUpdate(
            school_name="My School",
            school_address="123 Street",
            school_phone="+254700000000",
            school_email="info@school.co.ke",
            use_paybill=True,
            mpesa_business_number="123456",
            use_bank_transfer=True,
            bank_name="ABC Bank",
            bank_account_name="School Ltd",
            bank_account_number="1234567890",
            bank_branch="Nairobi",
            bank_swift_code="ABCBKENA",
        )
        updated = await update_school_settings(db_session, data)
        await db_session.commit()
        assert updated.school_name == "My School"
        assert updated.school_address == "123 Street"
        assert updated.mpesa_business_number == "123456"
        assert updated.use_bank_transfer is True
        assert updated.bank_name == "ABC Bank"
        assert updated.bank_swift_code == "ABCBKENA"


class TestSchoolSettingsEndpoints:
    """Tests for school settings API endpoints."""

    async def test_get_school_settings_requires_auth(self, client: AsyncClient):
        """GET /school-settings without token returns 401."""
        response = await client.get("/api/v1/school-settings")
        assert response.status_code == 401

    async def test_get_school_settings_returns_defaults(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /school-settings returns default row (any authenticated user)."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/school-settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        body = data["data"]
        assert "id" in body
        assert body["school_name"] == ""
        assert body["use_paybill"] is True
        assert body["use_bank_transfer"] is False
        assert body["logo_attachment_id"] is None
        assert body["stamp_attachment_id"] is None

    async def test_put_school_settings_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """PUT /school-settings as Admin updates and returns data."""
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.put(
            "/api/v1/school-settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "school_name": "API Test School",
                "use_paybill": True,
                "mpesa_business_number": "999888",
                "use_bank_transfer": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["school_name"] == "API Test School"
        assert data["data"]["mpesa_business_number"] == "999888"
        assert data["data"]["use_paybill"] is True
        assert data["data"]["use_bank_transfer"] is False

        get_resp = await client.get(
            "/api/v1/school-settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["school_name"] == "API Test School"

    async def test_put_school_settings_super_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """PUT /school-settings as SuperAdmin succeeds."""
        token = await _get_token(client, db_session, UserRole.SUPER_ADMIN)
        response = await client.put(
            "/api/v1/school-settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"school_name": "Super School", "use_bank_transfer": True},
        )
        assert response.status_code == 200
        assert response.json()["data"]["school_name"] == "Super School"
        assert response.json()["data"]["use_bank_transfer"] is True

    async def test_put_school_settings_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """PUT /school-settings as User returns 403."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.put(
            "/api/v1/school-settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"school_name": "Should Fail"},
        )
        assert response.status_code == 403

    async def test_put_school_settings_accountant_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """PUT /school-settings as Accountant returns 403."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.put(
            "/api/v1/school-settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"school_name": "Should Fail"},
        )
        assert response.status_code == 403
