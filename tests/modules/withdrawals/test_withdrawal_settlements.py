"""Tests for manual student withdrawal settlements."""

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.billing_accounts.service import BillingAccountService
from src.modules.invoices.models import Invoice, InvoiceAdjustment, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.payments.models import CreditAllocation, PaymentMethod
from src.modules.payments.schemas import PaymentCreate
from src.modules.payments.service import PaymentService
from src.modules.students.models import Gender, Grade, Student, StudentStatus


async def _setup_student_with_invoices(db_session: AsyncSession) -> tuple[str, int, dict]:
    auth_service = AuthService(db_session)
    user = await auth_service.create_user(
        email="withdrawal_admin@school.com",
        password="SuperAdmin123",
        full_name="Withdrawal Admin",
        role=UserRole.SUPER_ADMIN,
    )
    await db_session.flush()

    category = Category(name="Withdrawal Category", is_active=True)
    db_session.add(category)
    await db_session.flush()
    kit = Kit(
        category_id=category.id,
        sku_code="WITHDRAWAL-KIT",
        name="Withdrawal Kit",
        item_type=ItemType.SERVICE.value,
        price_type=PriceType.STANDARD.value,
        price=Decimal("1000.00"),
        requires_full_payment=False,
        is_active=True,
    )
    db_session.add(kit)

    grade = Grade(code="WDR", name="Withdrawal Grade", display_order=1, is_active=True)
    db_session.add(grade)
    await db_session.flush()

    student = Student(
        student_number="STU-WDR-001",
        first_name="Withdrawal",
        last_name="Student",
        gender=Gender.MALE.value,
        grade_id=grade.id,
        guardian_name="Withdrawal Guardian",
        guardian_phone="+254712345678",
        status=StudentStatus.ACTIVE.value,
        created_by_id=user.id,
    )
    db_session.add(student)
    await db_session.flush()
    await BillingAccountService(db_session).ensure_student_billing_account(student.id)
    await db_session.refresh(student)

    invoice_one = _invoice(student, user.id, "INV-WDR-001", Decimal("3000.00"))
    invoice_two = _invoice(student, user.id, "INV-WDR-002", Decimal("5000.00"))
    db_session.add_all([invoice_one, invoice_two])
    await db_session.flush()
    _line(db_session, invoice_one, kit.id, Decimal("3000.00"))
    _line(db_session, invoice_two, kit.id, Decimal("5000.00"))
    await db_session.commit()

    _, token, _ = await auth_service.authenticate("withdrawal_admin@school.com", "SuperAdmin123")
    return token, user.id, {
        "student": student,
        "grade": grade,
        "kit": kit,
        "invoice_one": invoice_one,
        "invoice_two": invoice_two,
    }


def _invoice(student: Student, user_id: int, number: str, total: Decimal) -> Invoice:
    return Invoice(
        invoice_number=number,
        student_id=student.id,
        billing_account_id=student.billing_account_id,
        invoice_type=InvoiceType.ADHOC.value,
        status=InvoiceStatus.ISSUED.value,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        subtotal=total,
        discount_total=Decimal("0.00"),
        total=total,
        paid_total=Decimal("0.00"),
        adjustment_total=Decimal("0.00"),
        amount_due=total,
        created_by_id=user_id,
    )


def _line(db_session: AsyncSession, invoice: Invoice, kit_id: int, amount: Decimal) -> None:
    line = InvoiceLine(
        invoice_id=invoice.id,
        kit_id=kit_id,
        description=f"{invoice.invoice_number} line",
        quantity=1,
        unit_price=amount,
        line_total=amount,
        discount_amount=Decimal("0.00"),
        net_amount=amount,
        paid_amount=Decimal("0.00"),
        adjustment_amount=Decimal("0.00"),
        remaining_amount=amount,
    )
    db_session.add(line)


