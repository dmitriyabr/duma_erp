import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.modules.students.models import Gender, Grade, Student, StudentStatus
from src.modules.students.schemas import GradeCreate, GradeUpdate, StudentCreate, StudentUpdate
from src.modules.students.service import StudentService


class TestGradeService:
    """Tests for Grade management in StudentService."""

    async def test_create_grade(self, db_session: AsyncSession):
        """Test creating a grade."""
        service = StudentService(db_session)

        grade = await service.create_grade(
            GradeCreate(code="G7", name="Grade 7", display_order=10),
            created_by_id=1,
        )

        assert grade.id is not None
        assert grade.code == "G7"
        assert grade.name == "Grade 7"
        assert grade.display_order == 10
        assert grade.is_active is True

    async def test_create_grade_duplicate_code(self, db_session: AsyncSession):
        """Test that duplicate grade code raises error."""
        service = StudentService(db_session)

        await service.create_grade(
            GradeCreate(code="TEST", name="Test Grade", display_order=100),
            created_by_id=1,
        )

        with pytest.raises(DuplicateError):
            await service.create_grade(
                GradeCreate(code="TEST", name="Another Test", display_order=101),
                created_by_id=1,
            )

    async def test_list_grades(self, db_session: AsyncSession):
        """Test listing grades."""
        service = StudentService(db_session)

        # Create test grades
        g1 = await service.create_grade(
            GradeCreate(code="A1", name="Grade A1", display_order=1),
            created_by_id=1,
        )
        g2 = await service.create_grade(
            GradeCreate(code="A2", name="Grade A2", display_order=2),
            created_by_id=1,
        )

        grades = await service.list_grades(include_inactive=False)
        assert len(grades) >= 2
        # Verify order
        codes = [g.code for g in grades]
        assert codes.index("A1") < codes.index("A2")

    async def test_update_grade(self, db_session: AsyncSession):
        """Test updating a grade."""
        service = StudentService(db_session)

        grade = await service.create_grade(
            GradeCreate(code="UPD", name="Original", display_order=50),
            created_by_id=1,
        )

        updated = await service.update_grade(
            grade.id,
            GradeUpdate(name="Updated Name", is_active=False),
            updated_by_id=1,
        )

        assert updated.name == "Updated Name"
        assert updated.is_active is False


