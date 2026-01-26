from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditAction, create_audit_log
from src.core.auth.models import User, UserRole
from src.core.auth.password import hash_password, verify_password
from src.core.exceptions import AuthenticationError, DuplicateError, NotFoundError, ValidationError
from src.modules.users.schemas import UserCreate, UserListFilters, UserUpdate


class UserService:
    """Service for user management operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(
        self, filters: UserListFilters
    ) -> tuple[list[User], int]:
        """
        List users with filters and pagination.

        Returns:
            Tuple of (users list, total count)
        """
        # Base query
        stmt = select(User)
        count_stmt = select(func.count(User.id))

        # Apply filters
        if filters.role:
            stmt = stmt.where(User.role == filters.role.value)
            count_stmt = count_stmt.where(User.role == filters.role.value)

        if filters.is_active is not None:
            stmt = stmt.where(User.is_active == filters.is_active)
            count_stmt = count_stmt.where(User.is_active == filters.is_active)

        if filters.search:
            search_term = f"%{filters.search}%"
            search_filter = or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Get total count
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply pagination and ordering
        offset = (filters.page - 1) * filters.limit
        stmt = stmt.order_by(User.full_name).offset(offset).limit(filters.limit)

        # Execute
        result = await self.session.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def create(
        self,
        data: UserCreate,
        created_by_id: int,
    ) -> User:
        """Create a new user (employee)."""
        # Check for duplicate email
        existing = await self.get_by_email(data.email)
        if existing:
            raise DuplicateError("User", "email", data.email)

        # Create user
        user = User(
            email=data.email,
            password_hash=hash_password(data.password) if data.password else None,
            full_name=data.full_name,
            phone=data.phone,
            role=data.role.value,
            is_active=True,
        )

        self.session.add(user)
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.CREATE,
            entity_type="User",
            entity_id=user.id,
            user_id=created_by_id,
            entity_identifier=user.email,
            new_values={
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "can_login": user.can_login,
            },
        )

        return user

    async def update(
        self,
        user_id: int,
        data: UserUpdate,
        updated_by_id: int,
    ) -> User:
        """Update user data."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        old_values = {
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
        }

        # Check email uniqueness if changing
        if data.email and data.email != user.email:
            existing = await self.get_by_email(data.email)
            if existing:
                raise DuplicateError("User", "email", data.email)
            user.email = data.email

        if data.full_name is not None:
            user.full_name = data.full_name

        if data.phone is not None:
            user.phone = data.phone

        if data.role is not None:
            user.role = data.role.value

        await self.session.flush()

        new_values = {
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
        }

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            user_id=updated_by_id,
            entity_identifier=user.email,
            old_values=old_values,
            new_values=new_values,
        )

        return user

    async def deactivate(self, user_id: int, deactivated_by_id: int) -> User:
        """Deactivate a user."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        if not user.is_active:
            raise ValidationError("User is already deactivated")

        user.is_active = False
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            user_id=deactivated_by_id,
            entity_identifier=user.email,
            old_values={"is_active": True},
            new_values={"is_active": False},
            comment="User deactivated",
        )

        return user

    async def activate(self, user_id: int, activated_by_id: int) -> User:
        """Activate a user."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        if user.is_active:
            raise ValidationError("User is already active")

        user.is_active = True
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            user_id=activated_by_id,
            entity_identifier=user.email,
            old_values={"is_active": False},
            new_values={"is_active": True},
            comment="User activated",
        )

        return user

    async def set_password(
        self,
        user_id: int,
        new_password: str,
        set_by_id: int,
    ) -> User:
        """Set or reset user password (by admin)."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        had_password = user.can_login
        user.password_hash = hash_password(new_password)
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            user_id=set_by_id,
            entity_identifier=user.email,
            old_values={"can_login": had_password},
            new_values={"can_login": True},
            comment="Password set by admin",
        )

        return user

    async def change_own_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> User:
        """Change own password (requires current password)."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        if not user.can_login:
            raise ValidationError("User does not have system access")

        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            user_id=user.id,
            entity_identifier=user.email,
            comment="Password changed by user",
        )

        return user

    async def remove_password(self, user_id: int, removed_by_id: int) -> User:
        """Remove user password (revoke system access)."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        if not user.can_login:
            raise ValidationError("User already does not have system access")

        user.password_hash = None
        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            user_id=removed_by_id,
            entity_identifier=user.email,
            old_values={"can_login": True},
            new_values={"can_login": False},
            comment="System access revoked",
        )

        return user
