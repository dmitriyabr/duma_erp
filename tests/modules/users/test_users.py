import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.modules.users.schemas import UserCreate, UserUpdate, UserListFilters
from src.modules.users.service import UserService


class TestUserService:
    """Tests for UserService."""

    async def test_create_user_with_password(self, db_session: AsyncSession):
        """Test creating a user with system access."""
        service = UserService(db_session)

        user = await service.create(
            UserCreate(
                email="employee@school.com",
                password="Password123",
                full_name="John Doe",
                role=UserRole.USER,
            ),
            created_by_id=1,
        )

        assert user.id is not None
        assert user.email == "employee@school.com"
        assert user.full_name == "John Doe"
        assert user.role == "User"
        assert user.can_login is True
        assert user.is_active is True

    async def test_create_user_without_password(self, db_session: AsyncSession):
        """Test creating a user without system access (e.g., guard)."""
        service = UserService(db_session)

        user = await service.create(
            UserCreate(
                email="guard@school.com",
                password=None,
                full_name="Security Guard",
                role=UserRole.USER,
            ),
            created_by_id=1,
        )

        assert user.id is not None
        assert user.can_login is False
        assert user.password_hash is None

    async def test_create_user_duplicate_email(self, db_session: AsyncSession):
        """Test that duplicate email raises error."""
        service = UserService(db_session)

        await service.create(
            UserCreate(
                email="test@school.com",
                full_name="User 1",
                role=UserRole.USER,
            ),
            created_by_id=1,
        )

        with pytest.raises(DuplicateError):
            await service.create(
                UserCreate(
                    email="test@school.com",
                    full_name="User 2",
                    role=UserRole.USER,
                ),
                created_by_id=1,
            )

    async def test_list_users_with_filters(self, db_session: AsyncSession):
        """Test listing users with filters."""
        service = UserService(db_session)

        # Create test users
        await service.create(
            UserCreate(email="admin1@school.com", full_name="Admin One", role=UserRole.ADMIN),
            created_by_id=1,
        )
        await service.create(
            UserCreate(email="user1@school.com", full_name="User One", role=UserRole.USER),
            created_by_id=1,
        )
        await service.create(
            UserCreate(email="user2@school.com", full_name="User Two", role=UserRole.USER),
            created_by_id=1,
        )

        # List all
        users, total = await service.list_users(UserListFilters())
        assert total == 3

        # Filter by role
        users, total = await service.list_users(UserListFilters(role=UserRole.USER))
        assert total == 2

        # Search by name
        users, total = await service.list_users(UserListFilters(search="One"))
        assert total == 2  # Admin One and User One

    async def test_update_user(self, db_session: AsyncSession):
        """Test updating user data."""
        service = UserService(db_session)

        user = await service.create(
            UserCreate(email="test@school.com", full_name="Old Name", role=UserRole.USER),
            created_by_id=1,
        )

        updated = await service.update(
            user.id,
            UserUpdate(full_name="New Name", phone="+254712345678"),
            updated_by_id=1,
        )

        assert updated.full_name == "New Name"
        assert updated.phone == "+254712345678"

    async def test_deactivate_activate_user(self, db_session: AsyncSession):
        """Test deactivating and activating user."""
        service = UserService(db_session)

        user = await service.create(
            UserCreate(email="test@school.com", full_name="Test User", role=UserRole.USER),
            created_by_id=1,
        )
        assert user.is_active is True

        # Deactivate
        user = await service.deactivate(user.id, deactivated_by_id=1)
        assert user.is_active is False

        # Try deactivate again - should fail
        with pytest.raises(ValidationError):
            await service.deactivate(user.id, deactivated_by_id=1)

        # Activate
        user = await service.activate(user.id, activated_by_id=1)
        assert user.is_active is True

    async def test_set_password(self, db_session: AsyncSession):
        """Test setting password for user without access."""
        service = UserService(db_session)

        # Create user without password
        user = await service.create(
            UserCreate(email="guard@school.com", full_name="Guard", role=UserRole.USER),
            created_by_id=1,
        )
        assert user.can_login is False

        # Set password
        user = await service.set_password(user.id, "NewPassword123", set_by_id=1)
        assert user.can_login is True

    async def test_remove_password(self, db_session: AsyncSession):
        """Test removing password (revoking access)."""
        service = UserService(db_session)

        user = await service.create(
            UserCreate(
                email="test@school.com",
                password="Password123",
                full_name="Test User",
                role=UserRole.USER,
            ),
            created_by_id=1,
        )
        assert user.can_login is True

        user = await service.remove_password(user.id, removed_by_id=1)
        assert user.can_login is False

    async def test_change_own_password(self, db_session: AsyncSession):
        """Test user changing own password."""
        service = UserService(db_session)

        user = await service.create(
            UserCreate(
                email="test@school.com",
                password="OldPassword123",
                full_name="Test User",
                role=UserRole.USER,
            ),
            created_by_id=1,
        )

        # Change password
        user = await service.change_own_password(
            user.id,
            current_password="OldPassword123",
            new_password="NewPassword456",
        )

        # Verify new password works
        auth_service = AuthService(db_session)
        authenticated_user, _, _ = await auth_service.authenticate(
            "test@school.com", "NewPassword456"
        )
        assert authenticated_user.id == user.id


class TestUserEndpoints:
    """Tests for user API endpoints."""

    async def _create_super_admin(self, db_session: AsyncSession) -> tuple[str, int]:
        """Helper to create super admin and get token."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="superadmin@school.com",
            password="SuperAdmin123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        _, access_token, _ = await auth_service.authenticate(
            "superadmin@school.com", "SuperAdmin123"
        )
        return access_token, user.id

    async def test_list_users_unauthorized(self, client: AsyncClient):
        """Test that unauthorized users cannot list users."""
        response = await client.get("/api/v1/users")
        assert response.status_code == 401

    async def test_list_users_as_super_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test listing users as super admin."""
        token, _ = await self._create_super_admin(db_session)

        response = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] >= 1

    async def test_create_user(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a user via API."""
        token, _ = await self._create_super_admin(db_session)

        response = await client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "newuser@school.com",
                "password": "Password123",
                "full_name": "New User",
                "role": "User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == "newuser@school.com"
        assert data["data"]["can_login"] is True

    async def test_create_user_without_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test creating a user without system access."""
        token, _ = await self._create_super_admin(db_session)

        response = await client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "guard@school.com",
                "full_name": "Security Guard",
                "role": "User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["can_login"] is False

    async def test_change_own_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test user changing own password."""
        token, _ = await self._create_super_admin(db_session)

        response = await client.post(
            "/api/v1/users/me/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "SuperAdmin123",
                "new_password": "NewPassword456",
            },
        )

        assert response.status_code == 200

        # Verify new password works
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "superadmin@school.com", "password": "NewPassword456"},
        )
        assert login_response.status_code == 200
