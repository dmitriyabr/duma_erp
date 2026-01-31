"""Service for reports (Admin/SuperAdmin)."""

from datetime import date
from decimal import Decimal
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.invoices.models import Invoice, InvoiceStatus
from src.modules.payments.models import Payment, PaymentStatus
from src.modules.students.models import Student
from src.shared.utils.money import round_money

from src.modules.reports.schemas import (
    AgedReceivablesRow,
    AgedReceivablesSummary,
)


class ReportsService:
    """Build report data for Admin/SuperAdmin."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def aged_receivables(
        self,
        as_at_date: date | None = None,
    ) -> dict:
        """
        Aged Receivables: student debts by aging bucket.

        Current = 0-30 days (not yet due or up to 30 days overdue).
        Then 31-60, 61-90, 90+ days overdue.
        as_at_date: report date (default today). Aging = (as_at_date - invoice.due_date).days.
        """
        as_at = as_at_date or date.today()

        # Load invoices with amount_due > 0, status issued/partially_paid, with student
        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.amount_due > 0,
                Invoice.status.in_(
                    [InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value]
                ),
            )
            .options(selectinload(Invoice.student))
        )
        invoices = list(result.scalars().unique().all())

        # By student: buckets — current (0-30 days), 31-60, 61-90, 90+
        by_student: dict[int, dict] = defaultdict(
            lambda: {
                "student_id": 0,
                "student_name": "",
                "total": Decimal("0"),
                "current": Decimal("0"),
                "bucket_31_60": Decimal("0"),
                "bucket_61_90": Decimal("0"),
                "bucket_90_plus": Decimal("0"),
            }
        )

        for inv in invoices:
            sid = inv.student_id
            if by_student[sid]["student_name"] == "" and inv.student:
                by_student[sid]["student_id"] = sid
                by_student[sid]["student_name"] = inv.student.full_name

            amount = round_money(inv.amount_due)
            due = inv.due_date
            if due is None:
                days = 0  # treat as current
            else:
                days = (as_at - due).days

            by_student[sid]["total"] += amount
            if days <= 30:
                by_student[sid]["current"] += amount
            elif days <= 60:
                by_student[sid]["bucket_31_60"] += amount
            elif days <= 90:
                by_student[sid]["bucket_61_90"] += amount
            else:
                by_student[sid]["bucket_90_plus"] += amount

        # Last payment per student
        last_pay = await self.db.execute(
            select(
                Payment.student_id,
                func.max(Payment.payment_date).label("last_date"),
            )
            .where(Payment.status == PaymentStatus.COMPLETED.value)
            .group_by(Payment.student_id)
        )
        last_payment_by_student = {r[0]: r[1] for r in last_pay.all()}

        summary_total = Decimal("0")
        summary_current = Decimal("0")
        summary_31_60 = Decimal("0")
        summary_61_90 = Decimal("0")
        summary_90_plus = Decimal("0")

        rows = []
        for sid, data in sorted(by_student.items(), key=lambda x: -float(x[1]["total"])):
            if data["total"] <= 0:
                continue
            summary_total += data["total"]
            summary_current += data["current"]
            summary_31_60 += data["bucket_31_60"]
            summary_61_90 += data["bucket_61_90"]
            summary_90_plus += data["bucket_90_plus"]
            rows.append(
                AgedReceivablesRow(
                    student_id=data["student_id"],
                    student_name=data["student_name"],
                    total=round_money(data["total"]),
                    current=round_money(data["current"]),
                    bucket_31_60=round_money(data["bucket_31_60"]),
                    bucket_61_90=round_money(data["bucket_61_90"]),
                    bucket_90_plus=round_money(data["bucket_90_plus"]),
                    last_payment_date=last_payment_by_student.get(sid),
                )
            )

        return {
            "as_at_date": as_at,
            "rows": rows,
            "summary": AgedReceivablesSummary(
                total=round_money(summary_total),
                current=round_money(summary_current),
                bucket_31_60=round_money(summary_31_60),
                bucket_61_90=round_money(summary_61_90),
                bucket_90_plus=round_money(summary_90_plus),
            ),
        }
