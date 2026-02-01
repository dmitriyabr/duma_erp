"""Service for dashboard summary (Admin/SuperAdmin main page)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.compensations.models import CompensationPayout, ExpenseClaim, ExpenseClaimStatus
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

        If year is None, uses current date year.
        If term_id is None, uses active term when available.
        """
        today = date.today()
        current_year = year or today.year

        # Resolve term: explicit term_id or active term
        active_term = None
        if term_id:
            r = await self.db.execute(select(Term).where(Term.id == term_id))
            active_term = r.scalar_one_or_none()
        if not active_term:
            r = await self.db.execute(
                select(Term).where(Term.status == TermStatus.ACTIVE.value)
            )
            active_term = r.scalar_one_or_none()

        # --- Revenue (student payments) ---
        # Total revenue this year
        rev_year = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                func.extract("year", Payment.payment_date) == current_year,
            )
        )
        total_revenue_this_year = round_money(Decimal(str(rev_year.scalar() or 0)))

        # This term revenue (if we have active term with dates)
        this_term_revenue = Decimal("0")
        this_term_invoiced = Decimal("0")
        this_term_paid = Decimal("0")
        active_term_id = None
        active_term_display_name = None

        if active_term and active_term.start_date and active_term.end_date:
            active_term_id = active_term.id
            active_term_display_name = active_term.display_name
            rev_term = await self.db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == PaymentStatus.COMPLETED.value,
                    Payment.payment_date >= active_term.start_date,
                    Payment.payment_date <= active_term.end_date,
                )
            )
            this_term_revenue = round_money(Decimal(str(rev_term.scalar() or 0)))

            inv_term = await self.db.execute(
                select(
                    func.coalesce(func.sum(Invoice.total), 0),
                    func.coalesce(func.sum(Invoice.paid_total), 0),
                ).where(
                    Invoice.term_id == active_term.id,
                    Invoice.status.in_(
                        [
                            InvoiceStatus.ISSUED.value,
                            InvoiceStatus.PARTIALLY_PAID.value,
                            InvoiceStatus.PAID.value,
                        ]
                    ),
                )
            )
            row = inv_term.one()
            this_term_invoiced = round_money(Decimal(str(row[0] or 0)))
            this_term_paid = round_money(Decimal(str(row[1] or 0)))

        collection_rate_percent = None
        if this_term_invoiced and this_term_invoiced > 0:
            collection_rate_percent = round(
                float(this_term_paid / this_term_invoiced * 100), 2
            )

        # --- Expenses this year ---
        proc = await self.db.execute(
            select(func.coalesce(func.sum(ProcurementPayment.amount), 0)).where(
                ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
                func.extract("year", ProcurementPayment.payment_date) == current_year,
            )
        )
        procurement_total_this_year = round_money(Decimal(str(proc.scalar() or 0)))

        comp = await self.db.execute(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                func.extract("year", CompensationPayout.payout_date) == current_year,
            )
        )
        employee_compensations_this_year = round_money(Decimal(str(comp.scalar() or 0)))

        total_expenses_this_year = round_money(
            procurement_total_this_year + employee_compensations_this_year
        )

        # --- Active students count ---
        active_students = await self.db.execute(
            select(func.count(Student.id)).where(Student.status == StudentStatus.ACTIVE.value)
        )
        active_students_count = int(active_students.scalar() or 0)

        # --- Student debts ---
        excluded_inv = (InvoiceStatus.PAID.value, InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value)
        debt_agg = await self.db.execute(
            select(
                func.coalesce(func.sum(Invoice.amount_due), 0),
                func.count(func.distinct(Invoice.student_id)),
            ).where(Invoice.status.notin_(excluded_inv))
        )
        debt_row = debt_agg.one()
        student_debts_total = round_money(Decimal(str(debt_row[0] or 0)))
        student_debts_count = int(debt_row[1] or 0)

        # --- Supplier debt ---
        supp = await self.db.execute(
            select(func.coalesce(func.sum(PurchaseOrder.debt_amount), 0)).where(
                PurchaseOrder.status.notin_(
                    [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value]
                )
            )
        )
        supplier_debt = round_money(Decimal(str(supp.scalar() or 0)))

        # --- Credit balances (sum of available balance per student) ---
        # Use cached balances from students table (much faster than SUM queries)
        credit_result = await self.db.execute(
            select(func.coalesce(func.sum(Student.cached_credit_balance), 0))
        )
        credit_balances_total = round_money(Decimal(str(credit_result.scalar() or 0)))

        # --- Pending expense claims ---
        pending_statuses = (
            ExpenseClaimStatus.PENDING_APPROVAL.value,
            ExpenseClaimStatus.APPROVED.value,
        )
        claims_agg = await self.db.execute(
            select(
                func.count(ExpenseClaim.id),
                func.coalesce(func.sum(ExpenseClaim.remaining_amount), 0),
            ).where(
                ExpenseClaim.status.in_(pending_statuses),
                ExpenseClaim.remaining_amount > 0,
            )
        )
        claims_row = claims_agg.one()
        pending_claims_count = int(claims_row[0] or 0)
        pending_claims_amount = round_money(Decimal(str(claims_row[1] or 0)))

        # --- Pending GRN ---
        grn_count = await self.db.execute(
            select(func.count(GoodsReceivedNote.id)).where(
                GoodsReceivedNote.status == GoodsReceivedStatus.DRAFT.value
            )
        )
        pending_grn_count = int(grn_count.scalar() or 0)

        return {
            "active_students_count": active_students_count,
            "total_revenue_this_year": total_revenue_this_year,
            "this_term_revenue": this_term_revenue,
            "this_term_invoiced": this_term_invoiced,
            "collection_rate_percent": collection_rate_percent,
            "total_expenses_this_year": total_expenses_this_year,
            "procurement_total_this_year": procurement_total_this_year,
            "employee_compensations_this_year": employee_compensations_this_year,
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
