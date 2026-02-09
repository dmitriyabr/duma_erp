import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService


@pytest.mark.asyncio
async def test_update_user_role_endpoint_does_not_500(client: AsyncClient, db_session: AsyncSession):
    auth = AuthService(db_session)

    await auth.create_user(
        email="sa_update_role@test.com",
        password="Pass12345",
        full_name="Super Admin",
        role=UserRole.SUPER_ADMIN,
    )
    _, token, _ = await auth.authenticate("sa_update_role@test.com", "Pass12345")

    employee = await auth.create_user(
        email="employee_update_role@test.com",
        password="Pass12345",
        full_name="Employee",
        role=UserRole.USER,
    )

    res = await client.put(
        f"/api/v1/users/{employee.id}",
        json={"role": "Admin"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["id"] == employee.id
    assert data["role"] == "Admin"
    assert data.get("updated_at") is not None

