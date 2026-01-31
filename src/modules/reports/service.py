"""Service for reports (Admin/SuperAdmin)."""

from datetime import date
from decimal import Decimal
from collections import defaultdict
from calendar import monthrange

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import NotFoundError
from src.modules.compensations.models import CompensationPayout, ExpenseClaim, ExpenseClaimStatus
from src.modules.discounts.models import Discount, DiscountReason
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.inventory.models import Stock
from src.modules.payments.models import CreditAllocation, Payment, PaymentStatus
from src.modules.procurement.models import (
    ProcurementPayment,
    ProcurementPaymentStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
)
from src.modules.students.models import Grade, Student
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
            raise NotFoundError(f"Term with id {term_id} not found")

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

    async def profit_loss(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Profit & Loss: revenue (invoiced by type), less discounts, expenses (procurement + compensations).

        Only invoices with issue_date in [date_from, date_to] and status issued/partially_paid/paid.
        """
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
        revenue_lines = []
        gross_revenue = Decimal("0")
        total_discounts = Decimal("0")
        for inv_type, tot, disc in rev_rows:
            tot = round_money(Decimal(str(tot)))
            disc = round_money(Decimal(str(disc)))
            gross_revenue += tot
            total_discounts += disc
            revenue_lines.append(
                ProfitLossRevenueLine(
                    label=type_labels.get(inv_type, inv_type or "Other"),
                    amount=tot,
                )
            )
        net_revenue = round_money(gross_revenue - total_discounts)

        # Expenses: procurement + compensations in period
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

        expense_lines = [
            ProfitLossExpenseLine(label="Procurement (Inventory)", amount=proc_total),
            ProfitLossExpenseLine(label="Employee Compensations", amount=comp_total),
        ]
        total_expenses = round_money(proc_total + comp_total)
        net_profit = round_money(net_revenue - total_expenses)
        profit_margin_percent = (
            round(float(net_profit / net_revenue * 100), 2) if net_revenue and net_revenue > 0 else None
        )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "revenue_lines": revenue_lines,
            "gross_revenue": gross_revenue,
            "total_discounts": total_discounts,
            "net_revenue": net_revenue,
            "expense_lines": expense_lines,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "profit_margin_percent": profit_margin_percent,
        }

    async def cash_flow(
        self,
        date_from: date,
        date_to: date,
        payment_method: str | None = None,
    ) -> dict:
        """
        Cash flow: opening balance (net cash position before date_from), inflows (student payments),
        outflows (procurement + compensations), closing balance.

        payment_method: optional filter for student payments (mpesa, bank_transfer, or None for all).
        """
        # Opening: net cash position before date_from (all payments - proc - comp)
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

        # Inflows in period: student payments, optionally by method
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
        inflow_lines = [
            CashFlowInflowLine(label=method_labels.get(m, m or "Other"), amount=round_money(Decimal(str(a))))
            for m, a in inflow_res.all()
        ]
        total_inflows = round_money(sum(l.amount for l in inflow_lines))

        # Outflows in period
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
        outflow_lines = [
            CashFlowOutflowLine(label="Supplier Payments", amount=proc_amt),
            CashFlowOutflowLine(label="Employee Compensations", amount=comp_amt),
        ]
        total_outflows = round_money(proc_amt + comp_amt)
        net_cash_flow = round_money(total_inflows - total_outflows)
        closing_balance = round_money(opening_balance + net_cash_flow)

        return {
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

    async def balance_sheet(self, as_at_date: date) -> dict:
        """
        Balance sheet as at date: assets (cash position, receivables, inventory),
        liabilities (supplier debt, credit balances, pending claims), net equity, ratios.
        """
        # Cash position = student payments - procurement - compensations up to as_at
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

        # Receivables: student debts (invoices with amount_due > 0, not paid/cancelled)
        excluded = (InvoiceStatus.PAID.value, InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value)
        recv = await self.db.execute(
            select(func.coalesce(func.sum(Invoice.amount_due), 0)).where(
                Invoice.status.notin_(excluded),
            )
        )
        receivables = round_money(Decimal(str(recv.scalar() or 0)))

        # Inventory at cost
        stock_res = await self.db.execute(
            select(
                func.coalesce(func.sum(Stock.quantity_on_hand * Stock.average_cost), 0),
            )
        )
        inventory = round_money(Decimal(str(stock_res.scalar() or 0)))

        asset_lines = [
            BalanceSheetAssetLine(label="Cash", amount=cash),
            BalanceSheetAssetLine(label="Accounts Receivable (Student Debts)", amount=receivables),
            BalanceSheetAssetLine(label="Inventory at Cost", amount=inventory),
        ]
        total_assets = round_money(cash + receivables + inventory)

        # Liabilities: supplier debt, credit balances, pending claims
        supp = await self.db.execute(
            select(func.coalesce(func.sum(PurchaseOrder.debt_amount), 0)).where(
                PurchaseOrder.status.notin_(
                    [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value]
                )
            )
        )
        supplier_debt = round_money(Decimal(str(supp.scalar() or 0)))

        pay_tot = await self.db.execute(
            select(
                Payment.student_id,
                func.coalesce(func.sum(Payment.amount), 0).label("s"),
            ).where(Payment.status == PaymentStatus.COMPLETED.value).group_by(Payment.student_id)
        )
        payments_by_student = {r[0]: Decimal(str(r[1])) for r in pay_tot.all()}
        alloc_tot = await self.db.execute(
            select(
                CreditAllocation.student_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0).label("s"),
            ).group_by(CreditAllocation.student_id)
        )
        allocated_by_student = {r[0]: Decimal(str(r[1])) for r in alloc_tot.all()}
        credit_total = Decimal("0")
        for sid in set(payments_by_student) | set(allocated_by_student):
            credit_total += round_money(
                payments_by_student.get(sid, Decimal("0")) - allocated_by_student.get(sid, Decimal("0"))
            )
        credit_balances = round_money(credit_total)

        pending_statuses = (
            ExpenseClaimStatus.PENDING_APPROVAL.value,
            ExpenseClaimStatus.APPROVED.value,
        )
        claims = await self.db.execute(
            select(func.coalesce(func.sum(ExpenseClaim.remaining_amount), 0)).where(
                ExpenseClaim.status.in_(pending_statuses),
                ExpenseClaim.remaining_amount > 0,
            )
        )
        pending_claims = round_money(Decimal(str(claims.scalar() or 0)))

        liability_lines = [
            BalanceSheetLiabilityLine(label="Accounts Payable (Supplier Debts)", amount=supplier_debt),
            BalanceSheetLiabilityLine(label="Student Credit Balances", amount=credit_balances),
            BalanceSheetLiabilityLine(label="Employee Payable (Pending Claims)", amount=pending_claims),
        ]
        total_liabilities = round_money(supplier_debt + credit_balances + pending_claims)
        net_equity = round_money(total_assets - total_liabilities)
        debt_to_asset_percent = (
            round(float(total_liabilities / total_assets * 100), 2) if total_assets and total_assets > 0 else None
        )
        current_ratio = (
            round(float(total_assets / total_liabilities), 2) if total_liabilities and total_liabilities > 0 else None
        )

        return {
            "as_at_date": as_at_date,
            "asset_lines": asset_lines,
            "total_assets": total_assets,
            "liability_lines": liability_lines,
            "total_liabilities": total_liabilities,
            "net_equity": net_equity,
            "debt_to_asset_percent": debt_to_asset_percent,
            "current_ratio": current_ratio,
        }

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
            select(Student.id, Student.full_name, Grade.name)
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
