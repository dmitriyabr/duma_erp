from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.config import settings
from src.integrations.mpesa.models import MpesaC2BEvent, MpesaC2BEventStatus
from src.integrations.mpesa.utils import normalize_bill_ref_to_student_number
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.payments.models import CreditAllocation, Payment, PaymentStatus
from src.modules.students.models import Gender, Grade, Student, StudentStatus


@pytest.mark.asyncio
async def test_normalize_bill_ref_to_student_number():
    assert normalize_bill_ref_to_student_number("STU-2026-000123") == "STU-2026-000123"
    assert normalize_bill_ref_to_student_number("26123") == "STU-2026-000123"
    assert normalize_bill_ref_to_student_number("  26-123 ") == "STU-2026-000123"
    assert normalize_bill_ref_to_student_number("") is None
    assert normalize_bill_ref_to_student_number("abc") is None


async def _seed_student_with_invoice(db: AsyncSession) -> dict:
    auth = AuthService(db)
    user = await auth.create_user(
        email="mpesa_system@school.com",
        password="Test123!",
        full_name="M-Pesa System",
        role=UserRole.SUPER_ADMIN,
    )
    await db.flush()

    category = Category(name="M-Pesa Test Category", is_active=True)
    db.add(category)
    await db.flush()

    kit = Kit(
        category_id=category.id,
        sku_code="MPESA-TEST-KIT",
        name="M-Pesa Test Kit",
        item_type=ItemType.SERVICE.value,
        price_type=PriceType.STANDARD.value,
        price=Decimal("5000.00"),
        requires_full_payment=False,
        is_active=True,
    )
    db.add(kit)
    await db.flush()

    grade = Grade(code="MPESA", name="M-Pesa Grade", display_order=1, is_active=True)
    db.add(grade)
    await db.flush()

    student = Student(
        student_number="STU-2026-000123",
        first_name="Test",
        last_name="Student",
        gender=Gender.MALE.value,
        grade_id=grade.id,
        guardian_name="Parent",
        guardian_phone="+254712345678",
        status=StudentStatus.ACTIVE.value,
        created_by_id=user.id,
    )
    db.add(student)
    await db.flush()

    invoice = Invoice(
        invoice_number="INV-MPESA-000001",
        student_id=student.id,
        invoice_type=InvoiceType.ADHOC.value,
        status=InvoiceStatus.ISSUED.value,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        subtotal=Decimal("5000.00"),
        discount_total=Decimal("0.00"),
        total=Decimal("5000.00"),
        paid_total=Decimal("0.00"),
        amount_due=Decimal("5000.00"),
        created_by_id=user.id,
    )
    invoice.lines = []
    db.add(invoice)
    await db.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        kit_id=kit.id,
        description="Test",
        quantity=1,
        unit_price=Decimal("5000.00"),
        line_total=Decimal("5000.00"),
        discount_amount=Decimal("0.00"),
        net_amount=Decimal("5000.00"),
        paid_amount=Decimal("0.00"),
        remaining_amount=Decimal("5000.00"),
    )
    db.add(line)
    invoice.lines.append(line)

    await db.commit()

    return {"user": user, "student": student, "invoice": invoice}


@pytest.mark.asyncio
async def test_mpesa_confirmation_creates_completed_payment_and_allocations(
    client: AsyncClient, db_session: AsyncSession
):
    data = await _seed_student_with_invoice(db_session)

    settings.mpesa_webhook_token = "testtoken"
    settings.mpesa_system_user_id = data["user"].id

    payload = {
        "TransID": "MPESA-TRANS-001",
        "TransTime": "20260227123045",
        "TransAmount": "5000.00",
        "BusinessShortCode": "123456",
        "BillRefNumber": "26123",
        "MSISDN": "+254700000001",
        "FirstName": "John",
        "LastName": "Doe",
    }

    r = await client.post("/api/v1/mpesa/c2b/confirmation/testtoken", json=payload)
    assert r.status_code == 200
    assert r.json()["ResultCode"] == 0

    payment = await db_session.scalar(
        select(Payment).where(Payment.reference == "MPESA-TRANS-001")
    )
    assert payment is not None
    assert payment.status == PaymentStatus.COMPLETED.value

    total_alloc = await db_session.scalar(
        select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
            CreditAllocation.student_id == data["student"].id
        )
    )
    assert Decimal(str(total_alloc)) == Decimal("5000.00")

    updated_student = await db_session.scalar(
        select(Student).where(Student.id == data["student"].id)
    )
    assert updated_student is not None
    assert Decimal(str(updated_student.cached_credit_balance)) == Decimal("0.00")


@pytest.mark.asyncio
async def test_mpesa_confirmation_is_idempotent(client: AsyncClient, db_session: AsyncSession):
    data = await _seed_student_with_invoice(db_session)

    settings.mpesa_webhook_token = "testtoken"
    settings.mpesa_system_user_id = data["user"].id

    payload = {
        "TransID": "MPESA-TRANS-002",
        "TransTime": "20260227123045",
        "TransAmount": "5000.00",
        "BillRefNumber": "26123",
    }

    r1 = await client.post("/api/v1/mpesa/c2b/confirmation/testtoken", json=payload)
    r2 = await client.post("/api/v1/mpesa/c2b/confirmation/testtoken", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200

    payments = list(
        (await db_session.execute(select(Payment).where(Payment.reference == "MPESA-TRANS-002")))
        .scalars()
        .all()
    )
    assert len(payments) == 1

    events = list(
        (await db_session.execute(select(MpesaC2BEvent).where(MpesaC2BEvent.trans_id == "MPESA-TRANS-002")))
        .scalars()
        .all()
    )
    assert len(events) == 1


@pytest.mark.asyncio
async def test_mpesa_unmatched_event_is_saved(client: AsyncClient, db_session: AsyncSession):
    # Create system user so FK received_by_id is valid if later linked.
    auth = AuthService(db_session)
    user = await auth.create_user(
        email="mpesa_system2@school.com",
        password="Test123!",
        full_name="M-Pesa System 2",
        role=UserRole.SUPER_ADMIN,
    )
    await db_session.commit()

    settings.mpesa_webhook_token = "testtoken"
    settings.mpesa_system_user_id = user.id

    payload = {
        "TransID": "MPESA-TRANS-003",
        "TransTime": "20260227123045",
        "TransAmount": "100.00",
        "BillRefNumber": "26999",  # no such student
    }

    r = await client.post("/api/v1/mpesa/c2b/confirmation/testtoken", json=payload)
    assert r.status_code == 200

    event = await db_session.scalar(
        select(MpesaC2BEvent).where(MpesaC2BEvent.trans_id == "MPESA-TRANS-003")
    )
    assert event is not None
    assert event.status == MpesaC2BEventStatus.UNMATCHED.value

    payment = await db_session.scalar(
        select(Payment).where(Payment.reference == "MPESA-TRANS-003")
    )
    assert payment is None

