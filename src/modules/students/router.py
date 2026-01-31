"""API endpoints for Students module."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.students.models import StudentStatus
from src.modules.students.schemas import (
    GradeCreate,
    GradeResponse,
    GradeUpdate,
    StudentCreate,
    StudentResponse,
    StudentUpdate,
)
from src.modules.students.service import StudentService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/students", tags=["Students"])


# --- Grade Endpoints ---


@router.post(
    "/grades",
    response_model=ApiResponse[GradeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_grade(
    data: GradeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Create a new grade. Requires SUPER_ADMIN role."""
    service = StudentService(db)
    grade = await service.create_grade(data, current_user.id)
    return ApiResponse(
        success=True,
        message="Grade created successfully",
        data=GradeResponse.model_validate(grade),
    )


@router.get(
    "/grades",
    response_model=ApiResponse[list[GradeResponse]],
)
async def list_grades(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """List all grades."""
    service = StudentService(db)
    grades = await service.list_grades(include_inactive=include_inactive)
    return ApiResponse(
        success=True,
        data=[GradeResponse.model_validate(g) for g in grades],
    )


@router.get(
    "/grades/{grade_id}",
    response_model=ApiResponse[GradeResponse],
)
async def get_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT)
    ),
):
    """Get grade by ID."""
    service = StudentService(db)
    grade = await service.get_grade_by_id(grade_id)
    return ApiResponse(
        success=True,
        data=GradeResponse.model_validate(grade),
    )


@router.patch(
    "/grades/{grade_id}",
    response_model=ApiResponse[GradeResponse],
)
async def update_grade(
    grade_id: int,
    data: GradeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Update a grade. Requires SUPER_ADMIN role."""
    service = StudentService(db)
    grade = await service.update_grade(grade_id, data, current_user.id)
    return ApiResponse(
        success=True,
        message="Grade updated successfully",
        data=GradeResponse.model_validate(grade),
    )


# --- Student Endpoints ---


def _student_to_response(student) -> StudentResponse:
    """Helper to convert Student to response."""
    return StudentResponse(
        id=student.id,
        student_number=student.student_number,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=student.full_name,
        date_of_birth=student.date_of_birth,
        gender=student.gender,
        grade_id=student.grade_id,
        grade_name=student.grade.name if student.grade else None,
        transport_zone_id=student.transport_zone_id,
        transport_zone_name=student.transport_zone.zone_name if student.transport_zone else None,
        guardian_name=student.guardian_name,
        guardian_phone=student.guardian_phone,
        guardian_email=student.guardian_email,
        status=student.status,
        enrollment_date=student.enrollment_date,
        notes=student.notes,
        created_by_id=student.created_by_id,
    )


@router.post(
    "",
    response_model=ApiResponse[StudentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_student(
    data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Create a new student. Requires ADMIN role."""
    service = StudentService(db)
    student = await service.create_student(data, current_user.id)
    student = await service.get_student_by_id(student.id, with_relations=True)
    return ApiResponse(
        success=True,
        message="Student created successfully",
        data=_student_to_response(student),
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[StudentResponse]],
)
async def list_students(
    status: str | None = Query(None, description="Filter by status (active/inactive)"),
    grade_id: int | None = Query(None, description="Filter by grade"),
    transport_zone_id: int | None = Query(None, description="Filter by transport zone"),
    search: str | None = Query(None, description="Search by name, number, guardian"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)
    ),
):
    """List students with optional filters."""
    service = StudentService(db)

    status_filter = StudentStatus(status) if status else None

    students, total = await service.list_students(
        status=status_filter,
        grade_id=grade_id,
        transport_zone_id=transport_zone_id,
        search=search,
        page=page,
        limit=limit,
    )

    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_student_to_response(s) for s in students],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get(
    "/{student_id}",
    response_model=ApiResponse[StudentResponse],
)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER)
    ),
):
    """Get student by ID."""
    service = StudentService(db)
    student = await service.get_student_by_id(student_id, with_relations=True)
    return ApiResponse(
        success=True,
        data=_student_to_response(student),
    )


@router.patch(
    "/{student_id}",
    response_model=ApiResponse[StudentResponse],
)
async def update_student(
    student_id: int,
    data: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Update a student. Requires ADMIN role."""
    service = StudentService(db)
    student = await service.update_student(student_id, data, current_user.id)
    student = await service.get_student_by_id(student.id, with_relations=True)
    return ApiResponse(
        success=True,
        message="Student updated successfully",
        data=_student_to_response(student),
    )


@router.post(
    "/{student_id}/activate",
    response_model=ApiResponse[StudentResponse],
)
async def activate_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Activate a student. Requires ADMIN role."""
    service = StudentService(db)
    student = await service.activate_student(student_id, current_user.id)
    student = await service.get_student_by_id(student.id, with_relations=True)
    return ApiResponse(
        success=True,
        message="Student activated successfully",
        data=_student_to_response(student),
    )


@router.post(
    "/{student_id}/deactivate",
    response_model=ApiResponse[StudentResponse],
)
async def deactivate_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """Deactivate a student. Inactive students won't receive automatic invoices.

    Requires ADMIN role.
    """
    service = StudentService(db)
    student = await service.deactivate_student(student_id, current_user.id)
    student = await service.get_student_by_id(student.id, with_relations=True)
    return ApiResponse(
        success=True,
        message="Student deactivated successfully",
        data=_student_to_response(student),
    )
