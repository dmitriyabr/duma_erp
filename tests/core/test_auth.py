import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import AuthenticationError, DuplicateError


class TestAuthService:
    """Tests for AuthService."""

    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a new user."""
        auth_service = AuthService(db_session)

        user = await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )

        assert user.id is not None
        assert user.email == "test@school.com"
        assert user.full_name == "Test User"
        assert user.role == "Admin"
        assert user.is_active is True
        assert user.password_hash != "Password123"  # Password should be hashed

    async def test_create_user_duplicate_email(self, db_session: AsyncSession):
        """Test that duplicate email raises error."""
        auth_service = AuthService(db_session)

        await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )

        with pytest.raises(DuplicateError) as exc_info:
            await auth_service.create_user(
                email="test@school.com",
                password="AnotherPass123",
                full_name="Another User",
                role=UserRole.USER,
            )

        assert "already exists" in str(exc_info.value)

    async def test_authenticate_success(self, db_session: AsyncSession):
        """Test successful authentication."""
        auth_service = AuthService(db_session)

        await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )

        user, access_token, refresh_token = await auth_service.authenticate(
            email="test@school.com",
            password="Password123",
        )

        assert user.email == "test@school.com"
        assert access_token is not None
        assert refresh_token is not None

    async def test_authenticate_wrong_password(self, db_session: AsyncSession):
        """Test authentication with wrong password."""
        auth_service = AuthService(db_session)

        await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )

        with pytest.raises(AuthenticationError):
            await auth_service.authenticate(
                email="test@school.com",
                password="WrongPassword",
            )

    async def test_authenticate_inactive_user(self, db_session: AsyncSession):
        """Test authentication with inactive user."""
        auth_service = AuthService(db_session)

        user = await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )
        user.is_active = False
        await db_session.flush()

        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate(
                email="test@school.com",
                password="Password123",
            )

        assert "deactivated" in str(exc_info.value)


class TestAuthEndpoints:
    """Tests for auth API endpoints."""

    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test login endpoint."""
        # Create user first
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@school.com", "password": "Password123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user"]["email"] == "test@school.com"

    async def test_login_wrong_credentials(self, client: AsyncClient):
        """Test login with wrong credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@school.com", "password": "WrongPass"},
        )

        assert response.status_code == 401

    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test /me endpoint without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_get_me_authorized(self, client: AsyncClient, db_session: AsyncSession):
        """Test /me endpoint with valid token."""
        # Create user and login
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="test@school.com",
            password="Password123",
            full_name="Test User",
            role=UserRole.ADMIN,
        )
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@school.com", "password": "Password123"},
        )
        access_token = login_response.json()["data"]["access_token"]

        # Get user info
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["email"] == "test@school.com"