class TestStudentService:
    """Tests for StudentService."""

    async def _create_grade(self, db_session: AsyncSession) -> Grade:
        """Helper to create a test grade."""
        service = StudentService(db_session)
        return await service.create_grade(
            GradeCreate(code=f"TST{id(db_session)}", name="Test Grade", display_order=99),
            created_by_id=1,
        )

    async def test_create_student(self, db_session: AsyncSession):
        """Test creating a student."""
        grade = await self._create_grade(db_session)
        service = StudentService(db_session)

        student = await service.create_student(
            StudentCreate(
                first_name="John",
                last_name="Doe",
                gender=Gender.MALE,
                grade_id=grade.id,
                guardian_name="Jane Doe",
                guardian_phone="+254712345678",
                guardian_email="jane@example.com",
            ),
            created_by_id=1,
        )

        assert student.id is not None
        assert student.student_number.startswith("STU-")
        assert student.first_name == "John"
        assert student.last_name == "Doe"
        assert student.full_name == "John Doe"
        assert student.gender == "male"
        assert student.status == StudentStatus.ACTIVE.value
        assert student.guardian_phone == "+254712345678"

    async def test_create_student_phone_normalization(self, db_session: AsyncSession):
        """Test phone number normalization."""
        grade = await self._create_grade(db_session)
        service = StudentService(db_session)

        # Test with 0-format
        student = await service.create_student(
            StudentCreate(
                first_name="Alice",
                last_name="Smith",
                gender=Gender.FEMALE,
                grade_id=grade.id,
                guardian_name="Bob Smith",
                guardian_phone="0712345678",  # Local format
            ),
            created_by_id=1,
        )

        assert student.guardian_phone == "+254712345678"

    async def test_create_student_invalid_grade(self, db_session: AsyncSession):
        """Test creating student with invalid grade."""
        service = StudentService(db_session)

        with pytest.raises(NotFoundError):
            await service.create_student(
                StudentCreate(
                    first_name="Test",
                    last_name="User",
                    gender=Gender.MALE,
                    grade_id=99999,
                    guardian_name="Guardian",
                    guardian_phone="+254712345678",
                ),
                created_by_id=1,
            )

    async def test_list_students(self, db_session: AsyncSession):
        """Test listing students with filters."""
        grade = await self._create_grade(db_session)
        service = StudentService(db_session)

        # Create students
        await service.create_student(
            StudentCreate(
                first_name="Active",
                last_name="Student",
                gender=Gender.MALE,
                grade_id=grade.id,
                guardian_name="Guardian",
                guardian_phone="+254711111111",
            ),
            created_by_id=1,
        )

        students, total = await service.list_students()
        assert total >= 1

        # Filter by search
        students, total = await service.list_students(search="Active")
        assert total >= 1
        assert all("Active" in s.first_name or "Active" in s.last_name for s in students)

    async def test_list_active_students(self, db_session: AsyncSession):
        """Test listing only active students."""
        grade = await self._create_grade(db_session)
        service = StudentService(db_session)

        # Create active student
        active = await service.create_student(
            StudentCreate(
                first_name="Active",
                last_name="One",
                gender=Gender.MALE,
                grade_id=grade.id,
                guardian_name="Guardian",
                guardian_phone="+254711111111",
            ),
            created_by_id=1,
        )

        # Create inactive student
        inactive = await service.create_student(
            StudentCreate(
                first_name="Inactive",
                last_name="One",
                gender=Gender.FEMALE,
                grade_id=grade.id,
                guardian_name="Guardian",
                guardian_phone="+254722222222",
            ),
            created_by_id=1,
        )
        await service.deactivate_student(inactive.id, deactivated_by_id=1)

        # List active only
        active_students = await service.list_active_students(grade_id=grade.id)
        student_ids = [s.id for s in active_students]
        assert active.id in student_ids
        assert inactive.id not in student_ids

    async def test_update_student(self, db_session: AsyncSession):
        """Test updating a student."""
        grade = await self._create_grade(db_session)
        service = StudentService(db_session)

        student = await service.create_student(
            StudentCreate(
                first_name="Original",
                last_name="Name",
                gender=Gender.MALE,
                grade_id=grade.id,
                guardian_name="Guardian",
                guardian_phone="+254712345678",
            ),
            created_by_id=1,
        )

        updated = await service.update_student(
            student.id,
            StudentUpdate(first_name="Updated", notes="Some notes"),
            updated_by_id=1,
        )

        assert updated.first_name == "Updated"
        assert updated.last_name == "Name"
        assert updated.notes == "Some notes"

    async def test_activate_deactivate_student(self, db_session: AsyncSession):
        """Test activating and deactivating a student."""
        grade = await self._create_grade(db_session)
        service = StudentService(db_session)

        student = await service.create_student(
            StudentCreate(
                first_name="Test",
                last_name="Student",
                gender=Gender.MALE,
                grade_id=grade.id,
                guardian_name="Guardian",
                guardian_phone="+254712345678",
            ),
            created_by_id=1,
        )
        assert student.status == StudentStatus.ACTIVE.value

        # Deactivate
        student = await service.deactivate_student(student.id, deactivated_by_id=1)
        assert student.status == StudentStatus.INACTIVE.value

        # Try deactivate again - should fail
        with pytest.raises(ValidationError):
            await service.deactivate_student(student.id, deactivated_by_id=1)

        # Activate
        student = await service.activate_student(student.id, activated_by_id=1)
        assert student.status == StudentStatus.ACTIVE.value

        # Try activate again - should fail
        with pytest.raises(ValidationError):
            await service.activate_student(student.id, activated_by_id=1)


