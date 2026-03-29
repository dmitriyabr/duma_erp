"""Service layer for paid activities."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.activities.models import (
    Activity,
    ActivityAudienceType,
    ActivityGradeScope,
    ActivityParticipant,
    ActivityParticipantStatus,
    ActivityStatus,
)
from src.modules.activities.schemas import (
    ActivityCreate,
    ActivityInvoiceGenerationResult,
    ActivityListFilters,
    ActivityParticipantAddRequest,
    ActivityUpdate,
)
from src.modules.invoices.models import Invoice, InvoiceStatus, InvoiceType
from src.modules.invoices.schemas import InvoiceLineCreate
from src.modules.invoices.service import InvoiceService
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.payments.schemas import AutoAllocateRequest
from src.modules.payments.service import PaymentService
from src.modules.students.models import Student, StudentStatus
from src.modules.terms.models import Term
from src.shared.utils.money import round_money


class ActivityService:
    """Business logic for paid activities."""

    ACTIVITY_CATEGORY_NAME = "Activities"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def create_activity(self, data: ActivityCreate, created_by_id: int) -> Activity:
        """Create a new paid activity and snapshot its initial audience."""
        await self._validate_code(data.code)
        await self._validate_term(data.term_id)

        number_gen = DocumentNumberGenerator(self.db)
        activity_number = await number_gen.generate("ACT")

        activity = Activity(
            activity_number=activity_number,
            code=data.code,
            name=data.name.strip(),
            description=data.description,
            activity_date=data.activity_date,
            due_date=data.due_date,
            term_id=data.term_id,
            status=data.status.value,
            audience_type=data.audience_type.value,
            amount=round_money(data.amount),
            requires_full_payment=data.requires_full_payment,
            notes=data.notes,
            created_by_id=created_by_id,
        )
        self.db.add(activity)
        with self.db.no_autoflush:
            students = await self._resolve_audience_students(
                data.audience_type,
                data.grade_ids,
                data.student_ids,
            )
        for grade_id in sorted({int(gid) for gid in data.grade_ids}):
            activity.grade_scopes.append(ActivityGradeScope(grade_id=grade_id))
        for student in students:
            activity.participants.append(
                ActivityParticipant(
                    student_id=student.id,
                    status=ActivityParticipantStatus.PLANNED.value,
                    selected_amount=round_money(activity.amount),
                    added_manually=data.audience_type == ActivityAudienceType.MANUAL,
                )
            )

        kit = await self._create_activity_kit(activity)
        activity.created_activity_kit_id = kit.id

        await self.audit.log(
            action="activity.create",
            entity_type="Activity",
            entity_id=activity.id,
            entity_identifier=activity.activity_number,
            user_id=created_by_id,
            new_values={
                "name": activity.name,
                "amount": str(activity.amount),
                "audience_type": activity.audience_type,
                "participants_total": len(activity.participants),
            },
        )

        await self.db.commit()
        return await self.get_activity_by_id(activity.id)

    async def update_activity(
        self,
        activity_id: int,
        data: ActivityUpdate,
        updated_by_id: int,
    ) -> Activity:
        """Update activity metadata and, when still uninvoiced, its audience snapshot."""
        activity = await self.get_activity_by_id(activity_id)
        fields_set = set(data.model_fields_set)

        if "code" in fields_set and data.code != activity.code:
            await self._validate_code(data.code, exclude_activity_id=activity.id)
            activity.code = data.code

        if "term_id" in fields_set:
            await self._validate_term(data.term_id)
            activity.term_id = data.term_id

        audience_fields = {"audience_type", "grade_ids", "student_ids"}
        if fields_set & audience_fields:
            if self._has_generated_invoices(activity):
                raise ValidationError(
                    "Audience cannot be changed after invoices have been generated. "
                    "Use participant actions instead."
                )
            audience_type, grade_ids, student_ids = self._effective_audience_update(
                activity, data
            )
            await self._validate_audience_payload(audience_type, grade_ids, student_ids)
            activity.audience_type = audience_type.value
            await self._replace_grade_scopes(activity, grade_ids)
            students = await self._resolve_audience_students(
                audience_type,
                grade_ids,
                student_ids,
            )
            await self._replace_participants(
                activity,
                students,
                added_manually=audience_type == ActivityAudienceType.MANUAL,
            )

        if "name" in fields_set and data.name is not None:
            activity.name = data.name.strip()
            if activity.created_activity_kit:
                activity.created_activity_kit.name = activity.name
        if "description" in fields_set:
            activity.description = data.description
        if "activity_date" in fields_set:
            activity.activity_date = data.activity_date
        if "due_date" in fields_set:
            activity.due_date = data.due_date
        if "notes" in fields_set:
            activity.notes = data.notes
        if "amount" in fields_set and data.amount is not None:
            activity.amount = round_money(data.amount)
            if activity.created_activity_kit:
                activity.created_activity_kit.price = activity.amount
            for participant in activity.participants:
                if (
                    participant.invoice_id is None
                    and participant.status == ActivityParticipantStatus.PLANNED.value
                ):
                    participant.selected_amount = activity.amount
        if "requires_full_payment" in fields_set and data.requires_full_payment is not None:
            activity.requires_full_payment = data.requires_full_payment
            if activity.created_activity_kit:
                activity.created_activity_kit.requires_full_payment = data.requires_full_payment
        if "status" in fields_set and data.status is not None:
            await self._apply_status_update(activity, data.status, updated_by_id)

        await self.audit.log(
            action="activity.update",
            entity_type="Activity",
            entity_id=activity.id,
            entity_identifier=activity.activity_number,
            user_id=updated_by_id,
            new_values={
                "status": activity.status,
                "amount": str(activity.amount),
                "participants_total": len(activity.participants),
            },
        )

        await self.db.commit()
        return await self.get_activity_by_id(activity.id)

    async def list_activities(
        self,
        filters: ActivityListFilters,
    ) -> tuple[list[Activity], int]:
        """List activities with summary data loaded."""
        query = (
            select(Activity)
            .options(
                selectinload(Activity.term),
                selectinload(Activity.grade_scopes),
                selectinload(Activity.participants)
                .selectinload(ActivityParticipant.student)
                .selectinload(Student.grade),
                selectinload(Activity.participants).selectinload(ActivityParticipant.invoice),
            )
            .order_by(Activity.created_at.desc())
        )

        if filters.status is not None:
            query = query.where(Activity.status == filters.status.value)
        if filters.search and filters.search.strip():
            search_term = f"%{filters.search.strip()}%"
            query = query.where(
                or_(
                    Activity.activity_number.ilike(search_term),
                    Activity.name.ilike(search_term),
                    Activity.code.ilike(search_term),
                    Activity.description.ilike(search_term),
                )
            )

        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
        activities = list((await self.db.execute(query)).scalars().unique().all())
        return activities, total

    async def get_activity_by_id(self, activity_id: int) -> Activity:
        """Load one activity with participants, invoices, grades, and term."""
        result = await self.db.execute(
            select(Activity)
            .where(Activity.id == activity_id)
            .options(
                selectinload(Activity.term),
                selectinload(Activity.created_activity_kit),
                selectinload(Activity.grade_scopes).selectinload(ActivityGradeScope.grade),
                selectinload(Activity.participants)
                .selectinload(ActivityParticipant.student)
                .selectinload(Student.grade),
                selectinload(Activity.participants).selectinload(ActivityParticipant.invoice),
            )
        )
        activity = result.scalar_one_or_none()
        if not activity:
            raise NotFoundError(f"Activity with id {activity_id} not found")

        invoice_ids = [participant.invoice_id for participant in activity.participants if participant.invoice_id]
        if invoice_ids:
            invoices_result = await self.db.execute(
                select(Invoice).where(Invoice.id.in_(invoice_ids))
            )
            invoices_by_id = {invoice.id: invoice for invoice in invoices_result.scalars().all()}
            for participant in activity.participants:
                if participant.invoice_id is not None:
                    participant.invoice = invoices_by_id.get(participant.invoice_id)
        return activity

    async def add_participant(
        self,
        activity_id: int,
        data: ActivityParticipantAddRequest,
        added_by_id: int,
    ) -> Activity:
        """Add one participant to an existing activity."""
        activity = await self.get_activity_by_id(activity_id)
        self._ensure_activity_open_for_billing(activity)

        student = await self._get_student(data.student_id)
        if student.status != StudentStatus.ACTIVE.value:
            raise ValidationError("Only active students can be added to an activity")

        amount = round_money(data.selected_amount or activity.amount)
        existing = next((p for p in activity.participants if p.student_id == student.id), None)
        if existing:
            if existing.invoice_id is not None:
                raise ValidationError("This student already has an activity invoice")
            if existing.status not in (
                ActivityParticipantStatus.CANCELLED.value,
                ActivityParticipantStatus.SKIPPED.value,
            ):
                raise ValidationError("This student is already in the activity audience")
            existing.status = ActivityParticipantStatus.PLANNED.value
            existing.selected_amount = amount
            existing.excluded_reason = None
            existing.added_manually = True
        else:
            self.db.add(
                ActivityParticipant(
                    activity_id=activity.id,
                    student_id=student.id,
                    status=ActivityParticipantStatus.PLANNED.value,
                    selected_amount=amount,
                    added_manually=True,
                )
            )

        await self.audit.log(
            action="activity.add_participant",
            entity_type="Activity",
            entity_id=activity.id,
            entity_identifier=activity.activity_number,
            user_id=added_by_id,
            new_values={"student_id": student.id, "selected_amount": str(amount)},
        )

        await self.db.commit()
        return await self.get_activity_by_id(activity.id)

    async def exclude_participant(
        self,
        activity_id: int,
        participant_id: int,
        excluded_by_id: int,
        reason: str | None = None,
    ) -> Activity:
        """Exclude a student from the activity, cancelling unpaid invoice if needed."""
        activity = await self.get_activity_by_id(activity_id)
        participant = next((p for p in activity.participants if p.id == participant_id), None)
        if not participant:
            raise NotFoundError(f"Activity participant with id {participant_id} not found")

        if participant.invoice is not None:
            invoice = participant.invoice
            if invoice.paid_total > Decimal("0.00"):
                raise ValidationError(
                    "Cannot exclude a participant with a paid activity invoice. Handle reversal manually."
                )
            if invoice.status not in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
                if not invoice.can_be_cancelled:
                    raise ValidationError(
                        f"Cannot cancel linked invoice with status '{invoice.status}'"
                    )
                invoice.status = InvoiceStatus.CANCELLED.value
                await self.audit.log(
                    action="invoice.cancel",
                    entity_type="Invoice",
                    entity_id=invoice.id,
                    entity_identifier=invoice.invoice_number,
                    user_id=excluded_by_id,
                    comment=reason or "Excluded from activity",
                    new_values={"status": InvoiceStatus.CANCELLED.value},
                )

        participant.status = ActivityParticipantStatus.CANCELLED.value
        participant.excluded_reason = reason

        await self.audit.log(
            action="activity.exclude_participant",
            entity_type="ActivityParticipant",
            entity_id=participant.id,
            user_id=excluded_by_id,
            comment=reason,
            new_values={
                "activity_id": activity.id,
                "student_id": participant.student_id,
                "status": participant.status,
            },
        )

        await self.db.commit()
        return await self.get_activity_by_id(activity.id)

    async def generate_invoices(
        self,
        activity_id: int,
        generated_by_id: int,
    ) -> ActivityInvoiceGenerationResult:
        """Create missing activity invoices for planned participants."""
        activity = await self.get_activity_by_id(activity_id)
        self._ensure_activity_open_for_billing(activity)

        if not activity.created_activity_kit_id:
            raise ValidationError("Activity has no billing kit configured")

        invoice_service = InvoiceService(self.db)
        number_gen = DocumentNumberGenerator(self.db)
        payment_service = PaymentService(self.db)

        invoices_created = 0
        participants_skipped = 0
        affected_student_ids: set[int] = set()

        if activity.status == ActivityStatus.DRAFT.value:
            activity.status = ActivityStatus.PUBLISHED.value

        for participant in activity.participants:
            if participant.invoice_id is not None:
                participants_skipped += 1
                continue
            if participant.status != ActivityParticipantStatus.PLANNED.value:
                participants_skipped += 1
                continue

            student = participant.student
            if student.status != StudentStatus.ACTIVE.value:
                participant.status = ActivityParticipantStatus.SKIPPED.value
                participant.excluded_reason = "Student is inactive"
                participants_skipped += 1
                continue

            invoice = Invoice(
                invoice_number=await number_gen.generate("INV"),
                student_id=student.id,
                term_id=activity.term_id,
                invoice_type=InvoiceType.ACTIVITY.value,
                status=InvoiceStatus.ISSUED.value,
                issue_date=date.today(),
                due_date=activity.due_date or (date.today() + timedelta(days=30)),
                notes=activity.activity_number,
                created_by_id=generated_by_id,
            )
            invoice.lines = []
            self.db.add(invoice)
            await self.db.flush()

            line = await invoice_service._add_line_to_invoice(
                invoice,
                InvoiceLineCreate(
                    kit_id=activity.created_activity_kit_id,
                    quantity=1,
                    unit_price_override=participant.selected_amount,
                ),
                student.grade_id,
                student.transport_zone_id,
            )
            invoice_service._recalculate_invoice(invoice)

            participant.invoice_id = invoice.id
            participant.invoice_line_id = line.id
            participant.status = ActivityParticipantStatus.INVOICED.value
            invoices_created += 1
            affected_student_ids.add(student.id)

        await self.audit.log(
            action="activity.generate_invoices",
            entity_type="Activity",
            entity_id=activity.id,
            entity_identifier=activity.activity_number,
            user_id=generated_by_id,
            new_values={
                "invoices_created": invoices_created,
                "participants_skipped": participants_skipped,
            },
        )

        await self.db.commit()

        for student_id in sorted(affected_student_ids):
            await payment_service.allocate_auto(
                AutoAllocateRequest(student_id=student_id),
                generated_by_id,
            )

        return ActivityInvoiceGenerationResult(
            activity_id=activity.id,
            invoices_created=invoices_created,
            participants_skipped=participants_skipped,
            affected_student_ids=sorted(affected_student_ids),
        )

    async def _validate_term(self, term_id: int | None) -> None:
        if term_id is None:
            return
        result = await self.db.execute(select(Term.id).where(Term.id == term_id))
        if result.scalar_one_or_none() is None:
            raise NotFoundError(f"Term with id {term_id} not found")

    async def _validate_code(
        self,
        code: str | None,
        exclude_activity_id: int | None = None,
    ) -> None:
        if not code:
            return
        query = select(Activity.id).where(Activity.code == code)
        if exclude_activity_id is not None:
            query = query.where(Activity.id != exclude_activity_id)
        existing_id = (await self.db.execute(query)).scalar_one_or_none()
        if existing_id is not None:
            raise ValidationError(f"Activity code '{code}' already exists")

    async def _create_activity_kit(self, activity: Activity) -> Kit:
        category = await self._get_or_create_activity_category()
        kit = Kit(
            category_id=category.id,
            sku_code=activity.activity_number,
            name=activity.name,
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=round_money(activity.amount),
            requires_full_payment=activity.requires_full_payment,
            is_active=True,
        )
        self.db.add(kit)
        await self.db.flush()
        return kit

    async def _get_or_create_activity_category(self) -> Category:
        result = await self.db.execute(
            select(Category).where(Category.name == self.ACTIVITY_CATEGORY_NAME)
        )
        category = result.scalar_one_or_none()
        if category:
            if not category.is_active:
                category.is_active = True
            return category

        category = Category(name=self.ACTIVITY_CATEGORY_NAME, is_active=True)
        self.db.add(category)
        await self.db.flush()
        return category

    async def _resolve_audience_students(
        self,
        audience_type: ActivityAudienceType,
        grade_ids: list[int],
        student_ids: list[int],
    ) -> list[Student]:
        query = (
            select(Student)
            .options(selectinload(Student.grade))
            .where(Student.status == StudentStatus.ACTIVE.value)
            .order_by(Student.first_name.asc(), Student.last_name.asc(), Student.id.asc())
        )

        if audience_type == ActivityAudienceType.GRADES:
            unique_grade_ids = sorted({int(gid) for gid in grade_ids})
            await self._validate_grades(unique_grade_ids)
            query = query.where(Student.grade_id.in_(unique_grade_ids))
        elif audience_type == ActivityAudienceType.MANUAL:
            unique_student_ids = sorted({int(sid) for sid in student_ids})
            query = query.where(Student.id.in_(unique_student_ids))

        students = list((await self.db.execute(query)).scalars().unique().all())

        if audience_type == ActivityAudienceType.MANUAL:
            requested_ids = {int(sid) for sid in student_ids}
            found_ids = {student.id for student in students}
            missing_ids = sorted(requested_ids - found_ids)
            if missing_ids:
                raise ValidationError(
                    f"Some students are missing or inactive: {', '.join(str(sid) for sid in missing_ids)}"
                )

        return students

    async def _validate_grades(self, grade_ids: list[int]) -> None:
        if not grade_ids:
            return
        from src.modules.students.models import Grade

        result = await self.db.execute(select(Grade.id).where(Grade.id.in_(grade_ids)))
        found = {row[0] for row in result.all()}
        missing = sorted(set(grade_ids) - found)
        if missing:
            raise ValidationError(
                f"Some grades do not exist: {', '.join(str(grade_id) for grade_id in missing)}"
            )

    async def _replace_grade_scopes(self, activity: Activity, grade_ids: list[int]) -> None:
        activity.grade_scopes = [
            ActivityGradeScope(activity_id=activity.id, grade_id=grade_id)
            for grade_id in sorted({int(gid) for gid in grade_ids})
        ]
        await self.db.flush()

    async def _replace_participants(
        self,
        activity: Activity,
        students: list[Student],
        *,
        added_manually: bool,
    ) -> None:
        activity.participants = [
            ActivityParticipant(
                activity_id=activity.id,
                student_id=student.id,
                status=ActivityParticipantStatus.PLANNED.value,
                selected_amount=round_money(activity.amount),
                added_manually=added_manually,
            )
            for student in students
        ]
        await self.db.flush()

    async def _apply_status_update(
        self,
        activity: Activity,
        status: ActivityStatus,
        updated_by_id: int,
    ) -> None:
        if status == ActivityStatus.CANCELLED:
            if self._has_generated_invoices(activity):
                raise ValidationError(
                    "Cannot cancel an activity after invoices have been generated"
                )
            for participant in activity.participants:
                participant.status = ActivityParticipantStatus.CANCELLED.value
                participant.excluded_reason = "Activity cancelled"
        activity.status = status.value
        await self.audit.log(
            action="activity.status_update",
            entity_type="Activity",
            entity_id=activity.id,
            entity_identifier=activity.activity_number,
            user_id=updated_by_id,
            new_values={"status": activity.status},
        )

    def _effective_audience_update(
        self,
        activity: Activity,
        data: ActivityUpdate,
    ) -> tuple[ActivityAudienceType, list[int], list[int]]:
        audience_type = (
            data.audience_type
            if "audience_type" in data.model_fields_set and data.audience_type is not None
            else ActivityAudienceType(activity.audience_type)
        )
        grade_ids = (
            list(data.grade_ids or [])
            if "grade_ids" in data.model_fields_set
            else [scope.grade_id for scope in activity.grade_scopes]
        )
        student_ids = (
            list(data.student_ids or [])
            if "student_ids" in data.model_fields_set
            else [participant.student_id for participant in activity.participants]
        )
        return audience_type, grade_ids, student_ids

    async def _validate_audience_payload(
        self,
        audience_type: ActivityAudienceType,
        grade_ids: list[int],
        student_ids: list[int],
    ) -> None:
        if audience_type == ActivityAudienceType.ALL_ACTIVE:
            if grade_ids or student_ids:
                raise ValidationError(
                    "all_active activities cannot include grade_ids or student_ids"
                )
            return
        if audience_type == ActivityAudienceType.GRADES:
            if not grade_ids:
                raise ValidationError("grades audience requires at least one grade_id")
            if student_ids:
                raise ValidationError("grades audience cannot include student_ids")
            return
        if audience_type == ActivityAudienceType.MANUAL:
            if not student_ids:
                raise ValidationError("manual audience requires at least one student_id")
            if grade_ids:
                raise ValidationError("manual audience cannot include grade_ids")

    def _has_generated_invoices(self, activity: Activity) -> bool:
        return any(participant.invoice_id is not None for participant in activity.participants)

    def _ensure_activity_open_for_billing(self, activity: Activity) -> None:
        if activity.status in (ActivityStatus.CLOSED.value, ActivityStatus.CANCELLED.value):
            raise ValidationError(
                f"Cannot modify billing for activity with status '{activity.status}'"
            )

    async def _get_student(self, student_id: int) -> Student:
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .options(selectinload(Student.grade))
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student
