"""Service for Students module."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.modules.students.models import Grade, Student, StudentStatus
from src.modules.students.schemas import (
    GradeCreate,
    GradeUpdate,
    StudentCreate,
    StudentUpdate,
)
from src.modules.terms.models import TransportZone


class StudentService:
    """Service for managing students and grades."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # --- Grade Methods ---

    async def create_grade(self, data: GradeCreate, created_by_id: int) -> Grade:
        """Create a new grade."""
        # Check for duplicate code
        existing = await self.db.execute(
            select(Grade).where(Grade.code == data.code)
        )
        if existing.scalar_one_or_none():
            raise DuplicateError("Grade", "code", data.code)

        grade = Grade(
            code=data.code,
            name=data.name,
            display_order=data.display_order,
        )
        self.db.add(grade)
        await self.db.flush()

        await self.audit.log(
            action="grade.create",
            entity_type="Grade",
            entity_id=grade.id,
            user_id=created_by_id,
            new_values={"code": data.code, "name": data.name},
        )

        await self.db.commit()
        await self.db.refresh(grade)
        return grade

    async def get_grade_by_id(self, grade_id: int) -> Grade:
        """Get grade by ID."""
        result = await self.db.execute(select(Grade).where(Grade.id == grade_id))
        grade = result.scalar_one_or_none()
        if not grade:
            raise NotFoundError(f"Grade with id {grade_id} not found")
        return grade

    async def list_grades(self, include_inactive: bool = False) -> list[Grade]:
        """List all grades ordered by display_order."""
        query = select(Grade).order_by(Grade.display_order, Grade.code)
        if not include_inactive:
            query = query.where(Grade.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_grade(
        self, grade_id: int, data: GradeUpdate, updated_by_id: int
    ) -> Grade:
        """Update a grade."""
        grade = await self.get_grade_by_id(grade_id)
        old_values = {
            "code": grade.code,
            "name": grade.name,
            "display_order": grade.display_order,
            "is_active": grade.is_active,
        }
        new_values = {}

        if data.code is not None and data.code != grade.code:
            # Check for duplicate
            existing = await self.db.execute(
                select(Grade).where(Grade.code == data.code, Grade.id != grade_id)
            )
            if existing.scalar_one_or_none():
                raise DuplicateError("Grade", "code", data.code)
            grade.code = data.code
            new_values["code"] = data.code

        if data.name is not None and data.name != grade.name:
            grade.name = data.name
            new_values["name"] = data.name

        if data.display_order is not None and data.display_order != grade.display_order:
            grade.display_order = data.display_order
            new_values["display_order"] = data.display_order

        if data.is_active is not None and data.is_active != grade.is_active:
            grade.is_active = data.is_active
            new_values["is_active"] = data.is_active

        if new_values:
            await self.audit.log(
                action="grade.update",
                entity_type="Grade",
                entity_id=grade_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(grade)
        return grade

    # --- Student Methods ---

    async def _validate_grade(self, grade_id: int) -> Grade:
        """Validate grade exists and is active."""
        grade = await self.get_grade_by_id(grade_id)
        if not grade.is_active:
            raise ValidationError(f"Grade '{grade.name}' is not active")
        return grade

    async def _validate_transport_zone(self, zone_id: int) -> TransportZone:
        """Validate transport zone exists and is active."""
        result = await self.db.execute(
            select(TransportZone).where(TransportZone.id == zone_id)
        )
        zone = result.scalar_one_or_none()
        if not zone:
            raise NotFoundError(f"Transport zone with id {zone_id} not found")
        if not zone.is_active:
            raise ValidationError(f"Transport zone '{zone.zone_name}' is not active")
        return zone

    async def create_student(
        self, data: StudentCreate, created_by_id: int
    ) -> Student:
        """Create a new student."""
        # Validate grade
        await self._validate_grade(data.grade_id)

        # Validate transport zone if provided
        if data.transport_zone_id:
            await self._validate_transport_zone(data.transport_zone_id)

        # Generate student number
        number_gen = DocumentNumberGenerator(self.db)
        student_number = await number_gen.generate("STU")

        student = Student(
            student_number=student_number,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender.value,
            grade_id=data.grade_id,
            transport_zone_id=data.transport_zone_id,
            guardian_name=data.guardian_name,
            guardian_phone=data.guardian_phone,
            guardian_email=data.guardian_email,
            status=StudentStatus.ACTIVE.value,
            enrollment_date=data.enrollment_date,
            notes=data.notes,
            created_by_id=created_by_id,
        )
        self.db.add(student)
        await self.db.flush()

        await self.audit.log(
            action="student.create",
            entity_type="Student",
            entity_id=student.id,
            user_id=created_by_id,
            new_values={
                "student_number": student_number,
                "name": f"{data.first_name} {data.last_name}",
                "grade_id": data.grade_id,
            },
        )

        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def get_student_by_id(
        self, student_id: int, with_relations: bool = False
    ) -> Student:
        """Get student by ID."""
        query = select(Student).where(Student.id == student_id)
        if with_relations:
            query = query.options(
                selectinload(Student.grade),
                selectinload(Student.transport_zone),
            )
        result = await self.db.execute(query)
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    async def get_student_by_number(
        self, student_number: str, with_relations: bool = False
    ) -> Student:
        """Get student by student number."""
        query = select(Student).where(Student.student_number == student_number)
        if with_relations:
            query = query.options(
                selectinload(Student.grade),
                selectinload(Student.transport_zone),
            )
        result = await self.db.execute(query)
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with number '{student_number}' not found")
        return student

    async def list_students(
        self,
        status: StudentStatus | None = None,
        grade_id: int | None = None,
        transport_zone_id: int | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Student], int]:
        """List students with optional filters."""
        query = (
            select(Student)
            .options(
                selectinload(Student.grade),
                selectinload(Student.transport_zone),
            )
            .order_by(Student.last_name, Student.first_name)
        )

        if status is not None:
            query = query.where(Student.status == status.value)
        if grade_id is not None:
            query = query.where(Student.grade_id == grade_id)
        if transport_zone_id is not None:
            query = query.where(Student.transport_zone_id == transport_zone_id)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                    Student.student_number.ilike(search_term),
                    Student.guardian_name.ilike(search_term),
                    Student.guardian_phone.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        students = list(result.scalars().all())

        return students, total

    async def list_active_students(
        self,
        grade_id: int | None = None,
    ) -> list[Student]:
        """List all active students (for invoice generation)."""
        query = (
            select(Student)
            .options(
                selectinload(Student.grade),
                selectinload(Student.transport_zone),
            )
            .where(Student.status == StudentStatus.ACTIVE.value)
            .order_by(Student.grade_id, Student.last_name, Student.first_name)
        )

        if grade_id is not None:
            query = query.where(Student.grade_id == grade_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_student(
        self, student_id: int, data: StudentUpdate, updated_by_id: int
    ) -> Student:
        """Update a student."""
        student = await self.get_student_by_id(student_id)
        old_values = {}
        new_values = {}

        if data.first_name is not None and data.first_name != student.first_name:
            old_values["first_name"] = student.first_name
            student.first_name = data.first_name
            new_values["first_name"] = data.first_name

        if data.last_name is not None and data.last_name != student.last_name:
            old_values["last_name"] = student.last_name
            student.last_name = data.last_name
            new_values["last_name"] = data.last_name

        if data.date_of_birth is not None:
            old_values["date_of_birth"] = str(student.date_of_birth) if student.date_of_birth else None
            student.date_of_birth = data.date_of_birth
            new_values["date_of_birth"] = str(data.date_of_birth)

        if data.gender is not None and data.gender.value != student.gender:
            old_values["gender"] = student.gender
            student.gender = data.gender.value
            new_values["gender"] = data.gender.value

        if data.grade_id is not None and data.grade_id != student.grade_id:
            await self._validate_grade(data.grade_id)
            old_values["grade_id"] = student.grade_id
            student.grade_id = data.grade_id
            new_values["grade_id"] = data.grade_id

        if data.transport_zone_id is not None and data.transport_zone_id != student.transport_zone_id:
            if data.transport_zone_id:
                await self._validate_transport_zone(data.transport_zone_id)
            old_values["transport_zone_id"] = student.transport_zone_id
            student.transport_zone_id = data.transport_zone_id
            new_values["transport_zone_id"] = data.transport_zone_id

        if data.guardian_name is not None and data.guardian_name != student.guardian_name:
            old_values["guardian_name"] = student.guardian_name
            student.guardian_name = data.guardian_name
            new_values["guardian_name"] = data.guardian_name

        if data.guardian_phone is not None and data.guardian_phone != student.guardian_phone:
            old_values["guardian_phone"] = student.guardian_phone
            student.guardian_phone = data.guardian_phone
            new_values["guardian_phone"] = data.guardian_phone

        if data.guardian_email is not None and data.guardian_email != student.guardian_email:
            old_values["guardian_email"] = student.guardian_email
            student.guardian_email = data.guardian_email
            new_values["guardian_email"] = data.guardian_email

        if data.enrollment_date is not None:
            old_values["enrollment_date"] = str(student.enrollment_date) if student.enrollment_date else None
            student.enrollment_date = data.enrollment_date
            new_values["enrollment_date"] = str(data.enrollment_date)

        if data.notes is not None and data.notes != student.notes:
            old_values["notes"] = student.notes
            student.notes = data.notes
            new_values["notes"] = data.notes

        if new_values:
            await self.audit.log(
                action="student.update",
                entity_type="Student",
                entity_id=student_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def activate_student(self, student_id: int, activated_by_id: int) -> Student:
        """Activate a student."""
        student = await self.get_student_by_id(student_id)

        if student.status == StudentStatus.ACTIVE.value:
            raise ValidationError("Student is already active")

        old_status = student.status
        student.status = StudentStatus.ACTIVE.value

        await self.audit.log(
            action="student.activate",
            entity_type="Student",
            entity_id=student_id,
            user_id=activated_by_id,
            old_values={"status": old_status},
            new_values={"status": StudentStatus.ACTIVE.value},
        )

        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def deactivate_student(
        self, student_id: int, deactivated_by_id: int
    ) -> Student:
        """Deactivate a student.

        Inactive students will not receive automatic invoices.
        """
        student = await self.get_student_by_id(student_id)

        if student.status == StudentStatus.INACTIVE.value:
            raise ValidationError("Student is already inactive")

        old_status = student.status
        student.status = StudentStatus.INACTIVE.value

        await self.audit.log(
            action="student.deactivate",
            entity_type="Student",
            entity_id=student_id,
            user_id=deactivated_by_id,
            old_values={"status": old_status},
            new_values={"status": StudentStatus.INACTIVE.value},
        )

        await self.db.commit()
        await self.db.refresh(student)
        return student
