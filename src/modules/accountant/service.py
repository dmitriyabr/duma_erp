"""Accountant export service: build CSV/Excel for accountant reports."""

from datetime import date
from io import StringIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.payments.models import Payment, PaymentStatus
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


def build_student_payments_csv(
    rows: list[tuple[Payment, str | None, str | None]],
) -> str:
    """Build CSV content for student payments export."""
    import csv
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
