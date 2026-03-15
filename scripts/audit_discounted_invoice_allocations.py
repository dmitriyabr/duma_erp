#!/usr/bin/env python3
"""
Read-only audit for invoices where discounts were applied after allocations existed.

This focuses on the historical risk window before excess allocations started being
auto-deallocated and immediately auto-reallocated after invoice discounts.

It uses audit logs to find invoices touched by:

- discount.apply
- invoice.update_line_discount

For each matching invoice it reports:

- discount events that happened after the first allocation on that invoice
- current over-allocation against invoice total / line net amounts
- stale invoice/line aggregates that usually indicate missed deallocation

Usage examples:
    python3 scripts/audit_discounted_invoice_allocations.py
    python3 scripts/audit_discounted_invoice_allocations.py --event-date-to 2026-03-14
    python3 scripts/audit_discounted_invoice_allocations.py --student-number STU-2026-000014
    railway run python3 scripts/audit_discounted_invoice_allocations.py --json --fail-on-findings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

# Add project root to PYTHONPATH.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import Date as SqlDate
from sqlalchemy import and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.core.audit.models import AuditLog
from src.core.auth.models import User
from src.core.config import settings
from src.modules.discounts.models import Discount
from src.modules.inventory.models import Issuance, IssuanceItem, Stock, StockMovement
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.items.models import Category, Item, ItemVariant, ItemVariantMembership, Kit, KitItem
from src.modules.payments.models import CreditAllocation, Payment
from src.modules.reservations.models import Reservation, ReservationItem
from src.modules.students.models import Student
from src.modules.terms.models import Term, TransportZone
from src.shared.utils.money import round_money


@dataclass
class DiscountEventSnapshot:
    action: str
    created_at: str
    user_id: int | None
    source_line_id: int | None = None


@dataclass
class DiscountAuditIssue:
    code: str
    severity: str
    message: str
    actual: str | None = None
    expected: str | None = None


@dataclass
class InvoiceSnapshot:
    invoice_id: int
    invoice_number: str
    student_id: int
    student_number: str
    student_name: str
    status: str
    total: str
    paid_total: str
    amount_due: str
    allocation_total: str
    first_allocation_at: str | None
    discount_events: list[DiscountEventSnapshot]
    issues: list[DiscountAuditIssue] = field(default_factory=list)


@dataclass
class DiscountAuditSummary:
    environment: str
    database: str
    candidate_invoices: int
    invoices_reported: int
    invoices_with_post_allocation_discount_events: int
    invoices_with_errors: int
    total_discount_events: int
    total_findings: int
    findings_by_code: dict[str, int]


@dataclass
class DiscountAuditReport:
    summary: DiscountAuditSummary
    invoices: list[InvoiceSnapshot]


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


def parse_date_arg(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{raw}'. Expected YYYY-MM-DD."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit historically risky invoice discounts that happened after allocations."
    )
    parser.add_argument(
        "--database-url",
        help="Optional database URL override. Falls back to DATABASE_PUBLIC_URL when Railway CLI injects a private host locally.",
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
        "--invoice-id",
        action="append",
        type=int,
        dest="invoice_ids",
        help="Audit only one invoice id. Repeat flag to pass multiple ids.",
    )
    parser.add_argument(
        "--invoice-number",
        action="append",
        dest="invoice_numbers",
        help="Audit only one invoice number. Repeat flag to pass multiple numbers.",
    )
    parser.add_argument(
        "--event-date-from",
        type=parse_date_arg,
        help="Include only discount events on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--event-date-to",
        type=parse_date_arg,
        help="Include only discount events on or before this date (YYYY-MM-DD). Useful for the pre-fix window.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of candidate invoices to inspect after filters.",
    )
    parser.add_argument(
        "--only-errors",
        action="store_true",
        help="Suppress warning-only invoices and print only invoices with current breakage.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with code 1 when at least one reported finding is present.",
    )
    parser.add_argument(
        "--tolerance",
        type=Decimal,
        default=Decimal("0.05"),
        help="Money tolerance for mismatch checks (default: 0.05).",
    )
    parser.add_argument(
        "--max-issues-per-invoice",
        type=int,
        default=20,
        help="Cap text output per invoice to keep Railway logs readable.",
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


def format_issue_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (Decimal, float)):
        return money_str(value)
    if isinstance(value, datetime):
        return value.isoformat()
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


def issue_dict(issue: DiscountAuditIssue) -> dict[str, Any]:
    return {k: v for k, v in asdict(issue).items() if v is not None}


def event_dict(event: DiscountEventSnapshot) -> dict[str, Any]:
    return {k: v for k, v in asdict(event).items() if v is not None}


def add_issue(
    issues: list[DiscountAuditIssue],
    code: str,
    message: str,
    severity: str = "error",
    actual: Any | None = None,
    expected: Any | None = None,
) -> None:
    issues.append(
        DiscountAuditIssue(
            code=code,
            severity=severity,
            message=message,
            actual=format_issue_value(actual) if actual is not None else None,
            expected=format_issue_value(expected) if expected is not None else None,
        )
    )


async def load_students(
    session: AsyncSession,
    student_ids: list[int] | None,
    student_numbers: list[str] | None,
) -> list[Student]:
    query = select(Student).order_by(Student.id)

    filters = []
    if student_ids:
        filters.append(Student.id.in_(student_ids))
    if student_numbers:
        filters.append(Student.student_number.in_(student_numbers))
    if filters:
        query = query.where(or_(*filters))

    result = await session.execute(query)
    return list(result.scalars().all())


async def load_invoice_scope_ids(
    session: AsyncSession,
    invoice_ids: list[int] | None,
    invoice_numbers: list[str] | None,
) -> set[int] | None:
    if not invoice_ids and not invoice_numbers:
        return None

    query = select(Invoice.id)
    filters = []
    if invoice_ids:
        filters.append(Invoice.id.in_(invoice_ids))
    if invoice_numbers:
        filters.append(Invoice.invoice_number.in_(invoice_numbers))
    query = query.where(or_(*filters))

    result = await session.execute(query)
    return {int(row[0]) for row in result.all()}


async def load_discount_events(
    session: AsyncSession,
    scoped_student_ids: set[int] | None,
    scoped_invoice_ids: set[int] | None,
    event_date_from: date | None,
    event_date_to: date | None,
) -> dict[int, list[DiscountEventSnapshot]]:
    events_by_invoice: dict[int, list[DiscountEventSnapshot]] = defaultdict(list)

    discount_apply_query = (
        select(
            AuditLog.created_at,
            AuditLog.user_id,
            AuditLog.action,
            Invoice.id.label("invoice_id"),
            Discount.invoice_line_id.label("line_id"),
        )
        .select_from(AuditLog)
        .join(
            Discount,
            and_(
                AuditLog.entity_type == "Discount",
                AuditLog.entity_id == Discount.id,
            ),
        )
        .join(InvoiceLine, Discount.invoice_line_id == InvoiceLine.id)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .where(AuditLog.action == "discount.apply")
    )

    update_line_discount_query = (
        select(
            AuditLog.created_at,
            AuditLog.user_id,
            AuditLog.action,
            Invoice.id.label("invoice_id"),
            literal(None).label("line_id"),
        )
        .select_from(AuditLog)
        .join(
            Invoice,
            and_(
                AuditLog.entity_type == "Invoice",
                AuditLog.entity_id == Invoice.id,
            ),
        )
        .where(AuditLog.action == "invoice.update_line_discount")
    )

    for query in (discount_apply_query, update_line_discount_query):
        if scoped_student_ids is not None:
            query = query.where(Invoice.student_id.in_(scoped_student_ids))
        if scoped_invoice_ids is not None:
            query = query.where(Invoice.id.in_(scoped_invoice_ids))
        if event_date_from is not None:
            query = query.where(cast(AuditLog.created_at, SqlDate) >= event_date_from)
        if event_date_to is not None:
            query = query.where(cast(AuditLog.created_at, SqlDate) <= event_date_to)

        result = await session.execute(query)
        for row in result.all():
            events_by_invoice[int(row.invoice_id)].append(
                DiscountEventSnapshot(
                    action=row.action,
                    created_at=row.created_at.isoformat(),
                    user_id=row.user_id,
                    source_line_id=int(row.line_id) if row.line_id is not None else None,
                )
            )

    for invoice_events in events_by_invoice.values():
        invoice_events.sort(key=lambda event: event.created_at)

    return events_by_invoice


async def build_report(
    session: AsyncSession,
    *,
    student_ids: list[int] | None,
    student_numbers: list[str] | None,
    invoice_ids: list[int] | None,
    invoice_numbers: list[str] | None,
    event_date_from: date | None,
    event_date_to: date | None,
    limit: int | None,
    tolerance: Decimal,
    only_errors: bool,
    database_label: str,
) -> DiscountAuditReport:
    students: list[Student] = []
    scoped_student_ids: set[int] | None = None
    if student_ids or student_numbers:
        students = await load_students(session, student_ids, student_numbers)
        scoped_student_ids = {student.id for student in students}
    if (student_ids or student_numbers) and not scoped_student_ids:
        summary = DiscountAuditSummary(
            environment=settings.app_env,
            database=database_label,
            candidate_invoices=0,
            invoices_reported=0,
            invoices_with_post_allocation_discount_events=0,
            invoices_with_errors=0,
            total_discount_events=0,
            total_findings=0,
            findings_by_code={},
        )
        return DiscountAuditReport(summary=summary, invoices=[])

    scoped_invoice_ids = await load_invoice_scope_ids(
        session,
        invoice_ids=invoice_ids,
        invoice_numbers=invoice_numbers,
    )
    if (invoice_ids or invoice_numbers) and not scoped_invoice_ids:
        summary = DiscountAuditSummary(
            environment=settings.app_env,
            database=database_label,
            candidate_invoices=0,
            invoices_reported=0,
            invoices_with_post_allocation_discount_events=0,
            invoices_with_errors=0,
            total_discount_events=0,
            total_findings=0,
            findings_by_code={},
        )
        return DiscountAuditReport(summary=summary, invoices=[])

    events_by_invoice = await load_discount_events(
        session,
        scoped_student_ids=scoped_student_ids,
        scoped_invoice_ids=scoped_invoice_ids,
        event_date_from=event_date_from,
        event_date_to=event_date_to,
    )
    candidate_invoice_ids = sorted(events_by_invoice.keys())
    if limit:
        candidate_invoice_ids = candidate_invoice_ids[:limit]
        allowed = set(candidate_invoice_ids)
        events_by_invoice = {
            invoice_id: events
            for invoice_id, events in events_by_invoice.items()
            if invoice_id in allowed
        }

    if not candidate_invoice_ids:
        summary = DiscountAuditSummary(
            environment=settings.app_env,
            database=database_label,
            candidate_invoices=0,
            invoices_reported=0,
            invoices_with_post_allocation_discount_events=0,
            invoices_with_errors=0,
            total_discount_events=0,
            total_findings=0,
            findings_by_code={},
        )
        return DiscountAuditReport(summary=summary, invoices=[])

    invoices_result = await session.execute(
        select(Invoice)
        .where(Invoice.id.in_(candidate_invoice_ids))
        .options(
            selectinload(Invoice.student),
            selectinload(Invoice.lines),
        )
        .order_by(Invoice.student_id, Invoice.created_at, Invoice.id)
    )
    invoices = list(invoices_result.scalars().all())

    line_ids = [line.id for invoice in invoices for line in invoice.lines]

    invoice_alloc_rows = await session.execute(
        select(
            CreditAllocation.invoice_id,
            func.coalesce(func.sum(CreditAllocation.amount), 0).label("allocated_total"),
            func.min(CreditAllocation.created_at).label("first_allocation_at"),
        )
        .where(CreditAllocation.invoice_id.in_(candidate_invoice_ids))
        .group_by(CreditAllocation.invoice_id)
    )
    invoice_alloc_meta = {
        int(row.invoice_id): {
            "allocated_total": as_money(row.allocated_total),
            "first_allocation_at": row.first_allocation_at,
        }
        for row in invoice_alloc_rows.all()
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

    reported_invoices: list[InvoiceSnapshot] = []
    findings_counter: Counter[str] = Counter()
    invoices_with_post_allocation_events = 0
    invoices_with_errors = 0

    for invoice in invoices:
        events = events_by_invoice.get(invoice.id, [])
        issues: list[DiscountAuditIssue] = []

        alloc_meta = invoice_alloc_meta.get(
            invoice.id,
            {
                "allocated_total": Decimal("0.00"),
                "first_allocation_at": None,
            },
        )
        alloc_total = as_money(alloc_meta["allocated_total"])
        first_allocation_at = alloc_meta["first_allocation_at"]

        line_net_total = round_money(
            sum((as_money(line.net_amount) for line in invoice.lines), Decimal("0.00"))
        )
        line_paid_total = round_money(
            sum((as_money(line.paid_amount) for line in invoice.lines), Decimal("0.00"))
        )
        line_remaining_total = round_money(
            sum((as_money(line.remaining_amount) for line in invoice.lines), Decimal("0.00"))
        )

        post_allocation_events = []
        if first_allocation_at is not None:
            for event in events:
                if datetime.fromisoformat(event.created_at) > first_allocation_at:
                    post_allocation_events.append(event)
            if post_allocation_events:
                invoices_with_post_allocation_events += 1
                add_issue(
                    issues,
                    code="invoice.discount_event_after_allocation",
                    severity="warning",
                    message="At least one discount event happened after allocations already existed on this invoice.",
                    actual=post_allocation_events[0].created_at,
                    expected=first_allocation_at,
                )

        if alloc_total > as_money(invoice.total) + tolerance:
            add_issue(
                issues,
                code="invoice.allocations_exceed_total",
                severity="error",
                message="Current allocations linked to the invoice exceed the discounted invoice total.",
                actual=alloc_total,
                expected=invoice.total,
            )

        if alloc_total > line_net_total + tolerance:
            add_issue(
                issues,
                code="invoice.allocations_exceed_line_net_total",
                severity="error",
                message="Current allocations exceed the sum of line net amounts.",
                actual=alloc_total,
                expected=line_net_total,
            )

        if as_money(invoice.paid_total) > as_money(invoice.total) + tolerance:
            add_issue(
                issues,
                code="invoice.paid_total_exceeds_total",
                severity="error",
                message="Invoice paid_total exceeds invoice total.",
                actual=invoice.paid_total,
                expected=invoice.total,
            )

        if as_money(invoice.amount_due) < Decimal("0.00") - tolerance:
            add_issue(
                issues,
                code="invoice.amount_due_negative",
                severity="error",
                message="Invoice amount_due is negative.",
                actual=invoice.amount_due,
                expected=Decimal("0.00"),
            )

        if money_mismatch(invoice.paid_total, alloc_total, tolerance):
            add_issue(
                issues,
                code="invoice.paid_total_vs_allocations_mismatch",
                severity="error",
                message="Invoice paid_total does not match sum of allocations linked to the invoice.",
                actual=invoice.paid_total,
                expected=alloc_total,
            )

        if money_mismatch(invoice.paid_total, line_paid_total, tolerance):
            add_issue(
                issues,
                code="invoice.paid_total_vs_line_paid_mismatch",
                severity="error",
                message="Invoice paid_total does not match sum of line paid_amount values.",
                actual=invoice.paid_total,
                expected=line_paid_total,
            )

        expected_due = round_money(as_money(invoice.total) - as_money(invoice.paid_total))
        if money_mismatch(invoice.amount_due, expected_due, tolerance):
            add_issue(
                issues,
                code="invoice.amount_due_formula_mismatch",
                severity="error",
                message="Invoice amount_due does not match total - paid_total.",
                actual=invoice.amount_due,
                expected=expected_due,
            )

        if money_mismatch(invoice.amount_due, line_remaining_total, tolerance):
            add_issue(
                issues,
                code="invoice.amount_due_vs_line_remaining_mismatch",
                severity="error",
                message="Invoice amount_due does not match sum of line remaining_amount values.",
                actual=invoice.amount_due,
                expected=line_remaining_total,
            )

        for line in invoice.lines:
            explicit_alloc_total = line_alloc_sums.get(line.id, Decimal("0.00"))

            if explicit_alloc_total > as_money(line.net_amount) + tolerance:
                add_issue(
                    issues,
                    code="line.explicit_allocations_exceed_net",
                    severity="error",
                    message="Line-level allocations exceed the current line net_amount.",
                    actual=explicit_alloc_total,
                    expected=line.net_amount,
                )

            if as_money(line.paid_amount) > as_money(line.net_amount) + tolerance:
                add_issue(
                    issues,
                    code="line.paid_amount_exceeds_net",
                    severity="error",
                    message="Invoice line paid_amount exceeds net_amount.",
                    actual=line.paid_amount,
                    expected=line.net_amount,
                )

            expected_remaining = round_money(
                as_money(line.net_amount) - as_money(line.paid_amount)
            )
            if money_mismatch(line.remaining_amount, expected_remaining, tolerance):
                add_issue(
                    issues,
                    code="line.remaining_amount_formula_mismatch",
                    severity="error",
                    message="Invoice line remaining_amount does not match net_amount - paid_amount.",
                    actual=line.remaining_amount,
                    expected=expected_remaining,
                )

            if as_money(line.remaining_amount) < Decimal("0.00") - tolerance:
                add_issue(
                    issues,
                    code="line.remaining_amount_negative",
                    severity="error",
                    message="Invoice line remaining_amount is negative.",
                    actual=line.remaining_amount,
                    expected=Decimal("0.00"),
                )

        has_errors = any(issue.severity == "error" for issue in issues)
        if only_errors and not has_errors:
            continue
        if not issues:
            continue

        if has_errors:
            invoices_with_errors += 1

        for issue in issues:
            findings_counter[issue.code] += 1

        reported_invoices.append(
            InvoiceSnapshot(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                student_id=invoice.student_id,
                student_number=invoice.student.student_number if invoice.student else "",
                student_name=(
                    f"{invoice.student.first_name} {invoice.student.last_name}".strip()
                    if invoice.student
                    else ""
                ),
                status=invoice.status,
                total=money_str(invoice.total),
                paid_total=money_str(invoice.paid_total),
                amount_due=money_str(invoice.amount_due),
                allocation_total=money_str(alloc_total),
                first_allocation_at=first_allocation_at.isoformat()
                if first_allocation_at is not None
                else None,
                discount_events=events,
                issues=issues,
            )
        )

    total_discount_events = sum(len(events) for events in events_by_invoice.values())
    summary = DiscountAuditSummary(
        environment=settings.app_env,
        database=database_label,
        candidate_invoices=len(candidate_invoice_ids),
        invoices_reported=len(reported_invoices),
        invoices_with_post_allocation_discount_events=invoices_with_post_allocation_events,
        invoices_with_errors=invoices_with_errors,
        total_discount_events=total_discount_events,
        total_findings=sum(findings_counter.values()),
        findings_by_code=dict(sorted(findings_counter.items())),
    )
    return DiscountAuditReport(summary=summary, invoices=reported_invoices)


def print_text_report(report: DiscountAuditReport, max_issues_per_invoice: int) -> None:
    summary = report.summary
    print(
        "[discount-audit] "
        f"Environment={summary.environment} "
        f"Database={summary.database}"
    )
    print(
        "[discount-audit] "
        f"Candidates={summary.candidate_invoices} "
        f"Reported={summary.invoices_reported} "
        f"Risky={summary.invoices_with_post_allocation_discount_events} "
        f"Broken={summary.invoices_with_errors} "
        f"Findings={summary.total_findings}"
    )

    if not report.invoices:
        print("No discounted invoices with matching findings in the selected scope.")
        return

    for snapshot in report.invoices:
        print()
        print(
            f"[INV] {snapshot.invoice_number} · {snapshot.student_number} · "
            f"{snapshot.student_name} ({snapshot.status})"
        )
        print(
            f"  Totals: total={snapshot.total}, paid={snapshot.paid_total}, "
            f"due={snapshot.amount_due}, allocations={snapshot.allocation_total}"
        )
        if snapshot.first_allocation_at:
            print(f"  First allocation: {snapshot.first_allocation_at}")
        print(f"  Discount events: {len(snapshot.discount_events)}")
        for event in snapshot.discount_events[:5]:
            suffix = f" line_id={event.source_line_id}" if event.source_line_id else ""
            print(f"    - {event.created_at} · {event.action}{suffix}")
        if len(snapshot.discount_events) > 5:
            print(f"    - ... {len(snapshot.discount_events) - 5} more")

        for issue in snapshot.issues[:max_issues_per_invoice]:
            line = f"  - {issue.code}: {issue.message}"
            if issue.actual is not None or issue.expected is not None:
                line += f" (actual={issue.actual or ''}, expected={issue.expected or ''})"
            print(line)
        hidden = len(snapshot.issues) - max_issues_per_invoice
        if hidden > 0:
            print(f"  - ... {hidden} more issues suppressed")


def report_to_json(report: DiscountAuditReport) -> str:
    payload = {
        "summary": asdict(report.summary),
        "invoices": [
            {
                **{
                    key: value
                    for key, value in asdict(snapshot).items()
                    if key not in {"issues", "discount_events"}
                },
                "discount_events": [event_dict(event) for event in snapshot.discount_events],
                "issues": [issue_dict(issue) for issue in snapshot.issues],
            }
            for snapshot in report.invoices
        ],
    }
    return json.dumps(payload, indent=2)


async def main() -> int:
    args = parse_args()
    db_url, db_source = resolve_database_url(args.database_url)
    database_label = masked_database_url(db_url)
    print(
        f"[discount-audit] Environment={settings.app_env} "
        f"Database={database_label} Source={db_source}",
        file=sys.stderr if args.json else sys.stdout,
    )

    engine = create_async_engine(db_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with session_factory() as session:
            report = await build_report(
                session,
                student_ids=args.student_ids,
                student_numbers=args.student_numbers,
                invoice_ids=args.invoice_ids,
                invoice_numbers=args.invoice_numbers,
                event_date_from=args.event_date_from,
                event_date_to=args.event_date_to,
                limit=args.limit,
                tolerance=args.tolerance,
                only_errors=args.only_errors,
                database_label=database_label,
            )
    finally:
        await engine.dispose()

    if args.json:
        print(report_to_json(report))
    else:
        print_text_report(report, args.max_issues_per_invoice)

    if args.fail_on_findings and report.summary.total_findings > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