class TestStudentEndpoints:
    """Tests for student API endpoints."""

    async def _create_auth_and_grade(
        self, db_session: AsyncSession
    ) -> tuple[str, int, Grade]:
        """Helper to create super admin, get token, and create a grade."""
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

        # Create grade
        student_service = StudentService(db_session)
        grade = await student_service.create_grade(
            GradeCreate(code="API", name="API Test Grade", display_order=50),
            created_by_id=user.id,
        )

        return access_token, user.id, grade

    async def test_list_grades(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing grades via API."""
        token, _, _ = await self._create_auth_and_grade(db_session)

        response = await client.get(
            "/api/v1/students/grades",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_create_grade(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a grade via API."""
        token, _, _ = await self._create_auth_and_grade(db_session)

        response = await client.post(
            "/api/v1/students/grades",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "NEWG", "name": "New Grade", "display_order": 100},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["code"] == "NEWG"

    async def test_create_student(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a student via API."""
        token, _, grade = await self._create_auth_and_grade(db_session)

        response = await client.post(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "first_name": "API",
                "last_name": "Student",
                "gender": "male",
                "grade_id": grade.id,
                "guardian_name": "API Guardian",
                "guardian_phone": "+254712345678",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["first_name"] == "API"
        assert data["data"]["student_number"].startswith("STU-")
        assert data["data"]["grade_name"] == "API Test Grade"

    async def test_list_students(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing students via API."""
        token, _, grade = await self._create_auth_and_grade(db_session)

        # Create a student first
        await client.post(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "first_name": "List",
                "last_name": "Test",
                "gender": "female",
                "grade_id": grade.id,
                "guardian_name": "Guardian",
                "guardian_phone": "+254712345678",
            },
        )

        response = await client.get(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_search_students(self, client: AsyncClient, db_session: AsyncSession):
        """Test searching students via API."""
        token, _, grade = await self._create_auth_and_grade(db_session)

        # Create a student
        await client.post(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "first_name": "Searchable",
                "last_name": "Person",
                "gender": "male",
                "grade_id": grade.id,
                "guardian_name": "Search Guardian",
                "guardian_phone": "+254712345678",
            },
        )

        response = await client.get(
            "/api/v1/students?search=Searchable",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] >= 1

    async def test_deactivate_student(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test deactivating a student via API."""
        token, _, grade = await self._create_auth_and_grade(db_session)

        # Create a student
        create_response = await client.post(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "first_name": "Deactivate",
                "last_name": "Me",
                "gender": "female",
                "grade_id": grade.id,
                "guardian_name": "Guardian",
                "guardian_phone": "+254712345678",
            },
        )
        student_id = create_response.json()["data"]["id"]

        # Deactivate
        response = await client.post(
            f"/api/v1/students/{student_id}/deactivate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "inactive"

    async def test_activate_student(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test activating a student via API."""
        token, _, grade = await self._create_auth_and_grade(db_session)

        # Create and deactivate a student
        create_response = await client.post(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "first_name": "Activate",
                "last_name": "Me",
                "gender": "male",
                "grade_id": grade.id,
                "guardian_name": "Guardian",
                "guardian_phone": "+254712345678",
            },
        )
        student_id = create_response.json()["data"]["id"]

        await client.post(
            f"/api/v1/students/{student_id}/deactivate",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Activate
        response = await client.post(
            f"/api/v1/students/{student_id}/activate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "active"

    async def test_phone_validation_invalid(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that invalid phone numbers are rejected."""
        token, _, grade = await self._create_auth_and_grade(db_session)

        response = await client.post(
            "/api/v1/students",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "first_name": "Invalid",
                "last_name": "Phone",
                "gender": "male",
                "grade_id": grade.id,
                "guardian_name": "Guardian",
                "guardian_phone": "123456",  # Invalid format
            },
        )

        assert response.status_code == 422  # Validation error
