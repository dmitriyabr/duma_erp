"""Accountant export service: build CSV/Excel for accountant reports."""

import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.invoices.models import Invoice, InvoiceStatus
from src.modules.payments.models import CreditAllocation, Payment, PaymentStatus
from src.modules.procurement.models import ProcurementPayment, ProcurementPaymentStatus
from src.modules.students.models import Student
from src.shared.utils.money import round_money
from src.modules.bank_statements.models import BankStatementImport, BankTransaction, BankTransactionMatch


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


async def list_bank_transfers_for_export(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    limit: int = 20000,
) -> list[BankTransaction]:
    q = (
        select(BankTransaction)
        .outerjoin(
            BankTransactionMatch,
            BankTransactionMatch.bank_transaction_id == BankTransaction.id,
        )
        .where(BankTransaction.amount < 0)
        .where(BankTransaction.value_date >= date_from)
        .where(BankTransaction.value_date <= date_to)
        .options(
            selectinload(BankTransaction.match).selectinload(BankTransactionMatch.procurement_payment),
            selectinload(BankTransaction.match).selectinload(BankTransactionMatch.compensation_payout),
        )
        .order_by(BankTransaction.value_date, BankTransaction.id)
        .limit(limit)
    )
    result = await db.execute(q)
    return list(result.scalars().unique().all())


def build_bank_transfers_csv(
    rows: list[BankTransaction],
    app_base_url: str = "",
) -> str:
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Value Date",
            "Description",
            "Reference",
            "Type",
            "Amount",
            "Matched entity type",
            "Matched document#",
            "Proof link",
        ]
    )
    for t in rows:
        match = t.match
        entity_type = ""
        entity_number = ""
        proof_link = ""
        if match and match.procurement_payment_id and match.procurement_payment:
            entity_type = "procurement_payment"
            entity_number = match.procurement_payment.payment_number
            if app_base_url and match.procurement_payment.proof_attachment_id:
                proof_link = f"{app_base_url}/attachment/{match.procurement_payment.proof_attachment_id}/download"
        elif match and match.compensation_payout_id and match.compensation_payout:
            entity_type = "compensation_payout"
            entity_number = match.compensation_payout.payout_number
            if app_base_url and match.compensation_payout.proof_attachment_id:
                proof_link = f"{app_base_url}/attachment/{match.compensation_payout.proof_attachment_id}/download"

        writer.writerow(
            [
                t.value_date.isoformat(),
                t.description,
                t.account_owner_reference or "",
                t.txn_type or "",
                str(t.amount),
                entity_type,
                entity_number,
                proof_link,
            ]
        )
    return out.getvalue()


async def list_bank_statement_imports_for_export(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    limit: int = 5000,
) -> list[BankStatementImport]:
    q = (
        select(BankStatementImport)
        .where(BankStatementImport.range_from.is_not(None))
        .where(BankStatementImport.range_to.is_not(None))
        .where(BankStatementImport.range_to >= date_from)
        .where(BankStatementImport.range_from <= date_to)
        .order_by(BankStatementImport.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return list(result.scalars().all())


def build_bank_statement_imports_csv(
    rows: list[BankStatementImport],
    app_base_url: str = "",
) -> str:
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Import ID",
            "File name",
            "Range from",
            "Range to",
            "Download link",
            "Created at",
        ]
    )
    for imp in rows:
        link = (
            f"{app_base_url}/attachment/{imp.attachment_id}/download"
            if app_base_url
            else ""
        )
        writer.writerow(
            [
                imp.id,
                imp.file_name,
                imp.range_from.isoformat() if imp.range_from else "",
                imp.range_to.isoformat() if imp.range_to else "",
                link,
                imp.created_at.isoformat(),
            ]
        )
    return out.getvalue()


