"""Accountant export service: build CSV/Excel for accountant reports."""

import csv
from datetime import date
from io import StringIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.payments.models import Payment, PaymentStatus
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
) -> str:
    """Build CSV content for procurement payments export."""
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
    ])
    for p, po_number in rows:
        supplier = p.payee_name or (p.purchase_order.supplier_name if p.purchase_order else "")
        writer.writerow([
            p.payment_date.isoformat(),
            p.payment_number,
            supplier,
            po_number,
            str(p.amount),
            str(p.amount),
            p.payment_method,
            p.reference_number or "",
        ])
    return out.getvalue()


def build_student_payments_csv(
    rows: list[tuple[Payment, str | None, str | None]],
) -> str:
    """Build CSV content for student payments export."""
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
    ])
    for p, grade_name, received_by_name in rows:
        student_name = p.student.full_name if p.student else ""
        parent_name = p.student.guardian_name if p.student else ""
        admission = p.student.student_number if p.student else ""
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
        ])
    return out.getvalue()
