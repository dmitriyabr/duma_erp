from __future__ import annotations

import secrets
from datetime import date

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.school_settings.service import get_school_settings
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.payments.models import PaymentMethod
from src.modules.payments.schemas import PaymentCreate
from src.modules.payments.service import PaymentService
from src.modules.students.models import Student
from src.shared.utils.money import round_money
from src.integrations.mpesa.models import MpesaC2BEvent, MpesaC2BEventStatus
from src.integrations.mpesa.schemas import (
    MpesaC2BConfirmationPayload,
    MpesaC2BValidationPayload,
    parse_trans_time_to_datetime,
)
from src.integrations.mpesa.utils import normalize_bill_ref_to_student_number
from src.modules.payments.models import Payment


class MpesaC2BService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def verify_webhook_token(self, token: str) -> bool:
        configured = (settings.mpesa_webhook_token or "").strip()
        if not configured:
            return False
        return secrets.compare_digest(token or "", configured)

    async def validate_bill_ref(self, payload: MpesaC2BValidationPayload) -> bool:
        student_number = normalize_bill_ref_to_student_number(payload.BillRefNumber or "")
        if not student_number:
            return False
        student = await self.db.scalar(
            select(Student).where(Student.student_number == student_number)
        )
        return student is not None

    async def process_confirmation(self, payload: MpesaC2BConfirmationPayload) -> MpesaC2BEvent:
        """
        Idempotent confirmation processing:
        - persist event (unique trans_id)
        - map BillRefNumber -> Student
        - create + complete Payment
        - auto-allocate credit
        """
        trans_id = payload.TransID.strip()

        student_number = normalize_bill_ref_to_student_number(payload.BillRefNumber or "")

        payer_parts = [payload.FirstName, payload.MiddleName, payload.LastName]
        payer_name = " ".join([p.strip() for p in payer_parts if (p or "").strip()]) or None

        event = MpesaC2BEvent(
            trans_id=trans_id,
            business_short_code=(payload.BusinessShortCode or "").strip() or None,
            bill_ref_number=(payload.BillRefNumber or "").strip() or None,
            derived_student_number=student_number,
            amount=round_money(payload.TransAmount),
            trans_time_raw=(payload.TransTime or "").strip() or None,
            msisdn=(payload.MSISDN or "").strip() or None,
            payer_name=payer_name,
            raw_payload=payload.model_dump(mode="json"),
            status=MpesaC2BEventStatus.RECEIVED.value,
        )

        # Insert event first for idempotency (unique trans_id).
        self.db.add(event)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            existing = await self.db.scalar(
                select(MpesaC2BEvent).where(MpesaC2BEvent.trans_id == trans_id)
            )
            if existing is not None:
                return existing
            raise

        # Optional safety: ignore callbacks for a different Paybill/shortcode.
        school_settings = await get_school_settings(self.db)
        expected_shortcode = (school_settings.mpesa_business_number or "").strip()
        actual_shortcode = (payload.BusinessShortCode or "").strip()
        if expected_shortcode and actual_shortcode and expected_shortcode != actual_shortcode:
            event.status = MpesaC2BEventStatus.IGNORED.value
            event.error_message = f"BusinessShortCode mismatch: {actual_shortcode} != {expected_shortcode}"
            await self.db.commit()
            return event

        # Map to student.
        if not student_number:
            event.status = MpesaC2BEventStatus.UNMATCHED.value
            await self.db.commit()
            return event

        student = await self.db.scalar(
            select(Student).where(Student.student_number == student_number)
        )
        if student is None:
            event.status = MpesaC2BEventStatus.UNMATCHED.value
            await self.db.commit()
            return event

        # Create payment (pending) and complete it (creates receipt, updates cache, auto-allocates).
        service = PaymentService(self.db)

        trans_dt = parse_trans_time_to_datetime(payload.TransTime)
        payment_date = (trans_dt.date() if trans_dt else date.today())

        notes_parts = []
        if payload.MSISDN:
            notes_parts.append(f"MSISDN: {payload.MSISDN}")
        if payer_name:
            notes_parts.append(f"Payer: {payer_name}")
        if payload.BillRefNumber:
            notes_parts.append(f"BillRef: {payload.BillRefNumber}")
        notes = " | ".join(notes_parts) or None

        try:
            payment = await service.create_payment(
                PaymentCreate(
                    student_id=student.id,
                    amount=round_money(payload.TransAmount),
                    payment_method=PaymentMethod.MPESA,
                    payment_date=payment_date,
                    reference=trans_id,
                    notes=notes,
                ),
                received_by_id=settings.mpesa_system_user_id,
            )
            completed = await service.complete_payment(payment.id, settings.mpesa_system_user_id)

            event.payment_id = completed.id
            event.status = MpesaC2BEventStatus.PROCESSED.value
            await self.db.commit()
            return event
        except Exception as exc:  # noqa: BLE001
            await self.db.rollback()
            # Persist error on event (best-effort).
            persisted = await self.db.scalar(
                select(MpesaC2BEvent).where(MpesaC2BEvent.trans_id == trans_id)
            )
            if persisted is not None:
                persisted.status = MpesaC2BEventStatus.ERROR.value
                persisted.error_message = str(exc)[:500]
                await self.db.commit()
                return persisted
            raise

    async def list_unmatched_events(
        self, *, page: int = 1, limit: int = 50
    ) -> tuple[list[MpesaC2BEvent], int]:
        if page < 1:
            page = 1
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100

        base = select(MpesaC2BEvent).where(
            MpesaC2BEvent.status == MpesaC2BEventStatus.UNMATCHED.value
        )
        count_q = select(sa.func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            base.order_by(MpesaC2BEvent.received_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        rows = list((await self.db.execute(q)).scalars().all())
        return rows, int(total)

    async def link_event_to_student(self, *, event_id: int, student_id: int) -> MpesaC2BEvent:
        event = await self.db.scalar(select(MpesaC2BEvent).where(MpesaC2BEvent.id == event_id))
        if event is None:
            raise NotFoundError(f"M-Pesa event {event_id} not found")

        if event.payment_id is not None and event.status == MpesaC2BEventStatus.PROCESSED.value:
            return event

        student = await self.db.scalar(select(Student).where(Student.id == student_id))
        if student is None:
            raise NotFoundError(f"Student {student_id} not found")

        # If a payment already exists for this trans_id (manual entry), link/complete it.
        existing_payment = await self.db.scalar(
            select(Payment).where(
                Payment.payment_method == PaymentMethod.MPESA.value,
                Payment.reference == event.trans_id,
            )
        )
        if existing_payment is not None:
            payment_service = PaymentService(self.db)
            if existing_payment.status != "completed":
                await payment_service.complete_payment(existing_payment.id, settings.mpesa_system_user_id)
            event.payment_id = existing_payment.id
            event.status = MpesaC2BEventStatus.PROCESSED.value
            event.error_message = None
            await self.db.commit()
            return event

        payment_service = PaymentService(self.db)
        trans_dt = parse_trans_time_to_datetime(event.trans_time_raw)
        payment_date = trans_dt.date() if trans_dt else date.today()

        try:
            payment = await payment_service.create_payment(
                PaymentCreate(
                    student_id=student.id,
                    amount=round_money(event.amount),
                    payment_method=PaymentMethod.MPESA,
                    payment_date=payment_date,
                    reference=event.trans_id,
                    notes=f"Linked from unmatched M-Pesa event #{event.id}",
                ),
                received_by_id=settings.mpesa_system_user_id,
            )
            completed = await payment_service.complete_payment(payment.id, settings.mpesa_system_user_id)
        except IntegrityError as exc:
            await self.db.rollback()
            raise ValidationError("Failed to link M-Pesa event: duplicate payment reference") from exc

        event.payment_id = completed.id
        event.status = MpesaC2BEventStatus.PROCESSED.value
        event.error_message = None
        await self.db.commit()
        return event