async def list_student_balance_changes_for_export(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    limit: int = 10000,
) -> list[dict]:
    """
    List all balance-affecting transactions with running balances, grouped by student.
    Returns list of dicts with student info, opening/closing balances, and transactions.
    """
    pay_students = await db.execute(
        select(Payment.student_id)
        .where(Payment.payment_date >= date_from)
        .where(Payment.payment_date <= date_to)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .distinct()
    )
    invoice_students = await db.execute(
        select(Invoice.student_id)
        .where(Invoice.issue_date >= date_from)
        .where(Invoice.issue_date <= date_to)
        .where(Invoice.status.notin_([InvoiceStatus.DRAFT.value, InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value]))
        .distinct()
    )
    student_ids = set([r[0] for r in pay_students.all()] + [r[0] for r in invoice_students.all()])

    if not student_ids:
        return []

    students_q = (
        select(Student)
        .where(Student.id.in_(list(student_ids)))
        .options(selectinload(Student.grade))
    )
    students_result = await db.execute(students_q)
    students = {s.id: s for s in students_result.scalars().unique().all()}

    # Batch queries for opening balances (avoid N+1)
    student_ids_list = list(student_ids)

    opening_payments_result = await db.execute(
        select(
            Payment.student_id,
            func.coalesce(func.sum(Payment.amount), 0)
        ).where(
            Payment.student_id.in_(student_ids_list),
            Payment.status == PaymentStatus.COMPLETED.value,
            Payment.payment_date < date_from,
        ).group_by(Payment.student_id)
    )
    opening_payments_map = {
        row[0]: Decimal(str(row[1])) for row in opening_payments_result.all()
    }

    opening_allocations_result = await db.execute(
        select(
            CreditAllocation.student_id,
            func.coalesce(func.sum(CreditAllocation.amount), 0)
        ).where(
            CreditAllocation.student_id.in_(student_ids_list),
            func.date(CreditAllocation.created_at) < date_from,
        ).group_by(CreditAllocation.student_id)
    )
    opening_allocations_map = {
        row[0]: Decimal(str(row[1])) for row in opening_allocations_result.all()
    }

    excluded = (InvoiceStatus.PAID.value, InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value)
    opening_debt_result = await db.execute(
        select(
            Invoice.student_id,
            func.coalesce(func.sum(Invoice.amount_due), 0)
        ).where(
            Invoice.student_id.in_(student_ids_list),
            Invoice.status.notin_(excluded),
            Invoice.issue_date < date_from,
        ).group_by(Invoice.student_id)
    )
    opening_debt_map = {
        row[0]: Decimal(str(row[1])) for row in opening_debt_result.all()
    }

    opening_balances = {}
    for student_id in student_ids:
        opening_credits = opening_payments_map.get(student_id, Decimal("0"))
        opening_allocated = opening_allocations_map.get(student_id, Decimal("0"))
        opening_credit_balance = opening_credits - opening_allocated
        opening_debt = opening_debt_map.get(student_id, Decimal("0"))
        opening_balances[student_id] = round_money(opening_debt - opening_credit_balance)

    pay_q = (
        select(Payment)
        .where(Payment.payment_date >= date_from)
        .where(Payment.payment_date <= date_to)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.student_id.in_(student_ids_list))
        .order_by(Payment.payment_date, Payment.id)
        .limit(limit)
    )
    pay_result = await db.execute(pay_q)
    payments = list(pay_result.scalars().unique().all())

    invoice_q = (
        select(Invoice)
        .where(Invoice.issue_date >= date_from)
        .where(Invoice.issue_date <= date_to)
        .where(Invoice.status.notin_([InvoiceStatus.DRAFT.value, InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value]))
        .where(Invoice.student_id.in_(student_ids_list))
        .order_by(Invoice.issue_date, Invoice.id)
        .limit(limit)
    )
    invoice_result = await db.execute(invoice_q)
    invoices = list(invoice_result.scalars().unique().all())

    students_data: dict[int, dict] = {}

    for student_id in student_ids:
        student = students.get(student_id)
        if not student:
            continue
        students_data[student_id] = {
            "student_id": student_id,
            "student_name": student.full_name,
            "student_number": student.student_number,
            "grade_name": student.grade.name if student.grade else "",
            "opening_balance": opening_balances.get(student_id, Decimal("0.00")),
            "transactions": [],
            "total_credits": Decimal("0.00"),
            "total_debits": Decimal("0.00"),
        }

    for p in payments:
        if p.student_id not in students_data:
            continue
        payment_dt = datetime.combine(
            p.payment_date, datetime.min.time(), tzinfo=timezone.utc
        )
        sort_dt = (
            p.created_at
            if p.created_at.tzinfo
            else p.created_at.replace(tzinfo=timezone.utc)
        )
        students_data[p.student_id]["transactions"].append({
            "date": payment_dt,
            "sort_date": sort_dt,
            "type": "Payment",
            "description": f"Payment - {p.payment_method.upper()}",
            "reference": p.receipt_number or p.payment_number,
            "credit": p.amount,
            "debit": None,
        })
        students_data[p.student_id]["total_credits"] += p.amount

    for inv in invoices:
        if inv.student_id not in students_data:
            continue
        invoice_dt = datetime.combine(
            inv.issue_date, datetime.min.time(), tzinfo=timezone.utc
        )
        inv_sort_dt = (
            inv.created_at
            if inv.created_at.tzinfo
            else inv.created_at.replace(tzinfo=timezone.utc)
        )
        students_data[inv.student_id]["transactions"].append({
            "date": invoice_dt,
            "sort_date": inv_sort_dt,
            "type": "Invoice",
            "description": f"Invoice - {inv.invoice_type.replace('_', ' ').title()}",
            "reference": inv.invoice_number,
            "credit": None,
            "debit": inv.total,
        })
        students_data[inv.student_id]["total_debits"] += inv.total

    result = []
    for student_id, data in students_data.items():
        data["transactions"].sort(
            key=lambda x: (x["date"], x.get("sort_date", x["date"]))
        )

        running_balance = data["opening_balance"]
        for txn in data["transactions"]:
            if txn["debit"]:
                running_balance += txn["debit"]
            if txn["credit"]:
                running_balance -= txn["credit"]
            txn["running_balance"] = round_money(running_balance)

        data["closing_balance"] = round_money(running_balance)
        data["total_credits"] = round_money(data["total_credits"])
        data["total_debits"] = round_money(data["total_debits"])
        result.append(data)

    result.sort(key=lambda x: x["student_name"])
    return result