async def test_withdrawal_settlement_cancels_unpaid_and_writes_off_partial_invoice(
    client: AsyncClient,
    db_session: AsyncSession,
):
    token, user_id, data = await _setup_student_with_invoices(db_session)
    service = PaymentService(db_session)
    payment = await service.create_payment(
        PaymentCreate(
            student_id=data["student"].id,
            preferred_invoice_id=data["invoice_two"].id,
            amount=Decimal("1000.00"),
            payment_method=PaymentMethod.MPESA,
            payment_date=date.today(),
            reference="WDR-PARTIAL",
        ),
        received_by_id=user_id,
    )
    await service.complete_payment(payment.id, user_id)

    response = await client.post(
        f"/api/v1/students/{data['student'].id}/withdrawal-settlements",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settlement_date": str(date.today()),
            "reason": "Parent withdrew before term start",
            "retained_amount": "1000.00",
            "deduction_amount": "0.00",
            "invoice_actions": [
                {
                    "invoice_id": data["invoice_one"].id,
                    "action": "cancel_unpaid",
                    "amount": "3000.00",
                    "notes": "No service delivered",
                },
                {
                    "invoice_id": data["invoice_two"].id,
                    "action": "write_off",
                    "amount": "4000.00",
                    "notes": "Withdrawal write-off",
                },
            ],
        },
    )

    assert response.status_code == 201
    settlement = response.json()["data"]
    assert settlement["settlement_number"].startswith("WDR-")
    assert Decimal(settlement["write_off_amount"]) == Decimal("4000.00")
    assert Decimal(settlement["cancelled_amount"]) == Decimal("3000.00")
    assert Decimal(settlement["remaining_collectible_debt"]) == Decimal("0.00")

    invoice_one = await db_session.get(Invoice, data["invoice_one"].id)
    invoice_two = await db_session.get(Invoice, data["invoice_two"].id)
    student = await db_session.get(Student, data["student"].id)
    assert invoice_one.status == InvoiceStatus.CANCELLED.value
    assert invoice_two.status == InvoiceStatus.PAID.value
    assert invoice_two.amount_due == Decimal("0.00")
    assert invoice_two.adjustment_total == Decimal("4000.00")
    assert student.status == StudentStatus.INACTIVE.value

    adjustments = list((await db_session.execute(select(InvoiceAdjustment))).scalars().all())
    assert len(adjustments) == 1
    assert adjustments[0].adjustment_type == "withdrawal_write_off"


async def test_withdrawal_settlement_can_refund_and_write_off_reopened_invoice(
    client: AsyncClient,
    db_session: AsyncSession,
):
    token, user_id, data = await _setup_student_with_invoices(db_session)
    service = PaymentService(db_session)
    payment = await service.create_payment(
        PaymentCreate(
            student_id=data["student"].id,
            preferred_invoice_id=data["invoice_two"].id,
            amount=Decimal("5000.00"),
            payment_method=PaymentMethod.MPESA,
            payment_date=date.today(),
            reference="WDR-FULL",
        ),
        received_by_id=user_id,
    )
    await service.complete_payment(payment.id, user_id)

    allocation = (
        await db_session.execute(
            select(CreditAllocation).where(CreditAllocation.invoice_id == data["invoice_two"].id)
        )
    ).scalar_one()

    preview_response = await client.post(
        f"/api/v1/students/{data['student'].id}/withdrawal-settlements/preview",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settlement_date": str(date.today()),
            "reason": "Parent withdrew after partial delivery",
            "retained_amount": "3000.00",
            "deduction_amount": "0.00",
            "refund": {
                "amount": "2000.00",
                "refund_date": str(date.today()),
                "refund_method": "bank_transfer",
                "reference_number": "WDR-REFUND",
                "reason": "Withdrawal refund",
                "allocation_reversals": [
                    {"allocation_id": allocation.id, "amount": "2000.00"}
                ],
            },
            "invoice_actions": [
                {
                    "invoice_id": data["invoice_two"].id,
                    "action": "write_off",
                    "amount": "2000.00",
                    "notes": "Write off reopened balance",
                }
            ],
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert Decimal(preview["refund_amount"]) == Decimal("2000.00")
    assert Decimal(preview["remaining_collectible_debt_after"]) == Decimal("3000.00")

    create_response = await client.post(
        f"/api/v1/students/{data['student'].id}/withdrawal-settlements",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settlement_date": str(date.today()),
            "reason": "Parent withdrew after partial delivery",
            "retained_amount": "3000.00",
            "deduction_amount": "0.00",
            "refund": {
                "amount": "2000.00",
                "refund_date": str(date.today()),
                "refund_method": "bank_transfer",
                "reference_number": "WDR-REFUND",
                "reason": "Withdrawal refund",
                "allocation_reversals": [
                    {"allocation_id": allocation.id, "amount": "2000.00"}
                ],
            },
            "invoice_actions": [
                {
                    "invoice_id": data["invoice_one"].id,
                    "action": "cancel_unpaid",
                    "amount": "3000.00",
                    "notes": "No service delivered",
                },
                {
                    "invoice_id": data["invoice_two"].id,
                    "action": "write_off",
                    "amount": "2000.00",
                    "notes": "Write off reopened balance",
                },
            ],
        },
    )
    assert create_response.status_code == 201
    settlement = create_response.json()["data"]
    assert settlement["refund_id"] is not None
    assert Decimal(settlement["refund_amount"]) == Decimal("2000.00")
    assert Decimal(settlement["remaining_collectible_debt"]) == Decimal("0.00")

    invoice_two = await db_session.get(Invoice, data["invoice_two"].id)
    allocation_after = await db_session.get(CreditAllocation, allocation.id)
    assert allocation_after.amount == Decimal("3000.00")
    assert invoice_two.paid_total == Decimal("3000.00")
    assert invoice_two.adjustment_total == Decimal("2000.00")
    assert invoice_two.amount_due == Decimal("0.00")


