from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import ValidationError
from src.modules.activities.models import (
    ActivityParticipant,
    ActivityParticipantStatus,
    ActivityStatus,
)
from src.modules.activities.schemas import ActivityCreate, ActivityParticipantAddRequest
from src.modules.activities.service import ActivityService
from src.modules.invoices.models import Invoice, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, Kit
from src.modules.payments.models import PaymentMethod, PaymentStatus
from src.modules.payments.schemas import PaymentCreate
from src.modules.payments.service import PaymentService
from src.modules.students.models import Gender, Grade, Student, StudentStatus


class TestActivityService:
    async def _setup_data(self, db_session: AsyncSession) -> dict:
        auth = AuthService(db_session)
        admin = await auth.create_user(
            email="activities-admin@test.com",
            password="Pass123!",
            full_name="Activities Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()

        grade_one = Grade(code="ACT1", name="Activity Grade 1", display_order=1, is_active=True)
        grade_two = Grade(code="ACT2", name="Activity Grade 2", display_order=2, is_active=True)
        db_session.add_all([grade_one, grade_two])
        await db_session.flush()

        student_one = Student(
            student_number="STU-ACT-000001",
            first_name="Alice",
            last_name="A",
            gender=Gender.FEMALE.value,
            grade_id=grade_one.id,
            guardian_name="Parent A",
            guardian_phone="+254700000011",
            status=StudentStatus.ACTIVE.value,
            created_by_id=admin.id,
        )
        student_two = Student(
            student_number="STU-ACT-000002",
            first_name="Bob",
            last_name="B",
            gender=Gender.MALE.value,
            grade_id=grade_one.id,
            guardian_name="Parent B",
            guardian_phone="+254700000012",
            status=StudentStatus.ACTIVE.value,
            created_by_id=admin.id,
        )
        student_three = Student(
            student_number="STU-ACT-000003",
            first_name="Cara",
            last_name="C",
            gender=Gender.FEMALE.value,
            grade_id=grade_two.id,
            guardian_name="Parent C",
            guardian_phone="+254700000013",
            status=StudentStatus.ACTIVE.value,
            created_by_id=admin.id,
        )
        inactive_student = Student(
            student_number="STU-ACT-000004",
            first_name="Dave",
            last_name="D",
            gender=Gender.MALE.value,
            grade_id=grade_one.id,
            guardian_name="Parent D",
            guardian_phone="+254700000014",
            status=StudentStatus.INACTIVE.value,
            created_by_id=admin.id,
        )
        db_session.add_all([student_one, student_two, student_three, inactive_student])
        await db_session.commit()

        return {
            "admin": admin,
            "grade_one": grade_one,
            "grade_two": grade_two,
            "student_one": student_one,
            "student_two": student_two,
            "student_three": student_three,
            "inactive_student": inactive_student,
        }

    async def test_create_activity_builds_kit_and_participant_snapshot(
        self, db_session: AsyncSession
    ) -> None:
        data = await self._setup_data(db_session)
        service = ActivityService(db_session)

        activity = await service.create_activity(
            ActivityCreate(
                name="Fun Day",
                amount=Decimal("1500.00"),
                activity_date=date(2026, 4, 15),
                due_date=date(2026, 4, 10),
                requires_full_payment=True,
                audience_type="grades",
                grade_ids=[data["grade_one"].id],
            ),
            created_by_id=data["admin"].id,
        )

        assert activity.activity_number.startswith("ACT-")
        assert activity.status == ActivityStatus.DRAFT.value
        assert activity.created_activity_kit_id is not None
        assert {p.student_id for p in activity.participants} == {
            data["student_one"].id,
            data["student_two"].id,
        }

        kit = await db_session.get(Kit, activity.created_activity_kit_id)
        assert kit is not None
        assert kit.name == "Fun Day"
        assert kit.price == Decimal("1500.00")
        assert kit.requires_full_payment is True

        category_result = await db_session.execute(
            select(Category).where(Category.name == "Activities")
        )
        category = category_result.scalar_one()
        assert category.is_active is True

    async def test_generate_activity_invoices_auto_allocates_existing_credit(
        self, db_session: AsyncSession
    ) -> None:
        data = await self._setup_data(db_session)
        payment_service = PaymentService(db_session)
        activity_service = ActivityService(db_session)

        payment = await payment_service.create_payment(
            PaymentCreate(
                student_id=data["student_one"].id,
                amount=Decimal("500.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date(2026, 4, 1),
                reference="ACT500",
            ),
            received_by_id=data["admin"].id,
        )
        assert payment.status == PaymentStatus.PENDING.value
        completed = await payment_service.complete_payment(payment.id, data["admin"].id)
        assert completed.status == PaymentStatus.COMPLETED.value

        activity = await activity_service.create_activity(
            ActivityCreate(
                name="Excursion",
                amount=Decimal("500.00"),
                due_date=date(2026, 4, 5),
                audience_type="manual",
                student_ids=[data["student_one"].id],
            ),
            created_by_id=data["admin"].id,
        )

        result = await activity_service.generate_invoices(activity.id, data["admin"].id)
        assert result.invoices_created == 1
        assert result.affected_student_ids == [data["student_one"].id]

        invoice_result = await db_session.execute(
            select(Invoice).where(
                Invoice.student_id == data["student_one"].id,
                Invoice.invoice_type == InvoiceType.ACTIVITY.value,
            )
        )
        invoice = invoice_result.scalar_one()
        assert invoice.total == Decimal("500.00")
        assert invoice.amount_due == Decimal("0.00")
        assert invoice.status == InvoiceStatus.PAID.value

        refreshed_activity = await activity_service.get_activity_by_id(activity.id)
        participant = refreshed_activity.participants[0]
        assert participant.status == ActivityParticipantStatus.INVOICED.value
        assert participant.invoice_id == invoice.id

    async def test_exclude_participant_cancels_unpaid_invoice_and_blocks_paid_invoice(
        self, db_session: AsyncSession
    ) -> None:
        data = await self._setup_data(db_session)
        service = ActivityService(db_session)

        activity = await service.create_activity(
            ActivityCreate(
                name="Museum Trip",
                amount=Decimal("800.00"),
                audience_type="manual",
                student_ids=[data["student_two"].id],
            ),
            created_by_id=data["admin"].id,
        )
        await service.generate_invoices(activity.id, data["admin"].id)
        reloaded = await service.get_activity_by_id(activity.id)
        participant = reloaded.participants[0]

        updated = await service.exclude_participant(
            reloaded.id,
            participant.id,
            data["admin"].id,
            "Student opted out",
        )
        cancelled_participant = updated.participants[0]
        assert cancelled_participant.status == ActivityParticipantStatus.CANCELLED.value
        assert cancelled_participant.invoice is not None
        assert cancelled_participant.invoice.status == InvoiceStatus.CANCELLED.value

        paid_activity = await service.create_activity(
            ActivityCreate(
                name="Science Fair",
                amount=Decimal("600.00"),
                audience_type="manual",
                student_ids=[data["student_one"].id],
            ),
            created_by_id=data["admin"].id,
        )
        await service.generate_invoices(paid_activity.id, data["admin"].id)

        payment_service = PaymentService(db_session)
        payment = await payment_service.create_payment(
            PaymentCreate(
                student_id=data["student_one"].id,
                amount=Decimal("600.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_date=date(2026, 4, 2),
                reference="BANK600",
            ),
            received_by_id=data["admin"].id,
        )
        await payment_service.complete_payment(payment.id, data["admin"].id)

        paid_reloaded = await service.get_activity_by_id(paid_activity.id)
        paid_participant = paid_reloaded.participants[0]
        with pytest.raises(ValidationError):
            await service.exclude_participant(
                paid_activity.id,
                paid_participant.id,
                data["admin"].id,
                "Too late",
            )

    async def test_add_participant_reactivates_cancelled_row(
        self, db_session: AsyncSession
    ) -> None:
        data = await self._setup_data(db_session)
        service = ActivityService(db_session)

        activity = await service.create_activity(
            ActivityCreate(
                name="Drama Club Trip",
                amount=Decimal("450.00"),
                audience_type="manual",
                student_ids=[data["student_two"].id],
            ),
            created_by_id=data["admin"].id,
        )
        activity = await service.exclude_participant(
            activity.id,
            activity.participants[0].id,
            data["admin"].id,
            "Removed by mistake",
        )

        updated = await service.add_participant(
            activity.id,
            ActivityParticipantAddRequest(student_id=data["student_two"].id),
            data["admin"].id,
        )
        participant = updated.participants[0]
        assert participant.status == ActivityParticipantStatus.PLANNED.value
        assert participant.added_manually is True


class TestActivityEndpoints:
    async def _get_token(self, db_session: AsyncSession, role: UserRole, email: str) -> str:
        auth = AuthService(db_session)
        await auth.create_user(
            email=email,
            password="Pass123!",
            full_name=f"{role.value} User",
            role=role,
        )
        await db_session.commit()
        _, access_token, _ = await auth.authenticate(email, "Pass123!")
        return access_token

    async def _seed_students(self, db_session: AsyncSession) -> dict:
        auth = AuthService(db_session)
        admin = await auth.create_user(
            email="seed-admin@test.com",
            password="Pass123!",
            full_name="Seed Admin",
            role=UserRole.ADMIN,
        )
        await db_session.flush()

        grade = Grade(code="APIA", name="API Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-ACT-API-1",
            first_name="Api",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="API Parent",
            guardian_phone="+254700000020",
            status=StudentStatus.ACTIVE.value,
            created_by_id=admin.id,
        )
        db_session.add(student)
        await db_session.commit()
        return {"admin": admin, "student": student}

    async def test_activity_crud_and_permissions(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        seeded = await self._seed_students(db_session)
        admin_token = await self._get_token(
            db_session, UserRole.ADMIN, "activities-api-admin@test.com"
        )
        accountant_token = await self._get_token(
            db_session, UserRole.ACCOUNTANT, "activities-api-accountant@test.com"
        )

        create_response = await client.post(
            "/api/v1/activities",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "API Activity",
                "amount": "1200.00",
                "audience_type": "manual",
                "student_ids": [seeded["student"].id],
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()["data"]
        assert created["participants_total"] == 1

        list_response = await client.get(
            "/api/v1/activities",
            headers={"Authorization": f"Bearer {accountant_token}"},
        )
        assert list_response.status_code == 200
        assert list_response.json()["data"]["total"] == 1

        forbidden_response = await client.post(
            "/api/v1/activities",
            headers={"Authorization": f"Bearer {accountant_token}"},
            json={
                "name": "Forbidden Activity",
                "amount": "1000.00",
                "audience_type": "manual",
                "student_ids": [seeded["student"].id],
            },
        )
        assert forbidden_response.status_code == 403

        generate_response = await client.post(
            f"/api/v1/activities/{created['id']}/generate-invoices",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert generate_response.status_code == 200
        generation = generate_response.json()["data"]
        assert generation["invoices_created"] == 1

        detail_response = await client.get(
            f"/api/v1/activities/{created['id']}",
            headers={"Authorization": f"Bearer {accountant_token}"},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()["data"]
        assert detail["participants"][0]["invoice_number"] is not None

    async def test_activity_detail_excludes_cancelled_participants_from_current_audience(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        seeded = await self._seed_students(db_session)
        admin_token = await self._get_token(
            db_session, UserRole.ADMIN, "activities-api-audience@test.com"
        )

        create_response = await client.post(
            "/api/v1/activities",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Audience Activity",
                "amount": "900.00",
                "audience_type": "manual",
                "student_ids": [seeded["student"].id],
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()["data"]
        participant_id = created["participants"][0]["id"]

        exclude_response = await client.post(
            f"/api/v1/activities/{created['id']}/participants/{participant_id}/exclude",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Removed"},
        )
        assert exclude_response.status_code == 200

        detail_response = await client.get(
            f"/api/v1/activities/{created['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()["data"]
        assert detail["participants"][0]["status"] == ActivityParticipantStatus.CANCELLED.value
        assert detail["audience_student_ids"] == []
