"""Accountant export service: build CSV/Excel for accountant reports."""

import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.payments.models import CreditAllocation, Payment, PaymentStatus
from src.modules.procurement.models import ProcurementPayment, ProcurementPaymentStatus
from src.modules.students.models import Student


async def list_student_payments_for_export(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    limit: int = 5000,
) -> list[tuple[Payment, str | None, str | None]]:
    """
    List completed payments in date range with student (grade) and received_by.
    Returns list of (payment, grade_name, received_by_name).
    """
    from src.core.auth.models import User

    q = (
        select(Payment)
        .where(Payment.payment_date >= date_from)
        .where(Payment.payment_date <= date_to)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .options(
            selectinload(Payment.student).selectinload(Student.grade),
            selectinload(Payment.received_by),
        )
        .order_by(Payment.payment_date, Payment.id)
        .limit(limit)
    )
    result = await db.execute(q)
    payments = list(result.scalars().unique().all())
    rows = []
    for p in payments:
        grade_name = p.student.grade.name if p.student and p.student.grade else ""
        received_by_name = p.received_by.full_name if p.received_by else ""
        rows.append((p, grade_name, received_by_name))
    return rows


async def list_procurement_payments_for_export(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    limit: int = 5000,
) -> list[tuple[ProcurementPayment, str]]:
    """
    List posted procurement payments in date range with PO number.
    Returns list of (payment, po_number).
    """
    q = (
        select(ProcurementPayment)
        .where(ProcurementPayment.payment_date >= date_from)
        .where(ProcurementPayment.payment_date <= date_to)
        .where(ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value)
        .options(selectinload(ProcurementPayment.purchase_order))
        .order_by(ProcurementPayment.payment_date, ProcurementPayment.id)
        .limit(limit)
    )
    result = await db.execute(q)
    payments = list(result.scalars().unique().all())
    return [
        (p, p.purchase_order.po_number if p.purchase_order else "")
        for p in payments
    ]


def build_procurement_payments_csv(
    rows: list[tuple[ProcurementPayment, str]],
    app_base_url: str = "",
) -> str:
    """Build CSV content for procurement payments export. app_base_url = frontend URL for attachment links."""
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Payment Date",
        "Payment#",
        "Supplier",
        "PO#",
        "Gross Amount",
        "Net Paid",
        "Payment Method",
        "Reference",
        "Attachment link",
    ])
    for p, po_number in rows:
        supplier = p.payee_name or (p.purchase_order.supplier_name if p.purchase_order else "")
        att_link = f"{app_base_url}/attachment/{p.proof_attachment_id}/download" if app_base_url and p.proof_attachment_id else ""
        writer.writerow([
            p.payment_date.isoformat(),
            p.payment_number,
            supplier,
            po_number,
            str(p.amount),
            str(p.amount),
            p.payment_method,
            p.reference_number or "",
            att_link,
        ])
    return out.getvalue()


def build_student_payments_csv(
    rows: list[tuple[Payment, str | None, str | None]],
    app_base_url: str = "",
) -> str:
    """Build CSV content for student payments export. app_base_url = frontend URL for receipt/attachment links."""
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Receipt Date",
        "Receipt#",
        "Student Name",
        "Admission#",
        "Grade",
        "Parent Name",
        "Payment Method",
        "Amount",
        "Received By",
        "Receipt PDF link",
        "Attachment link",
    ])
    for p, grade_name, received_by_name in rows:
        student_name = p.student.full_name if p.student else ""
        parent_name = p.student.guardian_name if p.student else ""
        admission = p.student.student_number if p.student else ""
        receipt_link = f"{app_base_url}/payment/{p.id}/receipt" if app_base_url else ""
        att_link = f"{app_base_url}/attachment/{p.confirmation_attachment_id}/download" if app_base_url and p.confirmation_attachment_id else ""
        writer.writerow([
            p.payment_date.isoformat(),
            p.receipt_number or p.payment_number,
            student_name,
            admission,
            grade_name or "",
            parent_name,
            p.payment_method,
            str(p.amount),
            received_by_name,
            receipt_link,
            att_link,
        ])
    return out.getvalue()


async def list_student_balance_changes_for_export(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    limit: int = 10000,
) -> list[tuple[datetime, int, str, str, str, Decimal]]:
    """
    List all balance-affecting transactions (payments in, allocations out) in date range.
    Returns list of (datetime, student_id, student_name, type, reference, amount_signed).
    amount_signed: positive for Payment (credit in), negative for Allocation (credit out).
    """
    # Payments (completed) in range
    pay_q = (
        select(Payment)
        .where(Payment.payment_date >= date_from)
        .where(Payment.payment_date <= date_to)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .options(selectinload(Payment.student))
        .order_by(Payment.payment_date, Payment.id)
        .limit(limit)
    )
    pay_result = await db.execute(pay_q)
    payments = list(pay_result.scalars().unique().all())

    # Allocations in range
    alloc_q = (
        select(CreditAllocation)
        .where(func.date(CreditAllocation.created_at) >= date_from)
        .where(func.date(CreditAllocation.created_at) <= date_to)
        .options(
            selectinload(CreditAllocation.student),
            selectinload(CreditAllocation.invoice),
        )
        .order_by(CreditAllocation.created_at)
        .limit(limit)
    )
    alloc_result = await db.execute(alloc_q)
    allocations = list(alloc_result.scalars().unique().all())

    rows: list[tuple[datetime, int, str, str, str, Decimal]] = []
    for p in payments:
        dt = datetime.combine(p.payment_date, datetime.min.time(), tzinfo=timezone.utc)
        student_name = p.student.full_name if p.student else ""
        ref = p.receipt_number or p.payment_number
        rows.append((dt, p.student_id, student_name, "Payment", ref, p.amount))
    for a in allocations:
        student_name = a.student.full_name if a.student else ""
        ref = a.invoice.invoice_number if a.invoice else ""
        rows.append((a.created_at, a.student_id, student_name, "Allocation", ref, -a.amount))

    rows.sort(key=lambda x: x[0])
    return rows[:limit]


def build_student_balance_changes_csv(
    rows: list[tuple[datetime, int, str, str, str, Decimal]],
) -> str:
    """Build CSV content for student balance changes export."""
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Date",
        "Student ID",
        "Student Name",
        "Type",
        "Reference",
        "Amount (+ in / - out)",
    ])
    for dt, student_id, student_name, typ, ref, amount_signed in rows:
        writer.writerow([
            dt.isoformat(),
            student_id,
            student_name,
            typ,
            ref,
            str(amount_signed),
        ])
    return out.getvalue()