async def test_billing_account_withdrawal_settlement_deactivates_multiple_students(
    client: AsyncClient,
    db_session: AsyncSession,
):
    token, user_id, data = await _setup_student_with_invoices(db_session)
    first_student = data["student"]
    second_student = Student(
        student_number="STU-WDR-002",
        first_name="Sibling",
        last_name="Student",
        gender=Gender.FEMALE.value,
        grade_id=data["grade"].id,
        guardian_name="Withdrawal Guardian",
        guardian_phone="+254712345678",
        billing_account_id=first_student.billing_account_id,
        status=StudentStatus.ACTIVE.value,
        created_by_id=user_id,
    )
    db_session.add(second_student)
    await db_session.flush()

    sibling_invoice = _invoice(second_student, user_id, "INV-WDR-003", Decimal("2500.00"))
    db_session.add(sibling_invoice)
    await db_session.flush()
    _line(db_session, sibling_invoice, data["kit"].id, Decimal("2500.00"))
    await db_session.commit()

    response = await client.post(
        f"/api/v1/billing-accounts/{first_student.billing_account_id}/withdrawal-settlements",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "student_ids": [first_student.id, second_student.id],
            "settlement_date": str(date.today()),
            "reason": "Family withdrew all children",
            "retained_amount": "0.00",
            "deduction_amount": "0.00",
            "invoice_actions": [
                {
                    "invoice_id": data["invoice_one"].id,
                    "action": "cancel_unpaid",
                    "amount": "3000.00",
                    "notes": "No service delivered",
                },
                {
                    "invoice_id": data["invoice_two"].id,
                    "action": "cancel_unpaid",
                    "amount": "5000.00",
                    "notes": "No service delivered",
                },
                {
                    "invoice_id": sibling_invoice.id,
                    "action": "cancel_unpaid",
                    "amount": "2500.00",
                    "notes": "No service delivered",
                },
            ],
        },
    )

    assert response.status_code == 201
    settlement = response.json()["data"]
    assert settlement["student_id"] is None
    assert {student["student_id"] for student in settlement["students"]} == {
        first_student.id,
        second_student.id,
    }
    assert Decimal(settlement["cancelled_amount"]) == Decimal("10500.00")
    assert Decimal(settlement["remaining_collectible_debt"]) == Decimal("0.00")

    await db_session.refresh(first_student)
    await db_session.refresh(second_student)
    await db_session.refresh(sibling_invoice)
    assert first_student.status == StudentStatus.INACTIVE.value
    assert second_student.status == StudentStatus.INACTIVE.value
    assert sibling_invoice.status == InvoiceStatus.CANCELLED.value

    list_response = await client.get(
        f"/api/v1/billing-accounts/{first_student.billing_account_id}/withdrawal-settlements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1
