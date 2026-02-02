"""Service for dashboard summary (Admin/SuperAdmin main page)."""

import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.compensations.models import (
    CompensationPayout,
    ExpenseClaim,
    ExpenseClaimStatus,
)
from src.modules.invoices.models import Invoice, InvoiceStatus
from src.modules.payments.models import Payment, PaymentStatus
from src.modules.procurement.models import (
    GoodsReceivedNote,
    GoodsReceivedStatus,
    ProcurementPayment,
    ProcurementPaymentStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
)
from src.modules.students.models import Student, StudentStatus
from src.modules.terms.models import Term, TermStatus
from src.shared.utils.money import round_money


class DashboardService:
    """Aggregates data for main page: cards, key metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(
        self,
        *,
        year: int | None = None,
        term_id: int | None = None,
    ) -> dict:
        """
        Build dashboard summary.

        Optimized: Uses parallel queries and date ranges instead of
        func.extract(). Reduced from 12+ queries to 3-4 parallel queries.

        If year is None, uses current date year.
        If term_id is None, uses active term when available.
        """
        today = date.today()
        current_year = year or today.year
        year_start = date(current_year, 1, 1)
        year_end = date(current_year, 12, 31)

        # Resolve term: explicit term_id or active term (single query)
        active_term = None
        if term_id:
            r = await self.db.execute(select(Term).where(Term.id == term_id))
            active_term = r.scalar_one_or_none()
        if not active_term:
            r = await self.db.execute(
                select(Term).where(Term.status == TermStatus.ACTIVE.value)
            )
            active_term = r.scalar_one_or_none()

        active_term_id = None
        active_term_display_name = None
        term_start_date = None
        term_end_date = None

        if active_term:
            active_term_id = active_term.id
            active_term_display_name = active_term.display_name
            term_start_date = active_term.start_date
            term_end_date = active_term.end_date

        # Execute independent queries in parallel using asyncio.gather
        # This reduces total time from sum of all queries to max of parallel
        # queries

        # Query 1: Revenue and expenses for the year (can be combined)
        revenue_year_task = self._get_revenue_year(year_start, year_end)
        expenses_year_task = self._get_expenses_year(year_start, year_end)

        # Query 2: Term-specific revenue and invoices (if term exists)
        if active_term and term_start_date and term_end_date:
            term_metrics_task = self._get_term_metrics(
                active_term_id, term_start_date, term_end_date
            )
        else:
            term_metrics_task = None

        # Query 3: Student metrics (count, debts, credit balances)
        student_metrics_task = self._get_student_metrics()

        # Query 4: Other metrics (supplier debt, claims, GRN)
        other_metrics_task = self._get_other_metrics()

        # Execute all queries in parallel
        tasks = [
            revenue_year_task,
            expenses_year_task,
            student_metrics_task,
            other_metrics_task,
        ]
        if term_metrics_task:
            tasks.append(term_metrics_task)

        results = await asyncio.gather(*tasks)

        # Unpack results
        total_revenue_this_year = results[0]
        expenses_data = results[1]  # (procurement, compensations)
        # (count, debts_total, debts_count, credit_balances)
        student_data = results[2]
        # (supplier_debt, claims_count, claims_amount, grn_count)
        other_data = results[3]

        procurement_total_this_year = expenses_data[0]
        employee_compensations_this_year = expenses_data[1]
        total_expenses_this_year = round_money(
            procurement_total_this_year + employee_compensations_this_year
        )

        active_students_count = student_data[0]
        student_debts_total = student_data[1]
        student_debts_count = student_data[2]
        credit_balances_total = student_data[3]

        supplier_debt = other_data[0]
        pending_claims_count = other_data[1]
        pending_claims_amount = other_data[2]
        pending_grn_count = other_data[3]

        # Term-specific metrics
        this_term_revenue = Decimal("0")
        this_term_invoiced = Decimal("0")
        this_term_paid = Decimal("0")
        collection_rate_percent = None

        if term_metrics_task:
            term_results = results[4]  # (revenue, invoiced, paid)
            this_term_revenue = term_results[0]
            this_term_invoiced = term_results[1]
            this_term_paid = term_results[2]

            if this_term_invoiced and this_term_invoiced > 0:
                collection_rate_percent = round(
                    float(this_term_paid / this_term_invoiced * 100), 2
                )

        return {
            "active_students_count": active_students_count,
            "total_revenue_this_year": total_revenue_this_year,
            "this_term_revenue": this_term_revenue,
            "this_term_invoiced": this_term_invoiced,
            "collection_rate_percent": collection_rate_percent,
            "total_expenses_this_year": total_expenses_this_year,
            "procurement_total_this_year": procurement_total_this_year,
            "employee_compensations_this_year": (
                employee_compensations_this_year
            ),
            "cash_balance": Decimal("0"),  # MVP: not tracked separately
            "student_debts_total": student_debts_total,
            "student_debts_count": student_debts_count,
            "supplier_debt": supplier_debt,
            "credit_balances_total": credit_balances_total,
            "pending_claims_count": pending_claims_count,
            "pending_claims_amount": pending_claims_amount,
            "pending_grn_count": pending_grn_count,
            "active_term_id": active_term_id,
            "active_term_display_name": active_term_display_name,
            "current_year": current_year,
        }

    async def _get_revenue_year(
        self, year_start: date, year_end: date
    ) -> Decimal:
        """Get total revenue for the year (using date range for index)."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date >= year_start,
                Payment.payment_date <= year_end,
            )
        )
        return round_money(Decimal(str(result.scalar() or 0)))

    async def _get_expenses_year(
        self, year_start: date, year_end: date
    ) -> tuple[Decimal, Decimal]:
        """Get procurement and compensation expenses for the year."""
        # Execute both queries in parallel
        proc_task = self.db.execute(
            select(
                func.coalesce(func.sum(ProcurementPayment.amount), 0)
            ).where(
                ProcurementPayment.status
                == ProcurementPaymentStatus.POSTED.value,
                ProcurementPayment.payment_date >= year_start,
                ProcurementPayment.payment_date <= year_end,
            )
        )
        comp_task = self.db.execute(
            select(
                func.coalesce(func.sum(CompensationPayout.amount), 0)
            ).where(
                CompensationPayout.payout_date >= year_start,
                CompensationPayout.payout_date <= year_end,
            )
        )

        proc_result, comp_result = await asyncio.gather(proc_task, comp_task)

        procurement = round_money(Decimal(str(proc_result.scalar() or 0)))
        compensations = round_money(Decimal(str(comp_result.scalar() or 0)))

        return (procurement, compensations)

    async def _get_term_metrics(
        self, term_id: int, term_start: date, term_end: date
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Get term-specific revenue and invoice metrics."""
        # Execute revenue and invoice queries in parallel
        revenue_task = self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date >= term_start,
                Payment.payment_date <= term_end,
            )
        )

        invoice_task = self.db.execute(
            select(
                func.coalesce(func.sum(Invoice.total), 0),
                func.coalesce(func.sum(Invoice.paid_total), 0),
            ).where(
                Invoice.term_id == term_id,
                Invoice.status.in_(
                    [
                        InvoiceStatus.ISSUED.value,
                        InvoiceStatus.PARTIALLY_PAID.value,
                        InvoiceStatus.PAID.value,
                    ]
                ),
            )
        )

        revenue_result, invoice_result = await asyncio.gather(
            revenue_task, invoice_task
        )

        revenue = round_money(Decimal(str(revenue_result.scalar() or 0)))
        invoice_row = invoice_result.one()
        invoiced = round_money(Decimal(str(invoice_row[0] or 0)))
        paid = round_money(Decimal(str(invoice_row[1] or 0)))

        return (revenue, invoiced, paid)

    async def _get_student_metrics(
        self,
    ) -> tuple[int, Decimal, int, Decimal]:
        """Get student-related metrics: count, debts, credit balances."""
        # Execute all student-related queries in parallel
        active_count_task = self.db.execute(
            select(func.count(Student.id)).where(
                Student.status == StudentStatus.ACTIVE.value
            )
        )

        excluded_inv = (
            InvoiceStatus.PAID.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.VOID.value,
        )
        debt_task = self.db.execute(
            select(
                func.coalesce(func.sum(Invoice.amount_due), 0),
                func.count(func.distinct(Invoice.student_id)),
            ).where(Invoice.status.notin_(excluded_inv))
        )

        credit_task = self.db.execute(
            select(func.coalesce(func.sum(Student.cached_credit_balance), 0))
        )

        count_result, debt_result, credit_result = await asyncio.gather(
            active_count_task, debt_task, credit_task
        )

        active_count = int(count_result.scalar() or 0)
        debt_row = debt_result.one()
        debts_total = round_money(Decimal(str(debt_row[0] or 0)))
        debts_count = int(debt_row[1] or 0)
        credit_balances = round_money(
            Decimal(str(credit_result.scalar() or 0))
        )

        return (active_count, debts_total, debts_count, credit_balances)

    async def _get_other_metrics(
        self,
    ) -> tuple[Decimal, int, Decimal, int]:
        """Get other metrics: supplier debt, pending claims, pending GRN."""
        # Execute all other queries in parallel
        supplier_task = self.db.execute(
            select(
                func.coalesce(func.sum(PurchaseOrder.debt_amount), 0)
            ).where(
                PurchaseOrder.status.notin_(
                    [
                        PurchaseOrderStatus.CANCELLED.value,
                        PurchaseOrderStatus.CLOSED.value,
                    ]
                )
            )
        )

        pending_statuses = (
            ExpenseClaimStatus.PENDING_APPROVAL.value,
            ExpenseClaimStatus.APPROVED.value,
        )
        claims_task = self.db.execute(
            select(
                func.count(ExpenseClaim.id),
                func.coalesce(func.sum(ExpenseClaim.remaining_amount), 0),
            ).where(
                ExpenseClaim.status.in_(pending_statuses),
                ExpenseClaim.remaining_amount > 0,
            )
        )

        grn_task = self.db.execute(
            select(func.count(GoodsReceivedNote.id)).where(
                GoodsReceivedNote.status == GoodsReceivedStatus.DRAFT.value
            )
        )

        supplier_result, claims_result, grn_result = await asyncio.gather(
            supplier_task, claims_task, grn_task
        )

        supplier_debt = round_money(
            Decimal(str(supplier_result.scalar() or 0))
        )
        claims_row = claims_result.one()
        claims_count = int(claims_row[0] or 0)
        claims_amount = round_money(Decimal(str(claims_row[1] or 0)))
        grn_count = int(grn_result.scalar() or 0)

        return (supplier_debt, claims_count, claims_amount, grn_count)
