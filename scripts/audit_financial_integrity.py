#!/usr/bin/env python3
"""
Read-only audit for student financial integrity.

Scans students, invoices, invoice lines, payments, and credit allocations to find
data inconsistencies such as:

- student cached credit balance not matching completed payments - allocations
- student open debt by invoice headers not matching line remaining amounts
- invoice headers not matching line totals / line remaining amounts / allocations
- line formulas not matching (net, remaining)
- allocations linked to the wrong student / invoice / line

Usage examples:
    python3 scripts/audit_financial_integrity.py
    python3 scripts/audit_financial_integrity.py --student-number STU-2026-000001
    python3 scripts/audit_financial_integrity.py --json --fail-on-errors
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

# Add project root to PYTHONPATH.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.auth.models import User
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.inventory.models import Issuance, IssuanceItem, Stock, StockMovement
from src.modules.items.models import Category, Item, ItemVariant, ItemVariantMembership, Kit, KitItem
from src.modules.payments.models import CreditAllocation, Payment, PaymentStatus
from src.modules.reservations.models import Reservation, ReservationItem
from src.modules.students.models import Student
from src.modules.terms.models import Term, TransportZone
from src.shared.utils.money import round_money


OPEN_INVOICE_STATUSES = {
    InvoiceStatus.ISSUED.value,
    InvoiceStatus.PARTIALLY_PAID.value,
}


@dataclass
class AuditIssue:
    code: str
    severity: str
    message: str
    student_id: int | None = None
    student_number: str | None = None
    invoice_id: int | None = None
    invoice_number: str | None = None
    line_id: int | None = None
    allocation_id: int | None = None
    actual: str | None = None
    expected: str | None = None


@dataclass
class StudentSnapshot:
    student_id: int
    student_number: str
    full_name: str
    status: str
    cached_credit_balance: str
    computed_credit_balance: str
    open_due_headers: str
    open_due_lines: str
    issues: list[AuditIssue] = field(default_factory=list)


@dataclass
class AuditSummary:
    environment: str
    database: str
    students_scanned: int
    invoices_scanned: int
    lines_scanned: int
    payments_scanned: int
    completed_payments_scanned: int
    allocations_scanned: int
    students_with_issues: int
    total_issues: int
    issues_by_code: dict[str, int]


@dataclass
class AuditReport:
    summary: AuditSummary
    students: list[StudentSnapshot]


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def hostname_from_url(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except Exception:
        return None


def resolve_database_url(explicit_url: str | None) -> tuple[str, str]:
    candidate = explicit_url or os.getenv("DATABASE_URL") or settings.database_url
    candidate = normalize_database_url(candidate)

    hostname = hostname_from_url(candidate)
    public_url = os.getenv("DATABASE_PUBLIC_URL")
    if hostname and hostname.endswith(".railway.internal") and public_url:
        return normalize_database_url(public_url), "DATABASE_PUBLIC_URL"

    return candidate, "DATABASE_URL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit student financial integrity without modifying data."
    )
    parser.add_argument(
        "--database-url",
        help="Optional database URL override. If omitted, uses DATABASE_URL and falls back to DATABASE_PUBLIC_URL when needed for local Railway CLI runs.",
    )
    parser.add_argument(
        "--student-id",
        action="append",
        type=int,
        dest="student_ids",
        help="Audit only one student id. Repeat flag to pass multiple ids.",
    )
    parser.add_argument(
        "--student-number",
        action="append",
        dest="student_numbers",
        help="Audit only one student number. Repeat flag to pass multiple numbers.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of students to scan after filters.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit with code 1 when at least one issue is found.",
    )
    parser.add_argument(
        "--tolerance",
        type=Decimal,
        default=Decimal("0.05"),
        help="Money tolerance for mismatch checks (default: 0.05).",
    )
    parser.add_argument(
        "--max-issues-per-student",
        type=int,
        default=25,
        help="Cap text output per student to keep Railway logs readable.",
    )
    return parser.parse_args()


def as_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return round_money(value)
    return round_money(Decimal(str(value)))


def money_str(value: Any) -> str:
    return f"{as_money(value):,.2f}"


def value_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def format_issue_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (Decimal, float)):
        return money_str(value)
    return str(value)


def money_diff(left: Any, right: Any) -> Decimal:
    return abs(as_money(left) - as_money(right))


def money_mismatch(left: Any, right: Any, tolerance: Decimal) -> bool:
    return money_diff(left, right) > tolerance


def masked_database_url(url: str | None = None) -> str:
    effective_url = url or settings.database_url
    if "@" not in effective_url:
        return effective_url
    return f"...@{effective_url.split('@', 1)[1]}"


def issue_dict(issue: AuditIssue) -> dict[str, Any]:
    return {k: v for k, v in asdict(issue).items() if v is not None}


async def load_students(
    session: AsyncSession,
    student_ids: list[int] | None,
    student_numbers: list[str] | None,
    limit: int | None,
) -> list[Student]:
    query = select(Student).order_by(Student.id)

    filters = []
    if student_ids:
        filters.append(Student.id.in_(student_ids))
    if student_numbers:
        filters.append(Student.student_number.in_(student_numbers))
    if filters:
        query = query.where(or_(*filters))
    if limit:
        query = query.limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def scalar_count(session: AsyncSession, query) -> int:
    result = await session.execute(query)
    return int(result.scalar() or 0)


def add_issue(
    issues: list[AuditIssue],
    code: str,
    message: str,
    severity: str = "error",
    student: Student | None = None,
    invoice: Invoice | None = None,
    line: InvoiceLine | None = None,
    allocation_id: int | None = None,
    actual: Any | None = None,
    expected: Any | None = None,
) -> None:
    issues.append(
        AuditIssue(
            code=code,
            severity=severity,
            message=message,
            student_id=student.id if student else None,
            student_number=student.student_number if student else None,
            invoice_id=invoice.id if invoice else None,
            invoice_number=invoice.invoice_number if invoice else None,
            line_id=line.id if line else None,
            allocation_id=allocation_id,
            actual=format_issue_value(actual) if actual is not None else None,
            expected=format_issue_value(expected) if expected is not None else None,
        )
    )


async def build_report(
    session: AsyncSession,
    student_ids: list[int] | None,
    student_numbers: list[str] | None,
    limit: int | None,
    tolerance: Decimal,
    database_label: str,
) -> AuditReport:
    students = await load_students(session, student_ids, student_numbers, limit)
    if not students:
        summary = AuditSummary(
            environment=settings.app_env,
            database=database_label,
            students_scanned=0,
            invoices_scanned=0,
            lines_scanned=0,
            payments_scanned=0,
            completed_payments_scanned=0,
            allocations_scanned=0,
            students_with_issues=0,
            total_issues=0,
            issues_by_code={},
        )
        return AuditReport(summary=summary, students=[])

    scoped_student_ids = [student.id for student in students]
    payment_count = await scalar_count(
        session,
        select(func.count()).select_from(Payment).where(Payment.student_id.in_(scoped_student_ids)),
    )
    completed_payment_count = await scalar_count(
        session,
        select(func.count()).select_from(Payment).where(
            Payment.student_id.in_(scoped_student_ids),
            Payment.status == PaymentStatus.COMPLETED.value,
        ),
    )
    allocation_count = await scalar_count(
        session,
        select(func.count()).select_from(CreditAllocation).where(
            CreditAllocation.student_id.in_(scoped_student_ids)
        ),
    )

    payment_rows = await session.execute(
        select(
            Payment.student_id,
            func.coalesce(func.sum(Payment.amount), 0).label("completed_total"),
        )
        .where(
            Payment.student_id.in_(scoped_student_ids),
            Payment.status == PaymentStatus.COMPLETED.value,
        )
        .group_by(Payment.student_id)
    )
    completed_payments_by_student = {
        int(row.student_id): as_money(row.completed_total) for row in payment_rows.all()
    }

    allocation_rows = await session.execute(
        select(
            CreditAllocation.student_id,
            func.coalesce(func.sum(CreditAllocation.amount), 0).label("allocated_total"),
        )
        .where(CreditAllocation.student_id.in_(scoped_student_ids))
        .group_by(CreditAllocation.student_id)
    )
    allocations_by_student = {
        int(row.student_id): as_money(row.allocated_total) for row in allocation_rows.all()
    }

    invoices_result = await session.execute(
        select(Invoice)
        .where(Invoice.student_id.in_(scoped_student_ids))
        .options(selectinload(Invoice.lines))
        .order_by(Invoice.student_id, Invoice.created_at, Invoice.id)
    )
    invoices = list(invoices_result.scalars().all())
    invoices_by_student: dict[int, list[Invoice]] = defaultdict(list)
    for invoice in invoices:
        invoices_by_student[invoice.student_id].append(invoice)

    invoice_ids = [invoice.id for invoice in invoices]
    line_ids = [line.id for invoice in invoices for line in invoice.lines]

    invoice_alloc_sums: dict[int, Decimal] = {}
    if invoice_ids:
        invoice_alloc_rows = await session.execute(
            select(
                CreditAllocation.invoice_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0).label("allocated_total"),
            )
            .where(CreditAllocation.invoice_id.in_(invoice_ids))
            .group_by(CreditAllocation.invoice_id)
        )
        invoice_alloc_sums = {
            int(row.invoice_id): as_money(row.allocated_total) for row in invoice_alloc_rows.all()
        }

    line_alloc_sums: dict[int, Decimal] = {}
    if line_ids:
        line_alloc_rows = await session.execute(
            select(
                CreditAllocation.invoice_line_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0).label("allocated_total"),
            )
            .where(CreditAllocation.invoice_line_id.in_(line_ids))
            .group_by(CreditAllocation.invoice_line_id)
        )
        line_alloc_sums = {
            int(row.invoice_line_id): as_money(row.allocated_total)
            for row in line_alloc_rows.all()
            if row.invoice_line_id is not None
        }

    allocation_consistency_rows = await session.execute(
        select(
            CreditAllocation.id,
            CreditAllocation.student_id,
            CreditAllocation.invoice_id,
            CreditAllocation.invoice_line_id,
            CreditAllocation.amount,
            Invoice.student_id.label("invoice_student_id"),
            Invoice.invoice_number.label("invoice_number"),
            InvoiceLine.invoice_id.label("line_invoice_id"),
        )
        .select_from(CreditAllocation)
        .outerjoin(Invoice, CreditAllocation.invoice_id == Invoice.id)
        .outerjoin(InvoiceLine, CreditAllocation.invoice_line_id == InvoiceLine.id)
        .where(
            or_(
                CreditAllocation.student_id.in_(scoped_student_ids),
                Invoice.student_id.in_(scoped_student_ids),
            )
        )
    )
    allocation_consistency = allocation_consistency_rows.all()

    student_snapshots: list[StudentSnapshot] = []
    issues_by_code: Counter[str] = Counter()
    line_count = 0

    for student in students:
        issues: list[AuditIssue] = []

        completed_total = completed_payments_by_student.get(student.id, Decimal("0.00"))
        allocated_total = allocations_by_student.get(student.id, Decimal("0.00"))
        computed_credit = round_money(completed_total - allocated_total)
        cached_credit = as_money(student.cached_credit_balance)

        student_invoices = invoices_by_student.get(student.id, [])
        open_due_headers = round_money(
            sum(
                (as_money(invoice.amount_due) for invoice in student_invoices if invoice.status in OPEN_INVOICE_STATUSES),
                Decimal("0.00"),
            )
        )
        open_due_lines = round_money(
            sum(
                (
                    as_money(line.remaining_amount)
                    for invoice in student_invoices
                    if invoice.status in OPEN_INVOICE_STATUSES
                    for line in invoice.lines
                ),
                Decimal("0.00"),
            )
        )

        if money_mismatch(cached_credit, computed_credit, tolerance):
            add_issue(
                issues,
                code="student.cached_credit_balance_mismatch",
                message="Student cached credit balance does not match completed payments minus allocations.",
                student=student,
                actual=cached_credit,
                expected=computed_credit,
            )

        if money_mismatch(open_due_headers, open_due_lines, tolerance):
            add_issue(
                issues,
                code="student.open_due_headers_vs_lines_mismatch",
                message="Student open debt by invoice headers does not match sum of line remaining amounts.",
                student=student,
                actual=open_due_headers,
                expected=open_due_lines,
            )

        for invoice in student_invoices:
            line_count += len(invoice.lines)

            line_subtotal = round_money(
                sum((as_money(line.line_total) for line in invoice.lines), Decimal("0.00"))
            )
            line_discount_total = round_money(
                sum((as_money(line.discount_amount) for line in invoice.lines), Decimal("0.00"))
            )
            line_net_total = round_money(
                sum((as_money(line.net_amount) for line in invoice.lines), Decimal("0.00"))
            )
            line_paid_total = round_money(
                sum((as_money(line.paid_amount) for line in invoice.lines), Decimal("0.00"))
            )
            line_remaining_total = round_money(
                sum((as_money(line.remaining_amount) for line in invoice.lines), Decimal("0.00"))
            )
            alloc_total = invoice_alloc_sums.get(invoice.id, Decimal("0.00"))
            line_level_alloc_total = round_money(
                sum(
                    (
                        line_alloc_sums.get(line.id, Decimal("0.00"))
                        for line in invoice.lines
                    ),
                    Decimal("0.00"),
                )
            )

            expected_total_formula = round_money(as_money(invoice.subtotal) - as_money(invoice.discount_total))
            expected_due_formula = round_money(as_money(invoice.total) - as_money(invoice.paid_total))

            if money_mismatch(invoice.subtotal, line_subtotal, tolerance):
                add_issue(
                    issues,
                    code="invoice.subtotal_vs_lines_mismatch",
                    message="Invoice subtotal does not match sum of line totals.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.subtotal,
                    expected=line_subtotal,
                )

            if money_mismatch(invoice.discount_total, line_discount_total, tolerance):
                add_issue(
                    issues,
                    code="invoice.discount_total_vs_lines_mismatch",
                    message="Invoice discount_total does not match sum of line discounts.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.discount_total,
                    expected=line_discount_total,
                )

            if money_mismatch(invoice.total, expected_total_formula, tolerance):
                add_issue(
                    issues,
                    code="invoice.total_formula_mismatch",
                    message="Invoice total does not match subtotal - discount_total.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.total,
                    expected=expected_total_formula,
                )

            if money_mismatch(invoice.total, line_net_total, tolerance):
                add_issue(
                    issues,
                    code="invoice.total_vs_line_net_mismatch",
                    message="Invoice total does not match sum of line net_amount values.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.total,
                    expected=line_net_total,
                )

            if money_mismatch(invoice.paid_total, alloc_total, tolerance):
                add_issue(
                    issues,
                    code="invoice.paid_total_vs_allocations_mismatch",
                    message="Invoice paid_total does not match sum of allocations linked to the invoice.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.paid_total,
                    expected=alloc_total,
                )

            if money_mismatch(invoice.paid_total, line_paid_total, tolerance):
                add_issue(
                    issues,
                    code="invoice.paid_total_vs_line_paid_mismatch",
                    message="Invoice paid_total does not match sum of line paid_amount values.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.paid_total,
                    expected=line_paid_total,
                )

            if money_mismatch(invoice.amount_due, expected_due_formula, tolerance):
                add_issue(
                    issues,
                    code="invoice.amount_due_formula_mismatch",
                    message="Invoice amount_due does not match total - paid_total.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.amount_due,
                    expected=expected_due_formula,
                )

            if money_mismatch(invoice.amount_due, line_remaining_total, tolerance):
                add_issue(
                    issues,
                    code="invoice.amount_due_vs_line_remaining_mismatch",
                    message="Invoice amount_due does not match sum of line remaining_amount values.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.amount_due,
                    expected=line_remaining_total,
                )

            if as_money(invoice.paid_total) > as_money(invoice.total) + tolerance:
                add_issue(
                    issues,
                    code="invoice.paid_total_exceeds_total",
                    message="Invoice paid_total exceeds invoice total.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.paid_total,
                    expected=invoice.total,
                )

            if as_money(invoice.amount_due) < Decimal("0.00") - tolerance:
                add_issue(
                    issues,
                    code="invoice.amount_due_negative",
                    message="Invoice amount_due is negative.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.amount_due,
                    expected=Decimal("0.00"),
                )

            if invoice.status == InvoiceStatus.PAID.value and money_mismatch(invoice.amount_due, Decimal("0.00"), tolerance):
                add_issue(
                    issues,
                    code="invoice.status_paid_but_due_not_zero",
                    message="Invoice status is PAID but amount_due is not zero.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.amount_due,
                    expected=Decimal("0.00"),
                )

            if invoice.status == InvoiceStatus.ISSUED.value and money_mismatch(invoice.paid_total, Decimal("0.00"), tolerance):
                add_issue(
                    issues,
                    code="invoice.status_issued_but_paid_total_nonzero",
                    message="Invoice status is ISSUED but paid_total is not zero.",
                    student=student,
                    invoice=invoice,
                    actual=invoice.paid_total,
                    expected=Decimal("0.00"),
                )

            if invoice.status == InvoiceStatus.PARTIALLY_PAID.value:
                if as_money(invoice.paid_total) <= Decimal("0.00") + tolerance:
                    add_issue(
                        issues,
                        code="invoice.status_partial_but_paid_total_zero",
                        message="Invoice status is PARTIALLY_PAID but paid_total is zero.",
                        student=student,
                        invoice=invoice,
                        actual=invoice.paid_total,
                        expected=Decimal("0.01"),
                    )
                if as_money(invoice.amount_due) <= Decimal("0.00") + tolerance:
                    add_issue(
                        issues,
                        code="invoice.status_partial_but_due_zero",
                        message="Invoice status is PARTIALLY_PAID but amount_due is zero.",
                        student=student,
                        invoice=invoice,
                        actual=invoice.amount_due,
                        expected=Decimal("0.01"),
                    )

            if invoice.status == InvoiceStatus.DRAFT.value and alloc_total > tolerance:
                add_issue(
                    issues,
                    code="invoice.draft_with_allocations",
                    message="Draft invoice has allocations linked to it.",
                    student=student,
                    invoice=invoice,
                    actual=alloc_total,
                    expected=Decimal("0.00"),
                )

            if invoice.status in {InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value} and alloc_total > tolerance:
                add_issue(
                    issues,
                    code="invoice.cancelled_or_void_with_allocations",
                    message="Cancelled or void invoice still has allocations linked to it.",
                    student=student,
                    invoice=invoice,
                    actual=alloc_total,
                    expected=Decimal("0.00"),
                )

            if line_level_alloc_total > alloc_total + tolerance:
                add_issue(
                    issues,
                    code="invoice.line_allocations_exceed_invoice_allocations",
                    message="Sum of line-level allocations exceeds invoice-level allocation total.",
                    student=student,
                    invoice=invoice,
                    actual=line_level_alloc_total,
                    expected=alloc_total,
                )

            all_allocations_line_level = bool(invoice.lines) and line_level_alloc_total > tolerance and not money_mismatch(
                line_level_alloc_total,
                alloc_total,
                tolerance,
            )

            for line in invoice.lines:
                expected_net = round_money(as_money(line.line_total) - as_money(line.discount_amount))
                expected_remaining = round_money(as_money(line.net_amount) - as_money(line.paid_amount))
                alloc_line_total = line_alloc_sums.get(line.id, Decimal("0.00"))

                if money_mismatch(line.net_amount, expected_net, tolerance):
                    add_issue(
                        issues,
                        code="line.net_amount_formula_mismatch",
                        message="Invoice line net_amount does not match line_total - discount_amount.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=line.net_amount,
                        expected=expected_net,
                    )

                if money_mismatch(line.remaining_amount, expected_remaining, tolerance):
                    add_issue(
                        issues,
                        code="line.remaining_amount_formula_mismatch",
                        message="Invoice line remaining_amount does not match net_amount - paid_amount.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=line.remaining_amount,
                        expected=expected_remaining,
                    )

                if as_money(line.discount_amount) > as_money(line.line_total) + tolerance:
                    add_issue(
                        issues,
                        code="line.discount_exceeds_line_total",
                        message="Invoice line discount exceeds line total.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=line.discount_amount,
                        expected=line.line_total,
                    )

                if as_money(line.paid_amount) > as_money(line.net_amount) + tolerance:
                    add_issue(
                        issues,
                        code="line.paid_amount_exceeds_net_amount",
                        message="Invoice line paid_amount exceeds line net_amount.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=line.paid_amount,
                        expected=line.net_amount,
                    )

                if as_money(line.remaining_amount) < Decimal("0.00") - tolerance:
                    add_issue(
                        issues,
                        code="line.remaining_amount_negative",
                        message="Invoice line remaining_amount is negative.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=line.remaining_amount,
                        expected=Decimal("0.00"),
                    )

                if alloc_line_total > as_money(line.net_amount) + tolerance:
                    add_issue(
                        issues,
                        code="line.allocations_exceed_net_amount",
                        message="Line-level allocations exceed line net_amount.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=alloc_line_total,
                        expected=line.net_amount,
                    )

                if all_allocations_line_level and money_mismatch(line.paid_amount, alloc_line_total, tolerance):
                    add_issue(
                        issues,
                        code="line.paid_amount_vs_line_allocations_mismatch",
                        message="Line paid_amount does not match line-level allocations.",
                        student=student,
                        invoice=invoice,
                        line=line,
                        actual=line.paid_amount,
                        expected=alloc_line_total,
                    )

        for row in allocation_consistency:
            visible_for_student = {int(row.student_id)}
            if row.invoice_student_id is not None:
                visible_for_student.add(int(row.invoice_student_id))
            if student.id not in visible_for_student:
                continue

            linked_invoice = None
            if row.invoice_id is not None and row.invoice_id in invoice_alloc_sums:
                linked_invoice = next((inv for inv in student_invoices if inv.id == int(row.invoice_id)), None)

            if row.invoice_student_id is None:
                add_issue(
                    issues,
                    code="allocation.invoice_missing",
                    message="Allocation points to a missing invoice.",
                    student=student,
                    allocation_id=int(row.id),
                    actual=row.amount,
                    expected=Decimal("0.00"),
                )
                continue

            if int(row.invoice_student_id) != int(row.student_id):
                add_issue(
                    issues,
                    code="allocation.student_vs_invoice_student_mismatch",
                    message="Allocation student_id does not match invoice.student_id.",
                    student=student,
                    invoice=linked_invoice,
                    allocation_id=int(row.id),
                    actual=value_str(row.student_id),
                    expected=value_str(row.invoice_student_id),
                )

            if row.invoice_line_id is not None and row.line_invoice_id is None:
                add_issue(
                    issues,
                    code="allocation.invoice_line_missing",
                    message="Allocation points to a missing invoice line.",
                    student=student,
                    invoice=linked_invoice,
                    allocation_id=int(row.id),
                )
                continue

            if row.invoice_line_id is not None and int(row.line_invoice_id) != int(row.invoice_id):
                add_issue(
                    issues,
                    code="allocation.invoice_line_vs_invoice_mismatch",
                    message="Allocation invoice_line_id belongs to a different invoice.",
                    student=student,
                    invoice=linked_invoice,
                    allocation_id=int(row.id),
                    actual=value_str(row.invoice_id),
                    expected=value_str(row.line_invoice_id),
                )

        issues_by_code.update(issue.code for issue in issues)
        student_snapshots.append(
            StudentSnapshot(
                student_id=student.id,
                student_number=student.student_number,
                full_name=student.full_name,
                status=student.status,
                cached_credit_balance=money_str(cached_credit),
                computed_credit_balance=money_str(computed_credit),
                open_due_headers=money_str(open_due_headers),
                open_due_lines=money_str(open_due_lines),
                issues=issues,
            )
        )

    students_with_issues = [snapshot for snapshot in student_snapshots if snapshot.issues]
    students_with_issues.sort(key=lambda snapshot: (-len(snapshot.issues), snapshot.student_id))

    summary = AuditSummary(
        environment=settings.app_env,
        database=database_label,
        students_scanned=len(students),
        invoices_scanned=len(invoices),
        lines_scanned=line_count,
        payments_scanned=payment_count,
        completed_payments_scanned=completed_payment_count,
        allocations_scanned=allocation_count,
        students_with_issues=len(students_with_issues),
        total_issues=sum(len(snapshot.issues) for snapshot in students_with_issues),
        issues_by_code=dict(sorted(issues_by_code.items())),
    )
    return AuditReport(summary=summary, students=students_with_issues)


def print_text_report(report: AuditReport, max_issues_per_student: int) -> None:
    summary = report.summary

    print("=" * 78)
    print("FINANCIAL INTEGRITY AUDIT")
    print("=" * 78)
    print(f"Environment: {summary.environment}")
    print(f"Database:    {summary.database}")
    print(f"Students:    {summary.students_scanned}")
    print(f"Invoices:    {summary.invoices_scanned}")
    print(f"Lines:       {summary.lines_scanned}")
    print(f"Payments:    {summary.payments_scanned} total / {summary.completed_payments_scanned} completed")
    print(f"Allocations: {summary.allocations_scanned}")
    print(f"Issues:      {summary.total_issues} across {summary.students_with_issues} students")

    if summary.issues_by_code:
        print("\nIssue counts:")
        for code, count in summary.issues_by_code.items():
            print(f"  - {code}: {count}")

    if not report.students:
        print("\nNo issues found.")
        return

    print("\nStudents with issues:")
    for snapshot in report.students:
        print(
            f"\n[{snapshot.student_id}] {snapshot.student_number} · {snapshot.full_name} "
            f"({snapshot.status})"
        )
        print(
            "  Credit: cached="
            f"{snapshot.cached_credit_balance}, computed={snapshot.computed_credit_balance}"
        )
        print(
            "  Open due: headers="
            f"{snapshot.open_due_headers}, lines={snapshot.open_due_lines}"
        )

        visible_issues = snapshot.issues[:max_issues_per_student]
        hidden_count = len(snapshot.issues) - len(visible_issues)
        for issue in visible_issues:
            ref_parts = []
            if issue.invoice_number:
                ref_parts.append(issue.invoice_number)
            elif issue.invoice_id is not None:
                ref_parts.append(f"invoice_id={issue.invoice_id}")
            if issue.line_id is not None:
                ref_parts.append(f"line_id={issue.line_id}")
            if issue.allocation_id is not None:
                ref_parts.append(f"allocation_id={issue.allocation_id}")
            ref = f" [{' / '.join(ref_parts)}]" if ref_parts else ""
            details = []
            if issue.actual is not None:
                details.append(f"actual={issue.actual}")
            if issue.expected is not None:
                details.append(f"expected={issue.expected}")
            detail_suffix = f" ({', '.join(details)})" if details else ""
            print(f"  - {issue.code}{ref}: {issue.message}{detail_suffix}")
        if hidden_count > 0:
            print(f"  ... {hidden_count} more issue(s) omitted")


def print_json_report(report: AuditReport) -> None:
    payload = {
        "summary": asdict(report.summary),
        "students": [
            {
                **{
                    k: v
                    for k, v in asdict(snapshot).items()
                    if k != "issues"
                },
                "issues": [issue_dict(issue) for issue in snapshot.issues],
            }
            for snapshot in report.students
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


async def main() -> int:
    args = parse_args()
    database_url, url_source = resolve_database_url(args.database_url)
    engine = create_async_engine(
        database_url,
        echo=settings.debug,
        future=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    print(
        f"[audit] Environment={settings.app_env} Database={masked_database_url(database_url)} Source={url_source}",
        file=sys.stderr,
    )

    try:
        async with session_factory() as session:
            report = await build_report(
                session=session,
                student_ids=args.student_ids,
                student_numbers=args.student_numbers,
                limit=args.limit,
                tolerance=args.tolerance,
                database_label=masked_database_url(database_url),
            )
    finally:
        await engine.dispose()

    if args.json:
        print_json_report(report)
    else:
        print_text_report(report, max_issues_per_student=args.max_issues_per_student)

    if args.fail_on_errors and report.summary.total_issues > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