def build_student_balance_changes_csv(
    students_data: list[dict],
    date_from: date,
) -> str:
    """Build CSV content for student balance changes export with running balances."""
    out = StringIO()
    writer = csv.writer(out)

    # Header
    writer.writerow([
        "Student Number",
        "Student Name",
        "Grade",
        "Date",
        "Type",
        "Description",
        "Reference",
        "Credit",
        "Debit",
        "Running Balance",
    ])

    # Write data grouped by student
    for student_data in students_data:
        student_number = student_data["student_number"]
        student_name = student_data["student_name"]
        grade_name = student_data["grade_name"]
        opening_balance = student_data["opening_balance"]

        opening_dt = datetime.combine(
            date_from, datetime.min.time(), tzinfo=timezone.utc
        )
        writer.writerow([
            student_number,
            student_name,
            grade_name,
            opening_dt.isoformat(),
            "Opening Balance",
            "Balance at start of period",
            "",
            "",
            "",
            str(opening_balance),
        ])

        for txn in student_data["transactions"]:
            writer.writerow([
                student_number,
                student_name,
                grade_name,
                txn["date"].isoformat(),
                txn["type"],
                txn["description"],
                txn["reference"] or "",
                str(txn["credit"]) if txn["credit"] else "",
                str(txn["debit"]) if txn["debit"] else "",
                str(txn["running_balance"]),
            ])

        writer.writerow([])

    return out.getvalue()
