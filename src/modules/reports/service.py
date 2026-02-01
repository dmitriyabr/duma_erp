"""Service for reports (Admin/SuperAdmin)."""

from datetime import date
from decimal import Decimal
from collections import defaultdict
from calendar import monthrange

from sqlalchemy import case, cast, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.types import Date as SqlDate

from src.core.exceptions import NotFoundError
from src.modules.compensations.models import (
    CompensationPayout,
    ExpenseClaim,
    ExpenseClaimStatus,
    PayoutAllocation,
)
from src.modules.discounts.models import Discount, DiscountReason
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.inventory.models import Issuance, Stock, StockMovement, MovementType
from src.modules.items.models import Category, Item
from src.modules.payments.models import CreditAllocation, Payment, PaymentStatus
from src.modules.procurement.models import (
    GoodsReceivedNote,
    GoodsReceivedLine,
    GoodsReceivedStatus,
    PaymentPurpose,
    ProcurementPayment,
    ProcurementPaymentStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)
from src.modules.students.models import Grade, Student, StudentStatus
from src.modules.terms.models import Term
from src.shared.utils.money import round_money

from src.modules.reports.schemas import (
    AgedReceivablesRow,
    AgedReceivablesSummary,
    StudentFeesRow,
    StudentFeesSummary,
    ProfitLossRevenueLine,
    ProfitLossExpenseLine,
    CashFlowInflowLine,
    CashFlowOutflowLine,
    BalanceSheetAssetLine,
    BalanceSheetLiabilityLine,
    CollectionRateMonthRow,
    DiscountAnalysisRow,
    DiscountAnalysisSummary,
    TopDebtorRow,
    ProcurementSummaryRow,
    ProcurementSummaryOutstanding,
    InventoryValuationRow,
    LowStockAlertRow,
    StockMovementRow,
    CompensationSummaryRow,
    CompensationSummaryTotals,
    ExpenseClaimsByCategoryRow,
    RevenueTrendRow,
    PaymentMethodDistributionRow,
    TermComparisonMetric,
)


