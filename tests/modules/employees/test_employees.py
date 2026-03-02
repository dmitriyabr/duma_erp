from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.employees.models import EmployeeStatus
from src.modules.employees.schemas import EmployeeCreate, EmployeeListFilters, EmployeeUpdate
from src.modules.employees.service import EmployeeService


class TestEmployeeService:
    """Tests for EmployeeService."""

    async def test_create_employee(self, db_session: AsyncSession) -> None:
        service = EmployeeService(db_session)

        employee = await service.create_employee(
            EmployeeCreate(
                surname="Doe",
                first_name="John",
                job_title="Teacher",
                mobile_phone="0712345678",
                salary="45000.00",
            ),
            created_by_id=1,
        )

        assert employee.id is not None
        assert employee.employee_number.startswith("EMP-")
        assert employee.surname == "Doe"
        assert employee.first_name == "John"
        assert employee.job_title == "Teacher"
        assert employee.status == EmployeeStatus.ACTIVE.value
        assert str(employee.salary) == "45000.00"

    async def test_list_employees_filters(self, db_session: AsyncSession) -> None:
        service = EmployeeService(db_session)

        await service.create_employee(
            EmployeeCreate(surname="One", first_name="Alice", job_title="Teacher"),
            created_by_id=1,
        )
        await service.create_employee(
            EmployeeCreate(surname="Two", first_name="Bob", job_title="Guard"),
            created_by_id=1,
        )

        employees, total = await service.list_employees(EmployeeListFilters())
        assert total == 2
        assert len(employees) == 2

        employees, total = await service.list_employees(EmployeeListFilters(search="Alice"))
        assert total == 1
        assert employees[0].first_name == "Alice"

    async def test_update_employee_can_clear_nullable_fields(
        self, db_session: AsyncSession
    ) -> None:
        service = EmployeeService(db_session)
        employee = await service.create_employee(
            EmployeeCreate(
                surname="Clear",
                first_name="Field",
                email="clear@example.com",
                mobile_phone="0711111111",
            ),
            created_by_id=1,
        )

        updated = await service.update_employee(
            employee,
            EmployeeUpdate(email=None, mobile_phone=None),
        )
        assert updated.email is None
        assert updated.mobile_phone is None

    async def test_import_from_csv_parses_google_style_dates(
        self, db_session: AsyncSession
    ) -> None:
        service = EmployeeService(db_session)
        csv_content = (
            "Surname / Last Name,First Name,Date of Birth,Employee Start Date\n"
            "Date,Tester,3/2/2026,12/15/2025 00:00:00\n"
        )

        result = await service.import_from_csv(csv_content, created_by_id=1)
        assert result.rows_processed == 1
        assert result.employees_created == 1

        employees, total = await service.list_employees(EmployeeListFilters(search="Date"))
        assert total == 1
        assert employees[0].date_of_birth is not None
        assert employees[0].employee_start_date is not None

    async def test_import_does_not_overwrite_existing_date_with_empty_value(
        self, db_session: AsyncSession
    ) -> None:
        service = EmployeeService(db_session)
        existing = await service.create_employee(
            EmployeeCreate(
                surname="Keep",
                first_name="Date",
                employee_start_date="2026-01-06",
                national_id_number="999001",
            ),
            created_by_id=1,
        )

        csv_content = (
            "Surname / Last Name,First Name,Employee Start Date,National ID Number\n"
            "Keep,Date,,999001\n"
        )
        result = await service.import_from_csv(csv_content, created_by_id=1)
        assert result.employees_updated == 1

        refreshed = await service.get_employee(existing.id)
        assert refreshed is not None
        assert str(refreshed.employee_start_date) == "2026-01-06"


class TestEmployeeEndpoints:
    """Tests for employee API endpoints."""

    async def _create_super_admin(
        self,
        db_session: AsyncSession,
    ) -> tuple[str, int]:
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="superadmin@school.com",
            password="SuperAdmin123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        _, access_token, _ = await auth_service.authenticate("superadmin@school.com", "SuperAdmin123")
        return access_token, user.id

    async def _create_accountant(
        self,
        db_session: AsyncSession,
    ) -> tuple[str, int]:
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="accountant@school.com",
            password="Accountant123",
            full_name="Accountant",
            role=UserRole.ACCOUNTANT,
        )
        await db_session.commit()
        _, access_token, _ = await auth_service.authenticate(
            "accountant@school.com", "Accountant123"
        )
        return access_token, user.id

    async def test_list_employees_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/employees")
        assert response.status_code == 401

    async def test_create_and_list_employees(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        token, _ = await self._create_super_admin(db_session)

        response = await client.post(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "surname": "Doe",
                "first_name": "John",
                "job_title": "Teacher",
                "mobile_phone": "0712345678",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        emp_id = data["data"]["id"]

        list_resp = await client.get("/api/v1/employees", headers={"Authorization": f"Bearer {token}"})
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["data"]["total"] >= 1
        assert any(item["id"] == emp_id for item in list_data["data"]["items"])

    async def test_delete_employee(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        token, _ = await self._create_super_admin(db_session)

        create_resp = await client.post(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={"surname": "Delete", "first_name": "Me"},
        )
        assert create_resp.status_code == 201
        employee_id = create_resp.json()["data"]["id"]

        delete_resp = await client.delete(
            f"/api/v1/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["data"]["deleted"] is True

        get_resp = await client.get(
            f"/api/v1/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 404

    async def test_export_employees_csv(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        token, _ = await self._create_super_admin(db_session)
        create_resp = await client.post(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={"surname": "Csv", "first_name": "Export"},
        )
        assert create_resp.status_code == 201

        export_resp = await client.get(
            "/api/v1/employees/export?format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert export_resp.status_code == 200
        assert "text/csv" in export_resp.headers.get("content-type", "")
        disposition = export_resp.headers.get("content-disposition", "")
        assert "attachment;" in disposition
        assert "employees_" in disposition
        assert "Csv" in export_resp.text

    async def test_accountant_can_view_but_cannot_modify(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        admin_token, _ = await self._create_super_admin(db_session)
        acct_token, _ = await self._create_accountant(db_session)

        create_resp = await client.post(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"surname": "Readonly", "first_name": "Case"},
        )
        assert create_resp.status_code == 201
        employee_id = create_resp.json()["data"]["id"]

        list_resp = await client.get(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {acct_token}"},
        )
        assert list_resp.status_code == 200

        get_resp = await client.get(
            f"/api/v1/employees/{employee_id}",
            headers={"Authorization": f"Bearer {acct_token}"},
        )
        assert get_resp.status_code == 200

        forbid_create = await client.post(
            "/api/v1/employees",
            headers={"Authorization": f"Bearer {acct_token}"},
            json={"surname": "No", "first_name": "Write"},
        )
        assert forbid_create.status_code == 403

