"""Public student-number lookup used by payment correction dialogs."""

import pytest

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.main import app
from src.modules.students.models import Grade, Student
from src.shared.utils.student_numbers import format_student_number_short, normalize_student_number


@pytest.fixture
async def lookup_students(db_session):
    user = await AuthService(db_session).create_user(
        email="number-lookup@school.com",
        password="Test123!",
        full_name="Lookup Admin",
        role=UserRole.SUPER_ADMIN,
    )
    grade = Grade(code="LOOKUP", name="Lookup Grade", display_order=1)
    db_session.add(grade)
    await db_session.flush()
    students = []
    for number in ("STU-2026-000040", "STU-2026-002640", "STU-2025-000040", "STU-2026-000004"):
        student = Student(
            student_number=number,
            first_name="Student",
            last_name=number,
            gender="male",
            grade_id=grade.id,
            guardian_name="Guardian 2640",
            guardian_phone="+254712342640",
            created_by_id=user.id,
        )
        db_session.add(student)
        students.append(student)
    await db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield students
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize(
    "number,index", [("2640", 0), ("262640", 1), ("2540", 2), ("264", 3), (" 2640 ", 0)]
)
async def test_exact_invoice_number_is_not_internal_id_or_phone_search(
    client, lookup_students, number, index
):
    response = await client.get("/api/v1/students", params={"admission_number": number, "limit": 1})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["id"] == lookup_students[index].id
    assert data["items"][0]["student_number"] == lookup_students[index].student_number
    assert data["items"][0]["billing_account_id"] is not None


@pytest.mark.parametrize("number", ["40", "0", "", "abc2640", "2640.0", "260", "٢٦٤٠"])
async def test_invalid_number_does_not_resolve_a_different_student(client, lookup_students, number):
    response = await client.get("/api/v1/students", params={"admission_number": number})
    assert response.status_code == 422


async def test_missing_number_returns_no_match(client, lookup_students):
    response = await client.get("/api/v1/students", params={"admission_number": "26999"})
    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


def test_invoice_number_round_trip_uses_same_format_as_mpesa():
    assert format_student_number_short("STU-2026-000040") == "2640"
    assert normalize_student_number("2640") == "STU-2026-000040"