def _months_in_range(date_from: date, date_to: date) -> list[str]:
    """Return list of YYYY-MM for each month in [date_from, date_to]."""
    out: list[str] = []
    y, m = date_from.year, date_from.month
    end_y, end_m = date_to.year, date_to.month
    while (y, m) <= (end_y, end_m):
        out.append(f"{y:04d}-{m:02d}")
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


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

    async def student_fees_summary(
        self,
        term_id: int,
        grade_id: int | None = None,
    ) -> dict:
        """
        Student Fees Summary by Term: per-grade aggregates (students count, total invoiced, paid, balance, rate).

        term_id: required. grade_id: optional filter (only that grade).
        Only invoices with status issued, partially_paid, paid are included.
        """
        term_result = await self.db.execute(select(Term).where(Term.id == term_id))
        term = term_result.scalar_one_or_none()
        if not term:
            raise NotFoundError("Term", term_id)

        statuses = (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
            InvoiceStatus.PAID.value,
        )
        q = (
            select(
                Student.grade_id,
                Grade.name.label("grade_name"),
                func.count(func.distinct(Invoice.student_id)).label("students_count"),
                func.coalesce(func.sum(Invoice.total), 0).label("total_invoiced"),
                func.coalesce(func.sum(Invoice.paid_total), 0).label("total_paid"),
                func.coalesce(func.sum(Invoice.amount_due), 0).label("balance"),
            )
            .select_from(Invoice)
            .join(Student, Invoice.student_id == Student.id)
            .join(Grade, Student.grade_id == Grade.id)
            .where(
                Invoice.term_id == term_id,
                Invoice.status.in_(statuses),
            )
            .group_by(Student.grade_id, Grade.name, Grade.display_order)
            .order_by(Grade.display_order, Grade.name)
        )
        if grade_id is not None:
            q = q.where(Student.grade_id == grade_id)
        result = await self.db.execute(q)
        raw_rows = result.all()

        rows = []
        summary_students = 0
        summary_invoiced = Decimal("0")
        summary_paid = Decimal("0")
        summary_balance = Decimal("0")
        for r in raw_rows:
            gid, gname, cnt, inv, paid, bal = r
            inv = round_money(Decimal(str(inv)))
            paid = round_money(Decimal(str(paid)))
            bal = round_money(Decimal(str(bal)))
            rate = round(float(paid / inv * 100), 2) if inv and inv > 0 else None
            summary_students += int(cnt)
            summary_invoiced += inv
            summary_paid += paid
            summary_balance += bal
            rows.append(
                StudentFeesRow(
                    grade_id=int(gid),
                    grade_name=str(gname),
                    students_count=int(cnt),
                    total_invoiced=inv,
                    total_paid=paid,
                    balance=bal,
                    rate_percent=rate,
                )
            )
        summary_rate = (
            round(float(summary_paid / summary_invoiced * 100), 2)
            if summary_invoiced and summary_invoiced > 0
            else None
        )
        return {
            "term_id": term_id,
            "term_display_name": term.display_name,
            "grade_id": grade_id,
            "rows": rows,
            "summary": StudentFeesSummary(
                students_count=summary_students,
                total_invoiced=round_money(summary_invoiced),
                total_paid=round_money(summary_paid),
                balance=round_money(summary_balance),
                rate_percent=summary_rate,
            ),
        }

    async def _profit_loss_period(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Compute PnL for a single period; returns raw numbers for aggregation."""
        statuses = (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
            InvoiceStatus.PAID.value,
        )
        rev_q = (
            select(
                Invoice.invoice_type,
                func.coalesce(func.sum(Invoice.total), 0).label("total"),
                func.coalesce(func.sum(Invoice.discount_total), 0).label("discounts"),
            )
            .where(
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.status.in_(statuses),
            )
            .group_by(Invoice.invoice_type)
        )
        rev_result = await self.db.execute(rev_q)
        rev_rows = rev_result.all()
        type_labels = {
            "school_fee": "School Fee",
            "transport": "Transport",
            "adhoc": "Other Fees",
        }
        revenue_lines: list[dict] = []
        gross_revenue = Decimal("0")
        total_discounts = Decimal("0")
        for inv_type, tot, disc in rev_rows:
            tot = round_money(Decimal(str(tot)))
            disc = round_money(Decimal(str(disc)))
            gross_revenue += tot
            total_discounts += disc
            revenue_lines.append({"label": type_labels.get(inv_type, inv_type or "Other"), "amount": tot})
        net_revenue = round_money(gross_revenue - total_discounts)
        proc = await self.db.execute(
            select(func.coalesce(func.sum(ProcurementPayment.amount), 0)).where(
                ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
                ProcurementPayment.payment_date >= date_from,
                ProcurementPayment.payment_date <= date_to,
            )
        )
        proc_total = round_money(Decimal(str(proc.scalar() or 0)))
        comp = await self.db.execute(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.payout_date >= date_from,
                CompensationPayout.payout_date <= date_to,
            )
        )
        comp_total = round_money(Decimal(str(comp.scalar() or 0)))
        total_expenses = round_money(proc_total + comp_total)
        net_profit = round_money(net_revenue - total_expenses)
        return {
            "revenue_lines": revenue_lines,
            "gross_revenue": gross_revenue,
            "total_discounts": total_discounts,
            "net_revenue": net_revenue,
            "proc_total": proc_total,
            "comp_total": comp_total,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
        }

    async def profit_loss(
        self,
        date_from: date,
        date_to: date,
        breakdown_monthly: bool = False,
    ) -> dict:
        """
        Profit & Loss: revenue (invoiced by type), less discounts, expenses (procurement + compensations).

        Only invoices with issue_date in [date_from, date_to] and status issued/partially_paid/paid.
        If breakdown_monthly=True, adds months list and monthly amounts per line and per total.
        """
        full = await self._profit_loss_period(date_from, date_to)
        type_labels = {"school_fee": "School Fee", "transport": "Transport", "adhoc": "Other Fees"}
        revenue_lines = [
            ProfitLossRevenueLine(label=r["label"], amount=r["amount"])
            for r in full["revenue_lines"]
        ]
        expense_lines = [
            ProfitLossExpenseLine(label="Procurement (Inventory)", amount=full["proc_total"]),
            ProfitLossExpenseLine(label="Employee Compensations", amount=full["comp_total"]),
        ]
        profit_margin_percent = (
            round(float(full["net_profit"] / full["net_revenue"] * 100), 2)
            if full["net_revenue"] and full["net_revenue"] > 0
            else None
        )
        out: dict = {
            "date_from": date_from,
            "date_to": date_to,
            "revenue_lines": revenue_lines,
            "gross_revenue": full["gross_revenue"],
            "total_discounts": full["total_discounts"],
            "net_revenue": full["net_revenue"],
            "expense_lines": expense_lines,
            "total_expenses": full["total_expenses"],
            "net_profit": full["net_profit"],
            "profit_margin_percent": profit_margin_percent,
        }
        if not breakdown_monthly:
            return out
        months = _months_in_range(date_from, date_to)
        rev_by_label: dict[str, dict[str, Decimal]] = defaultdict(lambda: {})
        gross_monthly: dict[str, Decimal] = {}
        discounts_monthly: dict[str, Decimal] = {}
        net_rev_monthly: dict[str, Decimal] = {}
        proc_monthly: dict[str, Decimal] = {}
        comp_monthly: dict[str, Decimal] = {}
        total_exp_monthly: dict[str, Decimal] = {}
        net_profit_monthly: dict[str, Decimal] = {}
        profit_margin_monthly: dict[str, float] = {}
        for mo in months:
            y, m = int(mo[:4]), int(mo[5:7])
            first = date(y, m, 1)
            last = date(y, m, monthrange(y, m)[1])
            period = await self._profit_loss_period(first, last)
            gross_monthly[mo] = period["gross_revenue"]
            discounts_monthly[mo] = period["total_discounts"]
            net_rev_monthly[mo] = period["net_revenue"]
            proc_monthly[mo] = period["proc_total"]
            comp_monthly[mo] = period["comp_total"]
            total_exp_monthly[mo] = period["total_expenses"]
            net_profit_monthly[mo] = period["net_profit"]
            if period["net_revenue"] and period["net_revenue"] > 0:
                profit_margin_monthly[mo] = round(
                    float(period["net_profit"] / period["net_revenue"] * 100), 2
                )
            for r in period["revenue_lines"]:
                rev_by_label[r["label"]][mo] = r["amount"]
        for line in revenue_lines:
            line.monthly = dict(rev_by_label.get(line.label, {}))
        expense_lines[0].monthly = dict(proc_monthly)
        expense_lines[1].monthly = dict(comp_monthly)
        out["months"] = months
        out["gross_revenue_monthly"] = gross_monthly
        out["total_discounts_monthly"] = discounts_monthly
        out["net_revenue_monthly"] = net_rev_monthly
        out["total_expenses_monthly"] = total_exp_monthly
        out["net_profit_monthly"] = net_profit_monthly
        out["profit_margin_percent_monthly"] = profit_margin_monthly
        return out

    async def _cash_flow_period(
        self,
        date_from: date,
        date_to: date,
        payment_method: str | None,
    ) -> dict:
        """Inflows and outflows for a single period (no opening/closing)."""
        q_in = (
            select(
                Payment.payment_method,
                func.coalesce(func.sum(Payment.amount), 0).label("amt"),
            )
            .where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to,
            )
            .group_by(Payment.payment_method)
        )
        if payment_method:
            q_in = q_in.where(Payment.payment_method == payment_method)
        inflow_res = await self.db.execute(q_in)
        method_labels = {"mpesa": "M-Pesa", "bank_transfer": "Bank Transfer"}
        inflow_rows = [(m, round_money(Decimal(str(a)))) for m, a in inflow_res.all()]
        total_inflows = round_money(sum(a for _, a in inflow_rows))
        proc_out = await self.db.execute(
            select(func.coalesce(func.sum(ProcurementPayment.amount), 0)).where(
                ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
                ProcurementPayment.payment_date >= date_from,
                ProcurementPayment.payment_date <= date_to,
            )
        )
        comp_out = await self.db.execute(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.payout_date >= date_from,
                CompensationPayout.payout_date <= date_to,
            )
        )
        proc_amt = round_money(Decimal(str(proc_out.scalar() or 0)))
        comp_amt = round_money(Decimal(str(comp_out.scalar() or 0)))
        total_outflows = round_money(proc_amt + comp_amt)
        return {
            "inflow_rows": inflow_rows,
            "method_labels": method_labels,
            "total_inflows": total_inflows,
            "proc_amt": proc_amt,
            "comp_amt": comp_amt,
            "total_outflows": total_outflows,
        }

    async def cash_flow(
        self,
        date_from: date,
        date_to: date,
        payment_method: str | None = None,
        breakdown_monthly: bool = False,
    ) -> dict:
        """
        Cash flow: opening balance (net cash position before date_from), inflows (student payments),
        outflows (procurement + compensations), closing balance.

        payment_method: optional filter for student payments (mpesa, bank_transfer, or None for all).
        If breakdown_monthly=True, adds months list and monthly amounts per line and closing_balance_monthly.
        """
        pay_in = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date < date_from,
            )
        )
        pay_in_val = Decimal(str(pay_in.scalar() or 0))
        proc_before = await self.db.execute(
            select(func.coalesce(func.sum(ProcurementPayment.amount), 0)).where(
                ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
                ProcurementPayment.payment_date < date_from,
            )
        )
        comp_before = await self.db.execute(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.payout_date < date_from,
            )
        )
        opening_balance = round_money(
            pay_in_val - Decimal(str(proc_before.scalar() or 0)) - Decimal(str(comp_before.scalar() or 0))
        )
        full = await self._cash_flow_period(date_from, date_to, payment_method)
        method_labels = full["method_labels"]
        inflow_lines = [
            CashFlowInflowLine(
                label=method_labels.get(m, m or "Other"),
                amount=round_money(Decimal(str(a))),
            )
            for m, a in full["inflow_rows"]
        ]
        total_inflows = full["total_inflows"]
        outflow_lines = [
            CashFlowOutflowLine(label="Supplier Payments", amount=full["proc_amt"]),
            CashFlowOutflowLine(label="Employee Compensations", amount=full["comp_amt"]),
        ]
        total_outflows = full["total_outflows"]
        net_cash_flow = round_money(total_inflows - total_outflows)
        closing_balance = round_money(opening_balance + net_cash_flow)
        out: dict = {
            "date_from": date_from,
            "date_to": date_to,
            "opening_balance": opening_balance,
            "inflow_lines": inflow_lines,
            "total_inflows": total_inflows,
            "outflow_lines": outflow_lines,
            "total_outflows": total_outflows,
            "net_cash_flow": net_cash_flow,
            "closing_balance": closing_balance,
        }
        if not breakdown_monthly:
            return out
        months = _months_in_range(date_from, date_to)
        inflow_by_label: dict[str, dict[str, Decimal]] = defaultdict(lambda: {})
        total_inflows_monthly: dict[str, Decimal] = {}
        proc_monthly: dict[str, Decimal] = {}
        comp_monthly: dict[str, Decimal] = {}
        total_outflows_monthly: dict[str, Decimal] = {}
        closing_balance_monthly: dict[str, Decimal] = {}
        cum = opening_balance
        for mo in months:
            y, m = int(mo[:4]), int(mo[5:7])
            first = date(y, m, 1)
            last = date(y, m, monthrange(y, m)[1])
            period = await self._cash_flow_period(first, last, payment_method)
            total_inflows_monthly[mo] = period["total_inflows"]
            proc_monthly[mo] = period["proc_amt"]
            comp_monthly[mo] = period["comp_amt"]
            total_outflows_monthly[mo] = period["total_outflows"]
            for method_key, amt in period["inflow_rows"]:
                lbl = method_labels.get(method_key, method_key or "Other")
                inflow_by_label[lbl][mo] = amt
            cum = round_money(cum + period["total_inflows"] - period["total_outflows"])
            closing_balance_monthly[mo] = cum
        for line in inflow_lines:
            line.monthly = dict(inflow_by_label.get(line.label, {}))
        outflow_lines[0].monthly = dict(proc_monthly)
        outflow_lines[1].monthly = dict(comp_monthly)
        out["months"] = months
        out["total_inflows_monthly"] = total_inflows_monthly
        out["total_outflows_monthly"] = total_outflows_monthly
        out["closing_balance_monthly"] = closing_balance_monthly
        return out

    async def _balance_sheet_as_at(self, as_at_date: date) -> dict:
        """Compute balance sheet as at a single date; returns raw dict (no monthly)."""
        pay = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date <= as_at_date,
            )
        )
        proc = await self.db.execute(
            select(func.coalesce(func.sum(ProcurementPayment.amount), 0)).where(
                ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
                ProcurementPayment.payment_date <= as_at_date,
            )
        )
        comp = await self.db.execute(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.payout_date <= as_at_date,
            )
        )
        cash = round_money(
            Decimal(str(pay.scalar() or 0))
            - Decimal(str(proc.scalar() or 0))
            - Decimal(str(comp.scalar() or 0))
        )
        # Receivables as at date: invoices issued by as_at_date; amount due = total - allocations created by as_at_date.
        # Do not filter by PAID: historically the invoice may have been unpaid as at that date; we use allocation history.
        excluded = (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value)
        alloc_subq = (
            select(
                CreditAllocation.invoice_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0).label("allocated"),
            )
            .where(cast(CreditAllocation.created_at, SqlDate) <= as_at_date)
            .group_by(CreditAllocation.invoice_id)
        ).subquery()
        due_expr = Invoice.total - func.coalesce(alloc_subq.c.allocated, 0)
        recv_q = (
            select(
                func.coalesce(
                    func.sum(case((due_expr < 0, Decimal("0")), else_=due_expr)),
                    0,
                )
            )
            .select_from(Invoice)
            .outerjoin(alloc_subq, Invoice.id == alloc_subq.c.invoice_id)
            .where(Invoice.issue_date <= as_at_date)
            .where(Invoice.status.notin_(excluded))
        )
        recv = await self.db.execute(recv_q)
        receivables = round_money(Decimal(str(recv.scalar() or 0)))
        # Inventory at Cost as at date: from latest StockMovement per stock where movement date <= as_at_date.
        latest_mov = (
            select(
                StockMovement.stock_id,
                func.max(StockMovement.created_at).label("max_created"),
            )
            .where(cast(StockMovement.created_at, SqlDate) <= as_at_date)
            .group_by(StockMovement.stock_id)
        ).subquery()
        inv_q = (
            select(
                func.coalesce(
                    func.sum(
                        StockMovement.quantity_after * StockMovement.average_cost_after
                    ),
                    0,
                )
            )
            .select_from(StockMovement)
            .join(
                latest_mov,
                (StockMovement.stock_id == latest_mov.c.stock_id)
                & (StockMovement.created_at == latest_mov.c.max_created),
            )
        )
        inv_res = await self.db.execute(inv_q)
        inventory = round_money(Decimal(str(inv_res.scalar() or 0)))
        total_assets = round_money(cash + receivables + inventory)
        # Accounts Payable (Supplier Debts) as at date: received value (from GRNs approved by date) minus payments by date, per PO.
        grn_value_q = (
            select(
                GoodsReceivedNote.po_id,
                func.coalesce(
                    func.sum(GoodsReceivedLine.quantity_received * PurchaseOrderLine.unit_price),
                    0,
                ).label("received"),
            )
            .select_from(GoodsReceivedNote)
            .join(GoodsReceivedLine, GoodsReceivedLine.grn_id == GoodsReceivedNote.id)
            .join(PurchaseOrderLine, PurchaseOrderLine.id == GoodsReceivedLine.po_line_id)
            .where(GoodsReceivedNote.status == GoodsReceivedStatus.APPROVED.value)
            .where(cast(GoodsReceivedNote.approved_at, SqlDate) <= as_at_date)
            .group_by(GoodsReceivedNote.po_id)
        )
        grn_rows = (await self.db.execute(grn_value_q)).all()
        received_by_po: dict[int, Decimal] = {r[0]: round_money(Decimal(str(r[1] or 0))) for r in grn_rows}
        pay_supp_q = (
            select(
                ProcurementPayment.po_id,
                func.coalesce(func.sum(ProcurementPayment.amount), 0).label("paid"),
            )
            .where(ProcurementPayment.po_id.isnot(None))
            .where(ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value)
            .where(ProcurementPayment.payment_date <= as_at_date)
            .group_by(ProcurementPayment.po_id)
        )
        pay_supp_rows = (await self.db.execute(pay_supp_q)).all()
        paid_by_po: dict[int, Decimal] = {r[0]: round_money(Decimal(str(r[1] or 0))) for r in pay_supp_rows}
        all_po_ids = set(received_by_po) | set(paid_by_po)
        supplier_debt = round_money(
            sum(
                max(Decimal("0"), received_by_po.get(pid, Decimal("0")) - paid_by_po.get(pid, Decimal("0")))
                for pid in all_po_ids
            )
        )
        pay_tot = await self.db.execute(
            select(
                Payment.student_id,
                func.coalesce(func.sum(Payment.amount), 0).label("s"),
            )
            .where(Payment.status == PaymentStatus.COMPLETED.value)
            .where(Payment.payment_date <= as_at_date)
            .group_by(Payment.student_id)
        )
        payments_by_student = {r[0]: Decimal(str(r[1])) for r in pay_tot.all()}
        alloc_tot = await self.db.execute(
            select(
                CreditAllocation.student_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0).label("s"),
            )
            .where(cast(CreditAllocation.created_at, SqlDate) <= as_at_date)
            .group_by(CreditAllocation.student_id)
        )
        allocated_by_student = {r[0]: Decimal(str(r[1])) for r in alloc_tot.all()}
        credit_total = Decimal("0")
        for sid in set(payments_by_student) | set(allocated_by_student):
            credit_total += round_money(
                payments_by_student.get(sid, Decimal("0")) - allocated_by_student.get(sid, Decimal("0"))
            )
        credit_balances = round_money(credit_total)
        # Employee Payable (Pending Claims) as at date: for claims created by date and not draft/rejected,
        # remaining as at date = amount - sum(allocated_amount from payouts with payout_date <= as_at_date).
        excluded_claim_statuses = (
            ExpenseClaimStatus.DRAFT.value,
            ExpenseClaimStatus.REJECTED.value,
        )
        payout_tot = (
            select(
                PayoutAllocation.claim_id,
                func.coalesce(func.sum(PayoutAllocation.allocated_amount), 0).label("paid"),
            )
            .select_from(PayoutAllocation)
            .join(CompensationPayout, CompensationPayout.id == PayoutAllocation.payout_id)
            .where(CompensationPayout.payout_date <= as_at_date)
            .group_by(PayoutAllocation.claim_id)
        ).subquery()
        claims_q = (
            select(
                ExpenseClaim.id,
                ExpenseClaim.amount,
                func.coalesce(payout_tot.c.paid, 0).label("paid_by_date"),
            )
            .select_from(ExpenseClaim)
            .outerjoin(payout_tot, ExpenseClaim.id == payout_tot.c.claim_id)
            .where(cast(ExpenseClaim.created_at, SqlDate) <= as_at_date)
            .where(ExpenseClaim.status.notin_(excluded_claim_statuses))
        )
        claims_rows = (await self.db.execute(claims_q)).all()
        pending_claims = round_money(
            sum(
                max(
                    Decimal("0"),
                    Decimal(str(r[1] or 0)) - Decimal(str(r[2] or 0)),
                )
                for r in claims_rows
            )
        )
        total_liabilities = round_money(supplier_debt + credit_balances + pending_claims)
        net_equity = round_money(total_assets - total_liabilities)
        return {
            "asset_lines": [
                ("Cash", cash),
                ("Accounts Receivable (Student Debts)", receivables),
                ("Inventory at Cost", inventory),
            ],
            "total_assets": total_assets,
            "liability_lines": [
                ("Accounts Payable (Supplier Debts)", supplier_debt),
                ("Student Credit Balances", credit_balances),
                ("Employee Payable (Pending Claims)", pending_claims),
            ],
            "total_liabilities": total_liabilities,
            "net_equity": net_equity,
        }

    async def balance_sheet(
        self,
        as_at_date: date,
        date_from: date | None = None,
        date_to: date | None = None,
        breakdown_monthly: bool = False,
    ) -> dict:
        """
        Balance sheet as at date: assets (cash position, receivables, inventory),
        liabilities (supplier debt, credit balances, pending claims), net equity, ratios.
        If breakdown_monthly=True and date_from/date_to given, adds months and monthly amounts (as at each month end).
        """
        data = await self._balance_sheet_as_at(as_at_date)
        asset_lines = [
            BalanceSheetAssetLine(label=l, amount=a)
            for l, a in data["asset_lines"]
        ]
        liability_lines = [
            BalanceSheetLiabilityLine(label=l, amount=a)
            for l, a in data["liability_lines"]
        ]
        debt_to_asset_percent = (
            round(float(data["total_liabilities"] / data["total_assets"] * 100), 2)
            if data["total_assets"] and data["total_assets"] > 0
            else None
        )
        current_ratio = (
            round(float(data["total_assets"] / data["total_liabilities"]), 2)
            if data["total_liabilities"] and data["total_liabilities"] > 0
            else None
        )
        out: dict = {
            "as_at_date": as_at_date,
            "asset_lines": asset_lines,
            "total_assets": data["total_assets"],
            "liability_lines": liability_lines,
            "total_liabilities": data["total_liabilities"],
            "net_equity": data["net_equity"],
            "debt_to_asset_percent": debt_to_asset_percent,
            "current_ratio": current_ratio,
        }
        if not breakdown_monthly or not date_from or not date_to:
            return out
        months = _months_in_range(date_from, date_to)
        asset_by_label: dict[str, dict[str, Decimal]] = defaultdict(lambda: {})
        liability_by_label: dict[str, dict[str, Decimal]] = defaultdict(lambda: {})
        total_assets_monthly: dict[str, Decimal] = {}
        total_liabilities_monthly: dict[str, Decimal] = {}
        net_equity_monthly: dict[str, Decimal] = {}
        debt_to_asset_monthly: dict[str, float] = {}
        current_ratio_monthly: dict[str, float] = {}
        for mo in months:
            y, m = int(mo[:4]), int(mo[5:7])
            last = date(y, m, monthrange(y, m)[1])
            month_data = await self._balance_sheet_as_at(last)
            ta = month_data["total_assets"]
            tl = month_data["total_liabilities"]
            total_assets_monthly[mo] = ta
            total_liabilities_monthly[mo] = tl
            net_equity_monthly[mo] = month_data["net_equity"]
            if ta and ta > 0:
                debt_to_asset_monthly[mo] = round(float(tl / ta * 100), 2)
            if tl and tl > 0:
                current_ratio_monthly[mo] = round(float(ta / tl), 2)
            for l, a in month_data["asset_lines"]:
                asset_by_label[l][mo] = a
            for l, a in month_data["liability_lines"]:
                liability_by_label[l][mo] = a
        for line in asset_lines:
            line.monthly = dict(asset_by_label.get(line.label, {}))
        for line in liability_lines:
            line.monthly = dict(liability_by_label.get(line.label, {}))
        out["months"] = months
        out["total_assets_monthly"] = total_assets_monthly
        out["total_liabilities_monthly"] = total_liabilities_monthly
        out["net_equity_monthly"] = net_equity_monthly
        out["debt_to_asset_percent_monthly"] = debt_to_asset_monthly
        out["current_ratio_monthly"] = current_ratio_monthly
        return out

    async def collection_rate_trend(
        self,
        months: int = 12,
    ) -> dict:
        """
        Collection rate % over last N months. For each month: invoiced (issued), paid (payments in month), rate.
        """
        today = date.today()
        month_labels = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        rows = []
        total_inv = Decimal("0")
        total_paid = Decimal("0")
        statuses = (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
            InvoiceStatus.PAID.value,
        )
        for i in range(months - 1, -1, -1):
            # month end: today - i months
            y = today.year
            m = today.month - i
            while m <= 0:
                m += 12
                y -= 1
            start = date(y, m, 1)
            _, last_day = monthrange(y, m)
            end = date(y, m, last_day)
            year_month = f"{y}-{m:02d}"
            label = f"{month_labels[m - 1]} {y}"

            inv_q = (
                select(func.coalesce(func.sum(Invoice.total), 0)).where(
                    Invoice.issue_date >= start,
                    Invoice.issue_date <= end,
                    Invoice.status.in_(statuses),
                )
            )
            inv_res = await self.db.execute(inv_q)
            invoiced = round_money(Decimal(str(inv_res.scalar() or 0)))

            pay_q = (
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == PaymentStatus.COMPLETED.value,
                    Payment.payment_date >= start,
                    Payment.payment_date <= end,
                )
            )
            pay_res = await self.db.execute(pay_q)
            paid = round_money(Decimal(str(pay_res.scalar() or 0)))

            rate = (
                round(float(paid / invoiced * 100), 2) if invoiced and invoiced > 0 else None
            )
            total_inv += invoiced
            total_paid += paid
            rows.append(
                CollectionRateMonthRow(
                    year_month=year_month,
                    label=label,
                    total_invoiced=invoiced,
                    total_paid=paid,
                    rate_percent=rate,
                )
            )
        average_rate = (
            round(float(total_paid / total_inv * 100), 2) if total_inv and total_inv > 0 else None
        )
        return {
            "rows": rows,
            "average_rate_percent": average_rate,
            "target_rate_percent": 90,
        }

    async def discount_analysis(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Discount analysis by reason: students count, total amount, avg per student, % of revenue.
        Uses Discount on InvoiceLine -> Invoice; filter by Invoice.issue_date in period.
        """
        statuses = (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
            InvoiceStatus.PAID.value,
        )
        q = (
            select(
                Discount.reason_id,
                func.coalesce(DiscountReason.code, "other").label("reason_code"),
                func.coalesce(DiscountReason.name, "Other").label("reason_name"),
                func.count(func.distinct(Invoice.student_id)).label("students_count"),
                func.coalesce(func.sum(Discount.calculated_amount), 0).label("total_amount"),
            )
            .select_from(Discount)
            .join(InvoiceLine, Discount.invoice_line_id == InvoiceLine.id)
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
            .outerjoin(DiscountReason, Discount.reason_id == DiscountReason.id)
            .where(
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.status.in_(statuses),
            )
            .group_by(Discount.reason_id, DiscountReason.id)
        )
        res = await self.db.execute(q)
        raw_rows = res.all()

        revenue_q = (
            select(func.coalesce(func.sum(Invoice.total), 0)).where(
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.status.in_(statuses),
            )
        )
        rev_res = await self.db.execute(revenue_q)
        total_revenue = round_money(Decimal(str(rev_res.scalar() or 0)))

        rows = []
        summary_students = 0
        summary_amount = Decimal("0")
        for r in raw_rows:
            reason_id, reason_code, reason_name, cnt, amt = r
            amt = round_money(Decimal(str(amt)))
            cnt = int(cnt)
            avg_per = round_money(amt / cnt) if cnt else None
            pct = (
                round(float(amt / total_revenue * 100), 2)
                if total_revenue and total_revenue > 0 else None
            )
            summary_students += cnt
            summary_amount += amt
            rows.append(
                DiscountAnalysisRow(
                    reason_id=reason_id,
                    reason_code=str(reason_code) if reason_code else None,
                    reason_name=str(reason_name) if reason_name else "Other",
                    students_count=cnt,
                    total_amount=amt,
                    avg_per_student=avg_per,
                    percent_of_revenue=pct,
                )
            )
        pct_rev = (
            round(float(summary_amount / total_revenue * 100), 2)
            if total_revenue and total_revenue > 0 else None
        )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
            "summary": DiscountAnalysisSummary(
                students_count=summary_students,
                total_discount_amount=round_money(summary_amount),
                total_revenue=total_revenue,
                percent_of_revenue=pct_rev,
            ),
        }

    async def top_debtors(
        self,
        as_at_date: date | None = None,
        limit: int = 20,
    ) -> dict:
        """
        Top N students by debt (amount_due). Same buckets as aged_receivables but sorted by total desc, limited.
        Returns student_id, student_name, grade_name, total_debt, invoice_count, oldest_due_date.
        """
        as_at = as_at_date or date.today()
        ag = await self.aged_receivables(as_at_date=as_at)
        rows_data = ag["rows"]
        if not rows_data:
            return {
                "as_at_date": as_at,
                "limit": limit,
                "rows": [],
                "total_debt": Decimal("0"),
            }
        sorted_rows = sorted(rows_data, key=lambda r: -float(r.total))[:limit]
        total_debt = sum(r.total for r in sorted_rows)

        # Get grade_name and oldest_due_date per student
        student_ids = [r.student_id for r in sorted_rows]
        inv_q = (
            select(
                Invoice.student_id,
                func.count(Invoice.id).label("inv_count"),
                func.min(Invoice.due_date).label("oldest_due"),
            )
            .where(
                Invoice.student_id.in_(student_ids),
                Invoice.amount_due > 0,
                Invoice.status.in_(
                    [InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value]
                ),
            )
            .group_by(Invoice.student_id)
        )
        inv_res = await self.db.execute(inv_q)
        inv_by_student = {r[0]: (int(r[1]), r[2]) for r in inv_res.all()}

        students_q = (
            select(
                Student.id,
                func.concat(Student.first_name, " ", Student.last_name).label("full_name"),
                Grade.name,
            )
            .join(Grade, Student.grade_id == Grade.id)
            .where(Student.id.in_(student_ids))
        )
        st_res = await self.db.execute(students_q)
        student_info = {r[0]: (r[1], r[2]) for r in st_res.all()}

        rows = []
        for r in sorted_rows:
            info = student_info.get(r.student_id, ("", ""))
            inv_count, oldest_due = inv_by_student.get(r.student_id, (0, None))
            rows.append(
                TopDebtorRow(
                    student_id=r.student_id,
                    student_name=r.student_name,
                    grade_name=info[1] or "",
                    total_debt=round_money(r.total),
                    invoice_count=inv_count,
                    oldest_due_date=oldest_due,
                )
            )
        return {
            "as_at_date": as_at,
            "limit": limit,
            "rows": rows,
            "total_debt": round_money(total_debt),
        }

    async def procurement_summary(
        self,
        date_from: date,
        date_to: date,
        supplier_name: str | None = None,
    ) -> dict:
        """
        Procurement Summary: by supplier, PO count, total amount, paid, outstanding, status.
        Outstanding breakdown by age (0-30, 31-60, 61+ days since order_date).
        Only POs with order_date in [date_from, date_to], excluding cancelled/closed.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        q = (
            select(
                PurchaseOrder.supplier_name,
                func.count(PurchaseOrder.id).label("po_count"),
                func.coalesce(func.sum(PurchaseOrder.expected_total), 0).label("total_amount"),
                func.coalesce(func.sum(PurchaseOrder.paid_total), 0).label("paid"),
                func.coalesce(func.sum(PurchaseOrder.debt_amount), 0).label("outstanding"),
            )
            .where(
                PurchaseOrder.order_date >= date_from,
                PurchaseOrder.order_date <= date_to,
                PurchaseOrder.status.notin_(
                    [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value]
                ),
            )
            .group_by(PurchaseOrder.supplier_name)
        )
        if supplier_name:
            q = q.where(PurchaseOrder.supplier_name.ilike(f"%{supplier_name}%"))
        result = await self.db.execute(q)
        raw_rows = result.all()

        rows = []
        total_po_count = 0
        total_amount = Decimal("0")
        total_paid = Decimal("0")
        total_outstanding = Decimal("0")
        for r in raw_rows:
            sup_name, po_count, amt, paid, out = r
            amt = round_money(Decimal(str(amt)))
            paid = round_money(Decimal(str(paid)))
            out = round_money(Decimal(str(out)))
            status = "ok" if out <= 0 else "partial"
            total_po_count += int(po_count)
            total_amount += amt
            total_paid += paid
            total_outstanding += out
            rows.append(
                ProcurementSummaryRow(
                    supplier_name=sup_name,
                    po_count=int(po_count),
                    total_amount=amt,
                    paid=paid,
                    outstanding=out,
                    status=status,
                )
            )

        # Outstanding breakdown by age (days since order_date) for POs with debt
        as_at = date_to
        age_q = (
            select(
                PurchaseOrder.order_date,
                PurchaseOrder.debt_amount,
            )
            .where(
                PurchaseOrder.order_date >= date_from,
                PurchaseOrder.order_date <= date_to,
                PurchaseOrder.debt_amount > 0,
                PurchaseOrder.status.notin_(
                    [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value]
                ),
            )
        )
        if supplier_name:
            age_q = age_q.where(PurchaseOrder.supplier_name.ilike(f"%{supplier_name}%"))
        age_res = await self.db.execute(age_q)
        current_0_30 = Decimal("0")
        bucket_31_60 = Decimal("0")
        bucket_61_plus = Decimal("0")
        for r in age_res.all():
            order_d, debt = r[0], round_money(Decimal(str(r[1])))
            if not order_d:
                continue
            days = (as_at - order_d).days
            if days <= 30:
                current_0_30 += debt
            elif days <= 60:
                bucket_31_60 += debt
            else:
                bucket_61_plus += debt

        return {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
            "total_po_count": total_po_count,
            "total_amount": round_money(total_amount),
            "total_paid": round_money(total_paid),
            "total_outstanding": round_money(total_outstanding),
            "outstanding_breakdown": ProcurementSummaryOutstanding(
                current_0_30=round_money(current_0_30),
                bucket_31_60=round_money(bucket_31_60),
                bucket_61_plus=round_money(bucket_61_plus),
            ),
        }

    async def inventory_valuation(self, as_at_date: date) -> dict:
        """
        Inventory Valuation as at date: by category (items count, quantity, unit cost avg, total value).
        Uses current Stock (quantity_on_hand, average_cost). Turnover not computed (None).
        """
        # Stock is current state; we don't have historical snapshot, so "as_at" is conceptual
        q = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.count(Stock.id).label("items_count"),
                func.coalesce(func.sum(Stock.quantity_on_hand), 0).label("quantity"),
                func.coalesce(func.avg(Stock.average_cost), 0).label("unit_cost_avg"),
                func.coalesce(
                    func.sum(Stock.quantity_on_hand * Stock.average_cost), 0
                ).label("total_value"),
            )
            .select_from(Stock)
            .join(Item, Stock.item_id == Item.id)
            .join(Category, Item.category_id == Category.id)
            .where(Item.item_type == "product")
            .group_by(Category.id, Category.name)
            .order_by(Category.name)
        )
        result = await self.db.execute(q)
        raw_rows = result.all()

        rows = []
        total_items = 0
        total_quantity = 0
        total_value = Decimal("0")
        for r in raw_rows:
            cat_id, cat_name, items_count, qty, unit_avg, val = r
            qty = int(qty)
            unit_avg = round_money(Decimal(str(unit_avg))) if unit_avg else None
            val = round_money(Decimal(str(val)))
            total_items += int(items_count)
            total_quantity += qty
            total_value += val
            rows.append(
                InventoryValuationRow(
                    category_id=int(cat_id),
                    category_name=cat_name,
                    items_count=int(items_count),
                    quantity=qty,
                    unit_cost_avg=unit_avg,
                    total_value=val,
                    turnover=None,
                )
            )
        return {
            "as_at_date": as_at_date,
            "rows": rows,
            "total_items": total_items,
            "total_quantity": total_quantity,
            "total_value": round_money(total_value),
        }

    async def low_stock_alert(self) -> dict:
        """
        Low Stock Alert: items (product type) with stock where quantity_on_hand <= 0 or below min.
        Item has no min_stock_level in DB; use 0 as threshold: low = quantity_on_hand <= 0.
        status: "out" (<=0), "low" (1-10), "ok" (>10). suggested_order: 0 when out, else None.
        """
        q = (
            select(
                Item.id,
                Item.name,
                Item.sku_code,
                Stock.quantity_on_hand,
            )
            .select_from(Item)
            .join(Stock, Item.id == Stock.item_id)
            .where(Item.item_type == "product", Item.is_active.is_(True))
        )
        result = await self.db.execute(q)
        raw_rows = result.all()

        rows = []
        low_count = 0
        min_level = 0
        for r in raw_rows:
            item_id, name, sku, qty = r[0], r[1], r[2], int(r[3])
            if qty <= 0:
                status = "out"
                suggested = 10  # arbitrary reorder qty
                low_count += 1
            elif qty <= 10:
                status = "low"
                suggested = 10 - qty if qty < 10 else None
                low_count += 1
            else:
                status = "ok"
                suggested = None
            rows.append(
                LowStockAlertRow(
                    item_id=item_id,
                    item_name=name,
                    sku_code=sku,
                    current=qty,
                    min_level=min_level,
                    status=status,
                    suggested_order=suggested,
                )
            )
        # Sort: out first, then low, then ok; within same status by current ascending
        rows.sort(key=lambda x: (0 if x.status == "out" else 1 if x.status == "low" else 2, x.current))
        return {
            "rows": rows,
            "total_low_count": low_count,
        }

    async def stock_movement_report(
        self,
        date_from: date,
        date_to: date,
        movement_type: str | None = None,
    ) -> dict:
        """
        Stock Movement report: list movements in period with item name, ref display, user, balance.
        ref_display: from GRN number or Issuance number when reference_type matches.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        q = (
            select(
                StockMovement.id,
                StockMovement.created_at,
                StockMovement.movement_type,
                StockMovement.item_id,
                Item.name.label("item_name"),
                StockMovement.quantity,
                StockMovement.quantity_after,
                StockMovement.reference_type,
                StockMovement.reference_id,
                StockMovement.created_by_id,
            )
            .select_from(StockMovement)
            .join(Item, StockMovement.item_id == Item.id)
            .where(
                func.date(StockMovement.created_at) >= date_from,
                func.date(StockMovement.created_at) <= date_to,
            )
            .order_by(StockMovement.created_at.desc())
        )
        if movement_type:
            q = q.where(StockMovement.movement_type == movement_type)
        result = await self.db.execute(q)
        raw = result.all()

        # Resolve ref_display: load GRN and Issuance numbers for reference_id
        grn_ids = [r[7] for r in raw if r[6] == "grn" and r[7]]
        iss_ids = [r[7] for r in raw if r[6] == "issuance" and r[7]]
        grn_map = {}
        if grn_ids:
            grn_res = await self.db.execute(
                select(GoodsReceivedNote.id, GoodsReceivedNote.grn_number).where(
                    GoodsReceivedNote.id.in_(grn_ids)
                )
            )
            grn_map = {r[0]: r[1] for r in grn_res.all()}
        iss_map = {}
        if iss_ids:
            iss_res = await self.db.execute(
                select(Issuance.id, Issuance.issuance_number).where(Issuance.id.in_(iss_ids))
            )
            iss_map = {r[0]: r[1] for r in iss_res.all()}

        from src.core.auth.models import User as AuthUser
        user_ids = {r[9] for r in raw if r[9]}
        user_names = {}
        if user_ids:
            users_q = await self.db.execute(
                select(
                    AuthUser.id,
                    func.coalesce(AuthUser.full_name, "Unknown"),
                ).where(AuthUser.id.in_(user_ids))
            )
            user_names = {r[0]: (r[1] or "Unknown") for r in users_q.all()}

        rows = []
        for r in raw:
            mov_id, created_at, mtype, item_id, item_name, qty, qty_after, ref_type, ref_id, created_by_id = r
            ref_display = None
            if ref_type and ref_id:
                if ref_type == "grn":
                    ref_display = grn_map.get(ref_id)
                elif ref_type == "issuance":
                    ref_display = iss_map.get(ref_id)
                if not ref_display:
                    ref_display = f"{ref_type or 'n/a'}#{ref_id}"
            created_date = created_at.date() if hasattr(created_at, "date") else created_at
            if isinstance(created_date, str):
                created_date = date.fromisoformat(created_date[:10])
            user_name = user_names.get(created_by_id, "Unknown")
            rows.append(
                StockMovementRow(
                    movement_id=mov_id,
                    movement_date=created_date,
                    movement_type=mtype or "",
                    item_id=item_id,
                    item_name=item_name,
                    quantity=qty,
                    ref_display=ref_display,
                    created_by_name=user_name,
                    balance_after=qty_after,
                )
            )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
        }

    async def compensation_summary(
        self,
        date_from: date,
        date_to: date,
        status: str | None = None,
    ) -> dict:
        """
        Compensation Summary: by employee, claims count, total/approved/paid/pending.
        Optional filter by status. Uses expense_date for period.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        from src.core.auth.models import User as AuthUser

        q = (
            select(
                ExpenseClaim.employee_id,
                AuthUser.full_name.label("employee_name"),
                func.count(ExpenseClaim.id).label("claims_count"),
                func.coalesce(func.sum(ExpenseClaim.amount), 0).label("total_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ExpenseClaim.status.in_(
                                    [
                                        ExpenseClaimStatus.APPROVED.value,
                                        ExpenseClaimStatus.PARTIALLY_PAID.value,
                                        ExpenseClaimStatus.PAID.value,
                                    ]
                                ),
                                ExpenseClaim.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("approved_amount"),
                func.coalesce(func.sum(ExpenseClaim.paid_amount), 0).label("paid_amount"),
                func.coalesce(func.sum(ExpenseClaim.remaining_amount), 0).label("pending_amount"),
            )
            .select_from(ExpenseClaim)
            .join(AuthUser, ExpenseClaim.employee_id == AuthUser.id)
            .where(
                ExpenseClaim.expense_date >= date_from,
                ExpenseClaim.expense_date <= date_to,
                ExpenseClaim.status != ExpenseClaimStatus.REJECTED.value,
            )
            .group_by(ExpenseClaim.employee_id, AuthUser.full_name)
        )
        if status:
            q = q.where(ExpenseClaim.status == status)
        result = await self.db.execute(q)
        raw_rows = result.all()

        rows = []
        total_claims = 0
        total_amount = Decimal("0")
        total_approved = Decimal("0")
        total_paid = Decimal("0")
        total_pending = Decimal("0")
        for r in raw_rows:
            emp_id, emp_name, cnt, amt, approved, paid, pending = r
            amt = round_money(Decimal(str(amt)))
            approved = round_money(Decimal(str(approved)))
            paid = round_money(Decimal(str(paid)))
            pending = round_money(Decimal(str(pending)))
            total_claims += int(cnt)
            total_amount += amt
            total_approved += approved
            total_paid += paid
            total_pending += pending
            rows.append(
                CompensationSummaryRow(
                    employee_id=emp_id,
                    employee_name=emp_name or "Unknown",
                    claims_count=int(cnt),
                    total_amount=amt,
                    approved_amount=approved,
                    paid_amount=paid,
                    pending_amount=pending,
                )
            )

        # Pending approval: count and sum where status = pending_approval
        pending_app_q = (
            select(
                func.count(ExpenseClaim.id).label("cnt"),
                func.coalesce(func.sum(ExpenseClaim.amount), 0).label("amt"),
            )
            .where(
                ExpenseClaim.expense_date >= date_from,
                ExpenseClaim.expense_date <= date_to,
                ExpenseClaim.status == ExpenseClaimStatus.PENDING_APPROVAL.value,
            )
        )
        pending_app_res = await self.db.execute(pending_app_q)
        pa_row = pending_app_res.one()
        pending_approval_count = int(pa_row[0])
        pending_approval_amount = round_money(Decimal(str(pa_row[1])))

        # Approved but unpaid: approved or partially_paid with remaining_amount > 0
        approved_unpaid_q = (
            select(
                func.count(ExpenseClaim.id).label("cnt"),
                func.coalesce(func.sum(ExpenseClaim.remaining_amount), 0).label("amt"),
            )
            .where(
                ExpenseClaim.expense_date >= date_from,
                ExpenseClaim.expense_date <= date_to,
                ExpenseClaim.status.in_(
                    [ExpenseClaimStatus.APPROVED.value, ExpenseClaimStatus.PARTIALLY_PAID.value]
                ),
                ExpenseClaim.remaining_amount > 0,
            )
        )
        approved_unpaid_res = await self.db.execute(approved_unpaid_q)
        au_row = approved_unpaid_res.one()
        approved_unpaid_count = int(au_row[0])
        approved_unpaid_amount = round_money(Decimal(str(au_row[1])))

        return {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
            "summary": CompensationSummaryTotals(
                total_claims=total_claims,
                total_amount=round_money(total_amount),
                total_approved=round_money(total_approved),
                total_paid=round_money(total_paid),
                total_pending=round_money(total_pending),
                pending_approval_count=pending_approval_count,
                pending_approval_amount=pending_approval_amount,
                approved_unpaid_count=approved_unpaid_count,
                approved_unpaid_amount=approved_unpaid_amount,
            ),
        }

    async def expense_claims_by_category(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Expense Claims by Category (purpose): amount and count per purpose, percent of total.
        Uses expense_date for period. Excludes rejected.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        q = (
            select(
                PaymentPurpose.id.label("purpose_id"),
                PaymentPurpose.name.label("purpose_name"),
                func.coalesce(func.sum(ExpenseClaim.amount), 0).label("amount"),
                func.count(ExpenseClaim.id).label("claims_count"),
            )
            .select_from(ExpenseClaim)
            .join(PaymentPurpose, ExpenseClaim.purpose_id == PaymentPurpose.id)
            .where(
                ExpenseClaim.expense_date >= date_from,
                ExpenseClaim.expense_date <= date_to,
                ExpenseClaim.status != ExpenseClaimStatus.REJECTED.value,
            )
            .group_by(PaymentPurpose.id, PaymentPurpose.name)
            .order_by(func.sum(ExpenseClaim.amount).desc())
        )
        result = await self.db.execute(q)
        raw_rows = result.all()

        total_amount = Decimal("0")
        for r in raw_rows:
            total_amount += round_money(Decimal(str(r[2])))

        rows = []
        for r in raw_rows:
            purpose_id, purpose_name, amt, cnt = r
            amt = round_money(Decimal(str(amt)))
            pct = (
                round(float(amt / total_amount * 100), 2)
                if total_amount and total_amount > 0 else None
            )
            rows.append(
                ExpenseClaimsByCategoryRow(
                    purpose_id=int(purpose_id),
                    purpose_name=purpose_name or "Other",
                    amount=amt,
                    claims_count=int(cnt),
                    percent_of_total=pct,
                )
            )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
            "total_amount": round_money(total_amount),
        }

    async def revenue_trend(self, years: int = 3) -> dict:
        """
        Revenue per student trend over last N years (calendar year).
        For each year: total revenue (student payments), count of students with at least one payment, avg per student.
        growth_percent: (last_year_avg - first_year_avg) / first_year_avg * 100.
        """
        today = date.today()
        current_year = today.year
        rows = []
        first_avg = None
        last_avg = None
        for i in range(years - 1, -1, -1):
            y = current_year - i
            start = date(y, 1, 1)
            end = date(y, 12, 31)
            rev_q = (
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == PaymentStatus.COMPLETED.value,
                    Payment.payment_date >= start,
                    Payment.payment_date <= end,
                )
            )
            rev_res = await self.db.execute(rev_q)
            total_rev = round_money(Decimal(str(rev_res.scalar() or 0)))
            cnt_q = (
                select(func.count(func.distinct(Payment.student_id))).where(
                    Payment.status == PaymentStatus.COMPLETED.value,
                    Payment.payment_date >= start,
                    Payment.payment_date <= end,
                    Payment.student_id.isnot(None),
                )
            )
            cnt_res = await self.db.execute(cnt_q)
            students_count = int(cnt_res.scalar() or 0)
            avg_per = round_money(total_rev / students_count) if students_count else None
            if avg_per is not None:
                if first_avg is None:
                    first_avg = float(avg_per)
                last_avg = float(avg_per)
            rows.append(
                RevenueTrendRow(
                    year=y,
                    label=f"{y}/{y + 1}",
                    total_revenue=total_rev,
                    students_count=students_count,
                    avg_revenue_per_student=avg_per,
                )
            )
        growth_percent = (
            round((last_avg - first_avg) / first_avg * 100, 2)
            if first_avg and first_avg > 0 and last_avg is not None else None
        )
        return {
            "rows": rows,
            "growth_percent": growth_percent,
            "years_included": years,
        }

    async def payment_method_distribution(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Payment method distribution for student payments in period.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        q = (
            select(
                Payment.payment_method,
                func.coalesce(func.sum(Payment.amount), 0).label("amount"),
            )
            .where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to,
            )
            .group_by(Payment.payment_method)
        )
        result = await self.db.execute(q)
        raw = result.all()
        total = sum(round_money(Decimal(str(r[1]))) for r in raw)
        method_labels = {"mpesa": "M-Pesa", "bank_transfer": "Bank Transfer", "cash": "Cash", "cheque": "Cheque"}
        rows = []
        for method, amt in raw:
            amt = round_money(Decimal(str(amt)))
            pct = round(float(amt / total * 100), 2) if total and total > 0 else None
            rows.append(
                PaymentMethodDistributionRow(
                    payment_method=method or "other",
                    label=method_labels.get((method or "").lower(), (method or "Other").title()),
                    amount=amt,
                    percent_of_total=pct,
                )
            )
        return {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
            "total_amount": round_money(total),
        }

    async def term_comparison(self, term1_id: int, term2_id: int) -> dict:
        """
        Term-over-term comparison: students enrolled, total invoiced, total collected, collection rate, avg fee/student, discounts.
        """
        statuses = (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
            InvoiceStatus.PAID.value,
        )
        terms_res = await self.db.execute(
            select(Term).where(Term.id.in_([term1_id, term2_id]))
        )
        terms = {t.id: t for t in terms_res.scalars().unique().all()}
        if term1_id not in terms or term2_id not in terms:
            raise NotFoundError("Term", f"{term1_id},{term2_id}")
        t1, t2 = terms[term1_id], terms[term2_id]
        metrics = []

        async def get_term_metrics(term: Term) -> tuple:
            inv_q = (
                select(
                    func.count(func.distinct(Invoice.student_id)).label("students"),
                    func.coalesce(func.sum(Invoice.total), 0).label("invoiced"),
                    func.coalesce(func.sum(Invoice.paid_total), 0).label("paid"),
                    func.coalesce(func.sum(Invoice.discount_total), 0).label("discounts"),
                )
                .where(
                    Invoice.term_id == term.id,
                    Invoice.status.in_(statuses),
                )
            )
            r = (await self.db.execute(inv_q)).one()
            students = int(r[0])
            invoiced = round_money(Decimal(str(r[1])))
            paid = round_money(Decimal(str(r[2])))
            discounts = round_money(Decimal(str(r[3])))
            rate = round(float(paid / invoiced * 100), 2) if invoiced and invoiced > 0 else None
            avg_fee = round_money(invoiced / students) if students else None
            return students, invoiced, paid, rate, avg_fee, discounts

        s1, inv1, paid1, rate1, avg1, disc1 = await get_term_metrics(t1)
        s2, inv2, paid2, rate2, avg2, disc2 = await get_term_metrics(t2)

        def pct_change(a: float | None, b: float | None) -> tuple:
            if b is None or b == 0:
                return None, None
            if a is None:
                return None, None
            ch = a - b
            pct = round((ch / float(b)) * 100, 2)
            return ch, pct

        metrics.append(
            TermComparisonMetric(
                name="Students Enrolled",
                term1_value=s1,
                term2_value=s2,
                change_abs=s2 - s1,
                change_percent=round((s2 - s1) / s1 * 100, 2) if s1 else None,
            )
        )
        metrics.append(
            TermComparisonMetric(
                name="Total Invoiced (KES)",
                term1_value=float(inv1),
                term2_value=float(inv2),
                change_abs=float(inv2 - inv1),
                change_percent=round(float((inv2 - inv1) / inv1 * 100), 2) if inv1 else None,
            )
        )
        metrics.append(
            TermComparisonMetric(
                name="Total Collected (KES)",
                term1_value=float(paid1),
                term2_value=float(paid2),
                change_abs=float(paid2 - paid1),
                change_percent=round(float((paid2 - paid1) / paid1 * 100), 2) if paid1 else None,
            )
        )
        metrics.append(
            TermComparisonMetric(
                name="Collection Rate (%)",
                term1_value=rate1 if rate1 is not None else "—",
                term2_value=rate2 if rate2 is not None else "—",
                change_abs=(rate2 - rate1) if rate1 is not None and rate2 is not None else None,
                change_percent=(rate2 - rate1) if rate1 is not None and rate2 is not None else None,
            )
        )
        metrics.append(
            TermComparisonMetric(
                name="Avg Fee/Student (KES)",
                term1_value=float(avg1) if avg1 is not None else "—",
                term2_value=float(avg2) if avg2 is not None else "—",
                change_abs=float(avg2 - avg1) if avg1 and avg2 else None,
                change_percent=round(float((avg2 - avg1) / avg1 * 100), 2) if avg1 and avg1 > 0 and avg2 else None,
            )
        )
        metrics.append(
            TermComparisonMetric(
                name="Discounts Given (KES)",
                term1_value=float(disc1),
                term2_value=float(disc2),
                change_abs=float(disc2 - disc1),
                change_percent=round(float((disc2 - disc1) / disc1 * 100), 2) if disc1 else None,
            )
        )
        return {
            "term1_id": term1_id,
            "term1_display_name": t1.display_name,
            "term2_id": term2_id,
            "term2_display_name": t2.display_name,
            "metrics": metrics,
        }

    async def kpis_report(
        self,
        year: int | None = None,
        term_id: int | None = None,
    ) -> dict:
        """
        KPIs & key metrics for a period. If term_id given, use term dates; else use calendar year.
        """
        today = date.today()
        current_year = year or today.year
        period_type = "term" if term_id else "year"
        term_display_name = None
        active_term = None
        if term_id:
            term_res = await self.db.execute(select(Term).where(Term.id == term_id))
            active_term = term_res.scalar_one_or_none()
            if not active_term:
                raise NotFoundError("Term", term_id)
            term_display_name = active_term.display_name

        if active_term and active_term.start_date and active_term.end_date:
            date_from = active_term.start_date
            date_to = active_term.end_date
        else:
            date_from = date(current_year, 1, 1)
            date_to = date(current_year, 12, 31)

        active_students = await self.db.execute(
            select(func.count(Student.id)).where(Student.status == StudentStatus.ACTIVE.value)
        )
        active_students_count = int(active_students.scalar() or 0)

        rev_q = (
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to,
            )
        )
        total_revenue = round_money(Decimal(str((await self.db.execute(rev_q)).scalar() or 0)))

        inv_q = (
            select(func.coalesce(func.sum(Invoice.total), 0)).where(
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.status.in_(
                    [InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value, InvoiceStatus.PAID.value]
                ),
            )
        )
        total_invoiced = round_money(Decimal(str((await self.db.execute(inv_q)).scalar() or 0)))
        paid_q = (
            select(func.coalesce(func.sum(Invoice.paid_total), 0)).where(
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.status.in_(
                    [InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value, InvoiceStatus.PAID.value]
                ),
            )
        )
        total_paid = round_money(Decimal(str((await self.db.execute(paid_q)).scalar() or 0)))
        collection_rate_percent = (
            round(float(total_paid / total_invoiced * 100), 2) if total_invoiced and total_invoiced > 0 else None
        )

        proc_q = (
            select(func.coalesce(func.sum(ProcurementPayment.amount), 0)).where(
                ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
                ProcurementPayment.payment_date >= date_from,
                ProcurementPayment.payment_date <= date_to,
            )
        )
        comp_q = (
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.payout_date >= date_from,
                CompensationPayout.payout_date <= date_to,
            )
        )
        proc_amt = round_money(Decimal(str((await self.db.execute(proc_q)).scalar() or 0)))
        comp_amt = round_money(Decimal(str((await self.db.execute(comp_q)).scalar() or 0)))
        total_expenses = round_money(proc_amt + comp_amt)

        debt_q = (
            select(func.coalesce(func.sum(Invoice.amount_due), 0)).where(
                Invoice.status.in_([InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value]),
                Invoice.amount_due > 0,
            )
        )
        student_debt = round_money(Decimal(str((await self.db.execute(debt_q)).scalar() or 0)))
        supp_q = (
            select(func.coalesce(func.sum(PurchaseOrder.debt_amount), 0)).where(
                PurchaseOrder.status.notin_(
                    [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value]
                )
            )
        )
        supplier_debt = round_money(Decimal(str((await self.db.execute(supp_q)).scalar() or 0)))
        claims_q = (
            select(func.coalesce(func.sum(ExpenseClaim.remaining_amount), 0)).where(
                ExpenseClaim.status.in_(
                    [ExpenseClaimStatus.PENDING_APPROVAL.value, ExpenseClaimStatus.APPROVED.value]
                ),
                ExpenseClaim.remaining_amount > 0,
            )
        )
        pending_claims_amount = round_money(Decimal(str((await self.db.execute(claims_q)).scalar() or 0)))

        return {
            "period_type": period_type,
            "year": current_year if period_type == "year" else None,
            "term_id": term_id,
            "term_display_name": term_display_name,
            "active_students_count": active_students_count,
            "total_revenue": total_revenue,
            "total_invoiced": total_invoiced,
            "collection_rate_percent": collection_rate_percent,
            "total_expenses": total_expenses,
            "student_debt": student_debt,
            "supplier_debt": supplier_debt,
            "pending_claims_amount": pending_claims_amount,
        }
