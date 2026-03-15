#!/usr/bin/env python3
"""
Repair historical over-allocations on invoices discounted after allocations existed.

Dry-run by default. In apply mode, the script:

1. finds invoices touched by discount.apply or invoice.update_line_discount
2. estimates whether excess allocations still exist after the discount
3. releases excess allocations using PaymentService.release_excess_allocations()
4. runs standard auto-allocation once per affected student

Usage examples:
    python3 scripts/repair_discounted_invoice_allocations.py --event-date-to 2026-03-14
    python3 scripts/repair_discounted_invoice_allocations.py --invoice-number INV-2026-000218
    railway run python3 scripts/repair_discounted_invoice_allocations.py --invoice-number INV-2026-000218 --user-id 1 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
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
from src.modules.invoices.models import Invoice, InvoiceLine
from src.modules.items.models import Category, Item, ItemVariant, ItemVariantMembership, Kit, KitItem
from src.modules.payments.models import CreditAllocation, Payment
from src.modules.payments.schemas import AutoAllocateRequest
from src.modules.payments.service import PaymentService
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
class InvoiceRepairPlan:
    invoice_id: int
    invoice_number: str
    status: str
    total: str
    paid_total: str
    amount_due: str
    allocation_total: str
    estimated_release_amount: str
    first_allocation_at: str | None
    discount_events: list[DiscountEventSnapshot]
    reasons: list[str] = field(default_factory=list)
    applied_release_amount: str | None = None


@dataclass
class StudentRepairPlan:
    student_id: int
    student_number: str
    student_name: str
    invoices: list[InvoiceRepairPlan] = field(default_factory=list)
    estimated_release_total: str = "0.00"
    applied_release_total: str | None = None
    auto_allocated_total: str | None = None
    remaining_balance_after: str | None = None


@dataclass
class RepairSummary:
    environment: str
    database: str
    mode: str
    candidate_invoices: int
    repairable_invoices: int
    affected_students: int
    estimated_release_total: str
    applied_release_total: str
    applied_auto_allocated_total: str


@dataclass
class RepairReport:
    summary: RepairSummary
    students: list[StudentRepairPlan]


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
        description="Repair historical discounted invoices that still hold excess allocations."
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
        help="Target only one student id. Repeat flag to pass multiple ids.",
    )
    parser.add_argument(
        "--student-number",
        action="append",
        dest="student_numbers",
        help="Target only one student number. Repeat flag to pass multiple numbers.",
    )
    parser.add_argument(
        "--invoice-id",
        action="append",
        type=int,
        dest="invoice_ids",
        help="Target only one invoice id. Repeat flag to pass multiple ids.",
    )
    parser.add_argument(
        "--invoice-number",
        action="append",
        dest="invoice_numbers",
        help="Target only one invoice number. Repeat flag to pass multiple numbers.",
    )
    parser.add_argument(
        "--event-date-from",
        type=parse_date_arg,
        help="Include only discount events on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--event-date-to",
        type=parse_date_arg,
        help="Include only discount events on or before this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of candidate invoices to inspect after filters.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Allow apply-mode execution without any invoice/student/date filters.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        help="User id recorded in audit logs when --apply is used.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to the database. Without this flag the script is dry-run only.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--fail-on-targets",
        action="store_true",
        help="Exit with code 1 when at least one repairable invoice is found.",
    )
    parser.add_argument(
        "--tolerance",
        type=Decimal,
        default=Decimal("0.05"),
        help="Money tolerance for repair checks (default: 0.05).",
    )
    return parser.parse_args()


def as_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return round_money(value)
    return round_money(Decimal(str(value).replace(",", "")))


def money_str(value: Any) -> str:
    return f"{as_money(value):,.2f}"


def masked_database_url(url: str | None = None) -> str:
    effective_url = url or settings.database_url
    if "@" not in effective_url:
        return effective_url
    return f"...@{effective_url.split('@', 1)[1]}"


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


def simulate_reduce(
    allocations: list[dict[str, Any]],
    amount_to_release: Decimal,
) -> Decimal:
    released = Decimal("0.00")
    remaining = round_money(amount_to_release)

    for allocation in allocations:
        if remaining <= 0:
            break

        current_amount = as_money(allocation["amount"])
        release_amount = min(remaining, current_amount)
        if release_amount <= 0:
            continue

        allocation["amount"] = round_money(current_amount - release_amount)
        released = round_money(released + release_amount)
        remaining = round_money(remaining - release_amount)

    return released


def estimate_release_for_invoice(
    invoice: Invoice,
    allocations: list[CreditAllocation],
) -> tuple[Decimal, list[str]]:
    if not invoice.lines or not allocations:
        return Decimal("0.00"), []

    simulated = [
        {
            "allocation_id": allocation.id,
            "invoice_line_id": allocation.invoice_line_id,
            "amount": as_money(allocation.amount),
        }
        for allocation in allocations
    ]

    allocations_by_line: dict[int, list[dict[str, Any]]] = defaultdict(list)
    invoice_level_allocations: list[dict[str, Any]] = []
    for allocation in simulated:
        if allocation["invoice_line_id"] is None:
            invoice_level_allocations.append(allocation)
        else:
            allocations_by_line[int(allocation["invoice_line_id"])].append(allocation)

    released_total = Decimal("0.00")
    reasons: list[str] = []

    for line in invoice.lines:
        line_allocations = allocations_by_line.get(line.id, [])
        if not line_allocations:
            continue

        explicit_total = round_money(
            sum((as_money(allocation["amount"]) for allocation in line_allocations), Decimal("0.00"))
        )
        line_excess = round_money(max(Decimal("0.00"), explicit_total - as_money(line.net_amount)))
        if line_excess <= 0:
            continue

        released_total = round_money(
            released_total + simulate_reduce(line_allocations, line_excess)
        )
        reasons.append(
            f"Line {line.id} explicit allocations exceed net_amount by {money_str(line_excess)}"
        )

    total_allocated = round_money(
        sum((as_money(allocation["amount"]) for allocation in simulated), Decimal("0.00"))
    )
    invoice_excess = round_money(max(Decimal("0.00"), total_allocated - as_money(invoice.total)))
    if invoice_excess > 0 and invoice_level_allocations:
        released_total = round_money(
            released_total + simulate_reduce(invoice_level_allocations, invoice_excess)
        )
        reasons.append(
            f"Invoice allocations exceed invoice total by {money_str(invoice_excess)}"
        )

    total_allocated = round_money(
        sum((as_money(allocation["amount"]) for allocation in simulated), Decimal("0.00"))
    )
    invoice_excess = round_money(max(Decimal("0.00"), total_allocated - as_money(invoice.total)))
    if invoice_excess > 0:
        released_total = round_money(
            released_total + simulate_reduce(simulated, invoice_excess)
        )
        reasons.append(
            f"Fallback trim required for remaining excess {money_str(invoice_excess)}"
        )

    return round_money(released_total), reasons


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
    database_label: str,
    apply_mode: bool,
) -> RepairReport:
    students: list[Student] = []
    scoped_student_ids: set[int] | None = None
    if student_ids or student_numbers:
        students = await load_students(session, student_ids, student_numbers)
        scoped_student_ids = {student.id for student in students}
    if (student_ids or student_numbers) and not scoped_student_ids:
        summary = RepairSummary(
            environment=settings.app_env,
            database=database_label,
            mode="apply" if apply_mode else "dry-run",
            candidate_invoices=0,
            repairable_invoices=0,
            affected_students=0,
            estimated_release_total="0.00",
            applied_release_total="0.00",
            applied_auto_allocated_total="0.00",
        )
        return RepairReport(summary=summary, students=[])

    scoped_invoice_ids = await load_invoice_scope_ids(
        session,
        invoice_ids=invoice_ids,
        invoice_numbers=invoice_numbers,
    )
    if (invoice_ids or invoice_numbers) and not scoped_invoice_ids:
        summary = RepairSummary(
            environment=settings.app_env,
            database=database_label,
            mode="apply" if apply_mode else "dry-run",
            candidate_invoices=0,
            repairable_invoices=0,
            affected_students=0,
            estimated_release_total="0.00",
            applied_release_total="0.00",
            applied_auto_allocated_total="0.00",
        )
        return RepairReport(summary=summary, students=[])

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
        summary = RepairSummary(
            environment=settings.app_env,
            database=database_label,
            mode="apply" if apply_mode else "dry-run",
            candidate_invoices=0,
            repairable_invoices=0,
            affected_students=0,
            estimated_release_total="0.00",
            applied_release_total="0.00",
            applied_auto_allocated_total="0.00",
        )
        return RepairReport(summary=summary, students=[])

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

    allocations_result = await session.execute(
        select(CreditAllocation)
        .where(CreditAllocation.invoice_id.in_(candidate_invoice_ids))
        .order_by(CreditAllocation.created_at.desc(), CreditAllocation.id.desc())
    )
    allocations = list(allocations_result.scalars().all())
    allocations_by_invoice: dict[int, list[CreditAllocation]] = defaultdict(list)
    for allocation in allocations:
        allocations_by_invoice[allocation.invoice_id].append(allocation)

    student_plans_by_id: dict[int, StudentRepairPlan] = {}
    estimated_release_total = Decimal("0.00")
    repairable_invoices = 0

    for invoice in invoices:
        invoice_allocations = allocations_by_invoice.get(invoice.id, [])
        estimated_release, reasons = estimate_release_for_invoice(invoice, invoice_allocations)
        if estimated_release <= tolerance:
            continue

        repairable_invoices += 1
        estimated_release_total = round_money(estimated_release_total + estimated_release)

        student = invoice.student
        if student.id not in student_plans_by_id:
            student_plans_by_id[student.id] = StudentRepairPlan(
                student_id=student.id,
                student_number=student.student_number,
                student_name=student.full_name,
            )

        first_allocation_at = (
            invoice_allocations[-1].created_at.isoformat() if invoice_allocations else None
        )
        invoice_plan = InvoiceRepairPlan(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            status=invoice.status,
            total=money_str(invoice.total),
            paid_total=money_str(invoice.paid_total),
            amount_due=money_str(invoice.amount_due),
            allocation_total=money_str(
                sum((as_money(allocation.amount) for allocation in invoice_allocations), Decimal("0.00"))
            ),
            estimated_release_amount=money_str(estimated_release),
            first_allocation_at=first_allocation_at,
            discount_events=events_by_invoice.get(invoice.id, []),
            reasons=reasons,
        )
        student_plans_by_id[student.id].invoices.append(invoice_plan)

    student_plans = list(student_plans_by_id.values())
    for student_plan in student_plans:
        student_plan.estimated_release_total = money_str(
            sum((as_money(invoice.estimated_release_amount) for invoice in student_plan.invoices), Decimal("0.00"))
        )

    summary = RepairSummary(
        environment=settings.app_env,
        database=database_label,
        mode="apply" if apply_mode else "dry-run",
        candidate_invoices=len(candidate_invoice_ids),
        repairable_invoices=repairable_invoices,
        affected_students=len(student_plans),
        estimated_release_total=money_str(estimated_release_total),
        applied_release_total="0.00",
        applied_auto_allocated_total="0.00",
    )
    return RepairReport(summary=summary, students=student_plans)


async def apply_report(
    session: AsyncSession,
    report: RepairReport,
    user_id: int,
) -> None:
    payment_service = PaymentService(session)
    total_released = Decimal("0.00")
    total_auto_allocated = Decimal("0.00")

    for student_plan in report.students:
        student_released = Decimal("0.00")

        for invoice_plan in student_plan.invoices:
            released = await payment_service.release_excess_allocations(
                invoice_id=invoice_plan.invoice_id,
                user_id=user_id,
                reason=(
                    "Repair historical discounted invoice over-allocation "
                    f"for {invoice_plan.invoice_number}"
                ),
            )
            invoice_plan.applied_release_amount = money_str(released)
            student_released = round_money(student_released + released)
            total_released = round_money(total_released + released)

        student_plan.applied_release_total = money_str(student_released)
        if student_released > 0:
            auto_result = await payment_service.allocate_auto(
                AutoAllocateRequest(student_id=student_plan.student_id),
                user_id,
            )
            student_plan.auto_allocated_total = money_str(auto_result.total_allocated)
            student_plan.remaining_balance_after = money_str(auto_result.remaining_balance)
            total_auto_allocated = round_money(
                total_auto_allocated + auto_result.total_allocated
            )
        else:
            student_plan.auto_allocated_total = "0.00"
            student_plan.remaining_balance_after = None

    report.summary.applied_release_total = money_str(total_released)
    report.summary.applied_auto_allocated_total = money_str(total_auto_allocated)


def report_to_json(report: RepairReport) -> str:
    payload = {
        "summary": asdict(report.summary),
        "students": [
            {
                **{
                    key: value
                    for key, value in asdict(student_plan).items()
                    if key != "invoices"
                },
                "invoices": [
                    {
                        **{
                            key: value
                            for key, value in asdict(invoice_plan).items()
                            if key != "discount_events"
                        },
                        "discount_events": [
                            asdict(event) for event in invoice_plan.discount_events
                        ],
                    }
                    for invoice_plan in student_plan.invoices
                ],
            }
            for student_plan in report.students
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def print_text_report(report: RepairReport) -> None:
    summary = report.summary
    print(
        f"[discount-repair] Environment={summary.environment} "
        f"Database={summary.database} Mode={summary.mode}"
    )
    print(
        f"[discount-repair] Candidates={summary.candidate_invoices} "
        f"Repairable={summary.repairable_invoices} "
        f"Students={summary.affected_students} "
        f"EstimatedRelease={summary.estimated_release_total}"
    )
    if summary.mode == "apply":
        print(
            f"[discount-repair] AppliedRelease={summary.applied_release_total} "
            f"AutoAllocated={summary.applied_auto_allocated_total}"
        )

    if not report.students:
        print("No repairable discounted invoices found in the selected scope.")
        return

    for student_plan in report.students:
        print()
        print(
            f"[{student_plan.student_id}] {student_plan.student_number} · "
            f"{student_plan.student_name}"
        )
        print(f"  Estimated release: {student_plan.estimated_release_total}")
        if student_plan.applied_release_total is not None:
            print(
                f"  Applied release: {student_plan.applied_release_total} · "
                f"Auto-allocated: {student_plan.auto_allocated_total or '0.00'}"
            )
            if student_plan.remaining_balance_after is not None:
                print(f"  Remaining balance: {student_plan.remaining_balance_after}")

        for invoice_plan in student_plan.invoices:
            print(
                f"  - {invoice_plan.invoice_number} ({invoice_plan.status}) "
                f"total={invoice_plan.total} paid={invoice_plan.paid_total} "
                f"due={invoice_plan.amount_due} allocations={invoice_plan.allocation_total} "
                f"release={invoice_plan.estimated_release_amount}"
            )
            if invoice_plan.first_allocation_at:
                print(f"    first_allocation={invoice_plan.first_allocation_at}")
            if invoice_plan.discount_events:
                first_event = invoice_plan.discount_events[0]
                print(
                    f"    first_discount_event={first_event.created_at} "
                    f"action={first_event.action}"
                )
            for reason in invoice_plan.reasons:
                print(f"    reason: {reason}")
            if invoice_plan.applied_release_amount is not None:
                print(f"    applied_release={invoice_plan.applied_release_amount}")


async def main() -> int:
    args = parse_args()
    if args.apply and args.user_id is None:
        print("--user-id is required when --apply is used.", file=sys.stderr)
        return 2

    if args.apply and not (
        args.all
        or args.student_ids
        or args.student_numbers
        or args.invoice_ids
        or args.invoice_numbers
        or args.event_date_from
        or args.event_date_to
    ):
        print(
            "Refusing to run --apply without an explicit scope. "
            "Pass invoice/student filters, an event-date filter, or --all.",
            file=sys.stderr,
        )
        return 2

    db_url, db_source = resolve_database_url(args.database_url)
    database_label = masked_database_url(db_url)
    print(
        f"[discount-repair] Environment={settings.app_env} "
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
                database_label=database_label,
                apply_mode=args.apply,
            )
            if args.apply and report.summary.repairable_invoices > 0:
                await apply_report(session, report, args.user_id)
    finally:
        await engine.dispose()

    if args.json:
        print(report_to_json(report))
    else:
        print_text_report(report)

    if args.fail_on_targets and report.summary.repairable_invoices > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
