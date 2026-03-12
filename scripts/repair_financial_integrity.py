#!/usr/bin/env python3
"""
Repair stale financial aggregates for selected students.

Dry-run by default. Safe repairs include:

- recomputing invoice line net / paid / remaining from discounts + allocations
- recomputing invoice subtotal / discount_total / total / paid_total / amount_due
- refreshing invoice status for non-draft / non-cancelled / non-void invoices
- refreshing student.cached_credit_balance from completed payments - allocations

Usage examples:
    python3 scripts/repair_financial_integrity.py --student-number STU-2026-000014
    python3 scripts/repair_financial_integrity.py --student-id 14 --student-id 15 --apply
    railway run python3 scripts/repair_financial_integrity.py --student-number STU-2026-000014 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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


NON_EDITABLE_STATUSES = {
    InvoiceStatus.DRAFT.value,
    InvoiceStatus.CANCELLED.value,
    InvoiceStatus.VOID.value,
}


@dataclass
class FieldChange:
    field: str
    before: str
    after: str


@dataclass
class LinePlan:
    line: InvoiceLine
    target_net_amount: Decimal
    target_paid_amount: Decimal
    target_remaining_amount: Decimal
    changes: list[FieldChange] = field(default_factory=list)


@dataclass
class InvoicePlan:
    invoice: Invoice
    target_subtotal: Decimal
    target_discount_total: Decimal
    target_total: Decimal
    target_paid_total: Decimal
    target_amount_due: Decimal
    target_status: str
    changes: list[FieldChange] = field(default_factory=list)
    line_plans: list[LinePlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safe_to_apply: bool = True


@dataclass
class StudentPlan:
    student: Student
    target_cached_credit_balance: Decimal
    changes: list[FieldChange] = field(default_factory=list)
    invoice_plans: list[InvoicePlan] = field(default_factory=list)


@dataclass
class RepairSummary:
    environment: str
    database: str
    mode: str
    students_targeted: int
    students_with_changes: int
    invoices_with_changes: int
    lines_with_changes: int
    skipped_invoices: int
    warnings: int


@dataclass
class RepairReport:
    summary: RepairSummary
    students: list[StudentPlan]


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
        description="Repair stale invoice/payment aggregates for selected students."
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
        help="Repair only one student id. Repeat flag to pass multiple ids.",
    )
    parser.add_argument(
        "--student-number",
        action="append",
        dest="student_numbers",
        help="Repair only one student number. Repeat flag to pass multiple numbers.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_students",
        help="Target all students. Use carefully.",
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
        "--tolerance",
        type=Decimal,
        default=Decimal("0.05"),
        help="Money tolerance for mismatch checks (default: 0.05).",
    )
    parser.add_argument(
        "--max-lines-per-invoice",
        type=int,
        default=20,
        help="Cap text output per invoice to keep Railway logs readable.",
    )
    args = parser.parse_args()
    if not args.all_students and not args.student_ids and not args.student_numbers:
        parser.error("Pass at least one --student-id / --student-number, or use --all.")
    return args


def as_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return round_money(value)
    return round_money(Decimal(str(value)))


def money_str(value: Any) -> str:
    return f"{as_money(value):,.2f}"


def value_str(value: Any) -> str:
    if isinstance(value, (Decimal, float, int)):
        return money_str(value)
    return str(value)


def masked_database_url(url: str | None = None) -> str:
    effective_url = url or settings.database_url
    if "@" not in effective_url:
        return effective_url
    return f"...@{effective_url.split('@', 1)[1]}"


def money_diff(left: Any, right: Any) -> Decimal:
    return abs(as_money(left) - as_money(right))


def changed_money(left: Any, right: Any, tolerance: Decimal) -> bool:
    return money_diff(left, right) > tolerance


def changed_value(left: Any, right: Any, tolerance: Decimal) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        return changed_money(left, right, tolerance)
    return left != right


def add_change(
    changes: list[FieldChange],
    field_name: str,
    before: Any,
    after: Any,
    tolerance: Decimal,
) -> None:
    if not changed_value(before, after, tolerance):
        return
    changes.append(
        FieldChange(
            field=field_name,
            before=value_str(before),
            after=value_str(after),
        )
    )


def money_to_cents(value: Decimal) -> int:
    return int((round_money(value) * 100).to_integral_value())


def cents_to_money(value: int) -> Decimal:
    return round_money(Decimal(value) / Decimal("100"))


def allocate_proportionally(
    total: Decimal,
    capacities: dict[int, Decimal],
) -> tuple[dict[int, Decimal], Decimal]:
    allocations = {key: Decimal("0.00") for key in capacities}
    total = round_money(total)
    if total <= 0:
        return allocations, Decimal("0.00")

    capacity_cents = {
        key: max(0, money_to_cents(value))
        for key, value in capacities.items()
    }
    total_capacity_cents = sum(capacity_cents.values())
    if total_capacity_cents <= 0:
        return allocations, total

    total_cents = max(0, money_to_cents(total))
    if total_cents >= total_capacity_cents:
        for key, cents in capacity_cents.items():
            allocations[key] = cents_to_money(cents)
        return allocations, cents_to_money(total_cents - total_capacity_cents)

    allocated_cents = {key: 0 for key in capacities}
    remainders: list[tuple[Decimal, int]] = []
    used_cents = 0

    for key, cap_cents in capacity_cents.items():
        if cap_cents <= 0:
            continue
        raw_share = Decimal(total_cents) * Decimal(cap_cents) / Decimal(total_capacity_cents)
        base_cents = min(cap_cents, int(raw_share))
        allocated_cents[key] = base_cents
        used_cents += base_cents
        remainders.append((raw_share - Decimal(base_cents), key))

    leftover_cents = total_cents - used_cents
    remainders.sort(key=lambda row: (row[0], row[1]), reverse=True)
    while leftover_cents > 0:
        updated = False
        for _, key in remainders:
            if leftover_cents <= 0:
                break
            if allocated_cents[key] >= capacity_cents[key]:
                continue
            allocated_cents[key] += 1
            leftover_cents -= 1
            updated = True
        if not updated:
            break

    for key, cents in allocated_cents.items():
        allocations[key] = cents_to_money(cents)

    return allocations, cents_to_money(leftover_cents)


async def load_students(
    session: AsyncSession,
    student_ids: list[int] | None,
    student_numbers: list[str] | None,
    all_students: bool,
) -> list[Student]:
    query = select(Student).order_by(Student.id)
    filters = []
    if student_ids:
        filters.append(Student.id.in_(student_ids))
    if student_numbers:
        filters.append(Student.student_number.in_(student_numbers))
    if filters:
        query = query.where(or_(*filters))
    elif not all_students:
        return []

    result = await session.execute(query)
    return list(result.scalars().all())


def build_invoice_plan(
    invoice: Invoice,
    invoice_alloc_total: Decimal,
    line_alloc_sums: dict[int, Decimal],
    tolerance: Decimal,
) -> InvoicePlan:
    target_subtotal = round_money(
        sum((as_money(line.line_total) for line in invoice.lines), Decimal("0.00"))
    )
    target_discount_total = round_money(
        sum((as_money(line.discount_amount) for line in invoice.lines), Decimal("0.00"))
    )
    target_total = round_money(target_subtotal - target_discount_total)

    invoice_plan = InvoicePlan(
        invoice=invoice,
        target_subtotal=target_subtotal,
        target_discount_total=target_discount_total,
        target_total=target_total,
        target_paid_total=round_money(invoice_alloc_total),
        target_amount_due=Decimal("0.00"),
        target_status=invoice.status,
    )

    if not invoice.lines and invoice_alloc_total > tolerance:
        invoice_plan.safe_to_apply = False
        invoice_plan.warnings.append(
            "Invoice has allocations but no lines; automatic line repair is unsafe."
        )
        return invoice_plan

    explicit_line_total = Decimal("0.00")
    capacities: dict[int, Decimal] = {}
    line_targets: dict[int, tuple[Decimal, Decimal]] = {}

    for line in invoice.lines:
        target_net = round_money(as_money(line.line_total) - as_money(line.discount_amount))
        explicit_paid = round_money(line_alloc_sums.get(line.id, Decimal("0.00")))
        explicit_line_total = round_money(explicit_line_total + explicit_paid)
        capacities[line.id] = round_money(max(Decimal("0.00"), target_net - explicit_paid))
        line_targets[line.id] = (target_net, explicit_paid)

        if explicit_paid > target_net + tolerance:
            invoice_plan.safe_to_apply = False
            invoice_plan.warnings.append(
                f"Line {line.id} has explicit allocations greater than line net amount."
            )

    invoice_level_remainder = round_money(invoice_alloc_total - explicit_line_total)
    if invoice_level_remainder < Decimal("0.00") - tolerance:
        invoice_plan.safe_to_apply = False
        invoice_plan.warnings.append(
            "Line-level allocations exceed invoice-level allocation total."
        )

    proportional_paid_map, leftover = allocate_proportionally(
        max(Decimal("0.00"), invoice_level_remainder),
        capacities,
    )
    if leftover > tolerance:
        invoice_plan.safe_to_apply = False
        invoice_plan.warnings.append(
            "Invoice allocations exceed remaining line capacities after discount."
        )

    line_plans: list[LinePlan] = []
    for line in invoice.lines:
        target_net, explicit_paid = line_targets[line.id]
        target_paid = round_money(explicit_paid + proportional_paid_map.get(line.id, Decimal("0.00")))
        target_remaining = round_money(target_net - target_paid)

        line_plan = LinePlan(
            line=line,
            target_net_amount=target_net,
            target_paid_amount=target_paid,
            target_remaining_amount=target_remaining,
        )
        add_change(line_plan.changes, "net_amount", line.net_amount, target_net, tolerance)
        add_change(line_plan.changes, "paid_amount", line.paid_amount, target_paid, tolerance)
        add_change(
            line_plan.changes,
            "remaining_amount",
            line.remaining_amount,
            target_remaining,
            tolerance,
        )
        line_plans.append(line_plan)

        if target_remaining < Decimal("0.00") - tolerance:
            invoice_plan.safe_to_apply = False
            invoice_plan.warnings.append(
                f"Line {line.id} would end up with negative remaining_amount."
            )

    target_due = round_money(target_total - invoice_alloc_total)
    if invoice_alloc_total > target_total + tolerance:
        invoice_plan.safe_to_apply = False
        invoice_plan.warnings.append("Invoice allocations exceed invoice net total.")

    if invoice.status not in NON_EDITABLE_STATUSES:
        if target_due <= Decimal("0.00"):
            target_status = InvoiceStatus.PAID.value
        elif invoice_alloc_total > Decimal("0.00"):
            target_status = InvoiceStatus.PARTIALLY_PAID.value
        else:
            target_status = InvoiceStatus.ISSUED.value
    else:
        target_status = invoice.status

    invoice_plan.target_amount_due = target_due
    invoice_plan.target_status = target_status
    invoice_plan.line_plans = line_plans

    add_change(invoice_plan.changes, "subtotal", invoice.subtotal, target_subtotal, tolerance)
    add_change(
        invoice_plan.changes,
        "discount_total",
        invoice.discount_total,
        target_discount_total,
        tolerance,
    )
    add_change(invoice_plan.changes, "total", invoice.total, target_total, tolerance)
    add_change(
        invoice_plan.changes,
        "paid_total",
        invoice.paid_total,
        invoice_alloc_total,
        tolerance,
    )
    add_change(invoice_plan.changes, "amount_due", invoice.amount_due, target_due, tolerance)
    add_change(invoice_plan.changes, "status", invoice.status, target_status, tolerance)
    return invoice_plan


async def build_report(
    session: AsyncSession,
    student_ids: list[int] | None,
    student_numbers: list[str] | None,
    all_students: bool,
    tolerance: Decimal,
    database_label: str,
) -> RepairReport:
    students = await load_students(session, student_ids, student_numbers, all_students)
    if not students:
        return RepairReport(
            summary=RepairSummary(
                environment=settings.app_env,
                database=database_label,
                mode="dry-run",
                students_targeted=0,
                students_with_changes=0,
                invoices_with_changes=0,
                lines_with_changes=0,
                skipped_invoices=0,
                warnings=0,
            ),
            students=[],
        )

    student_ids_scope = [student.id for student in students]
    invoices_result = await session.execute(
        select(Invoice)
        .where(Invoice.student_id.in_(student_ids_scope))
        .options(selectinload(Invoice.lines))
        .order_by(Invoice.student_id, Invoice.created_at, Invoice.id)
    )
    invoices = list(invoices_result.scalars().all())

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
            int(row.invoice_id): as_money(row.allocated_total)
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

    completed_payments_rows = await session.execute(
        select(
            Payment.student_id,
            func.coalesce(func.sum(Payment.amount), 0).label("completed_total"),
        )
        .where(
            Payment.student_id.in_(student_ids_scope),
            Payment.status == PaymentStatus.COMPLETED.value,
        )
        .group_by(Payment.student_id)
    )
    completed_payments = {
        int(row.student_id): as_money(row.completed_total)
        for row in completed_payments_rows.all()
    }

    allocation_rows = await session.execute(
        select(
            CreditAllocation.student_id,
            func.coalesce(func.sum(CreditAllocation.amount), 0).label("allocated_total"),
        )
        .where(CreditAllocation.student_id.in_(student_ids_scope))
        .group_by(CreditAllocation.student_id)
    )
    allocated_by_student = {
        int(row.student_id): as_money(row.allocated_total)
        for row in allocation_rows.all()
    }

    invoices_by_student: dict[int, list[Invoice]] = {student.id: [] for student in students}
    for invoice in invoices:
        invoices_by_student.setdefault(invoice.student_id, []).append(invoice)

    student_plans: list[StudentPlan] = []
    students_with_changes = 0
    invoices_with_changes = 0
    lines_with_changes = 0
    skipped_invoices = 0
    warnings = 0

    for student in students:
        target_cached_credit = round_money(
            completed_payments.get(student.id, Decimal("0.00"))
            - allocated_by_student.get(student.id, Decimal("0.00"))
        )
        student_plan = StudentPlan(
            student=student,
            target_cached_credit_balance=target_cached_credit,
        )
        add_change(
            student_plan.changes,
            "cached_credit_balance",
            student.cached_credit_balance,
            target_cached_credit,
            tolerance,
        )

        for invoice in invoices_by_student.get(student.id, []):
            invoice_line_alloc_sums = {
                line.id: line_alloc_sums.get(line.id, Decimal("0.00"))
                for line in invoice.lines
            }
            plan = build_invoice_plan(
                invoice=invoice,
                invoice_alloc_total=invoice_alloc_sums.get(invoice.id, Decimal("0.00")),
                line_alloc_sums=invoice_line_alloc_sums,
                tolerance=tolerance,
            )
            student_plan.invoice_plans.append(plan)

            if plan.warnings:
                warnings += len(plan.warnings)
            if not plan.safe_to_apply:
                skipped_invoices += 1
            if plan.changes:
                invoices_with_changes += 1
            lines_with_changes += sum(1 for line_plan in plan.line_plans if line_plan.changes)

        has_changes = bool(student_plan.changes) or any(
            plan.changes or any(line_plan.changes for line_plan in plan.line_plans)
            for plan in student_plan.invoice_plans
        )
        if has_changes:
            students_with_changes += 1
            student_plans.append(student_plan)
        elif any(plan.warnings for plan in student_plan.invoice_plans):
            student_plans.append(student_plan)

    summary = RepairSummary(
        environment=settings.app_env,
        database=database_label,
        mode="dry-run",
        students_targeted=len(students),
        students_with_changes=students_with_changes,
        invoices_with_changes=invoices_with_changes,
        lines_with_changes=lines_with_changes,
        skipped_invoices=skipped_invoices,
        warnings=warnings,
    )
    return RepairReport(summary=summary, students=student_plans)


def apply_report(report: RepairReport) -> None:
    for student_plan in report.students:
        student_plan.student.cached_credit_balance = student_plan.target_cached_credit_balance
        for invoice_plan in student_plan.invoice_plans:
            if not invoice_plan.safe_to_apply:
                continue
            for line_plan in invoice_plan.line_plans:
                line_plan.line.net_amount = line_plan.target_net_amount
                line_plan.line.paid_amount = line_plan.target_paid_amount
                line_plan.line.remaining_amount = line_plan.target_remaining_amount

            invoice_plan.invoice.subtotal = invoice_plan.target_subtotal
            invoice_plan.invoice.discount_total = invoice_plan.target_discount_total
            invoice_plan.invoice.total = invoice_plan.target_total
            invoice_plan.invoice.paid_total = invoice_plan.target_paid_total
            invoice_plan.invoice.amount_due = invoice_plan.target_amount_due
            invoice_plan.invoice.status = invoice_plan.target_status


def report_to_json(report: RepairReport) -> str:
    payload = {
        "summary": asdict(report.summary),
        "students": [
            {
                "student_id": plan.student.id,
                "student_number": plan.student.student_number,
                "full_name": plan.student.full_name,
                "changes": [asdict(change) for change in plan.changes],
                "invoices": [
                    {
                        "invoice_id": invoice_plan.invoice.id,
                        "invoice_number": invoice_plan.invoice.invoice_number,
                        "safe_to_apply": invoice_plan.safe_to_apply,
                        "warnings": invoice_plan.warnings,
                        "changes": [asdict(change) for change in invoice_plan.changes],
                        "lines": [
                            {
                                "line_id": line_plan.line.id,
                                "changes": [asdict(change) for change in line_plan.changes],
                            }
                            for line_plan in invoice_plan.line_plans
                            if line_plan.changes
                        ],
                    }
                    for invoice_plan in plan.invoice_plans
                    if invoice_plan.changes
                    or any(line_plan.changes for line_plan in invoice_plan.line_plans)
                    or invoice_plan.warnings
                ],
            }
            for plan in report.students
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def print_text_report(report: RepairReport, max_lines_per_invoice: int) -> None:
    summary = report.summary
    title = "FINANCIAL INTEGRITY REPAIR"
    print("=" * 78)
    print(title)
    print("=" * 78)
    print(f"Environment: {summary.environment}")
    print(f"Database:    {summary.database}")
    print(f"Mode:        {summary.mode}")
    print(f"Students:    {summary.students_targeted}")
    print(f"To change:   {summary.students_with_changes} students / {summary.invoices_with_changes} invoices / {summary.lines_with_changes} lines")
    print(f"Skipped:     {summary.skipped_invoices} invoices")
    print(f"Warnings:    {summary.warnings}")

    if not report.students:
        print("\nNo matching students found.")
        return

    visible_students = [
        plan
        for plan in report.students
        if plan.changes
        or any(
            invoice_plan.changes
            or any(line_plan.changes for line_plan in invoice_plan.line_plans)
            or invoice_plan.warnings
            for invoice_plan in plan.invoice_plans
        )
    ]
    if not visible_students:
        print("\nNo repairs needed.")
        return

    print("\nPlanned changes:")
    for student_plan in visible_students:
        print(
            f"\n[{student_plan.student.id}] {student_plan.student.student_number} · "
            f"{student_plan.student.full_name}"
        )
        for change in student_plan.changes:
            print(f"  - student.{change.field}: {change.before} -> {change.after}")

        for invoice_plan in student_plan.invoice_plans:
            has_invoice_output = (
                invoice_plan.changes
                or any(line_plan.changes for line_plan in invoice_plan.line_plans)
                or invoice_plan.warnings
            )
            if not has_invoice_output:
                continue

            status_suffix = "" if invoice_plan.safe_to_apply else " [SKIPPED]"
            print(f"  - invoice {invoice_plan.invoice.invoice_number}{status_suffix}")
            for change in invoice_plan.changes:
                print(f"      {change.field}: {change.before} -> {change.after}")
            for warning in invoice_plan.warnings:
                print(f"      warning: {warning}")

            visible_line_plans = [
                line_plan for line_plan in invoice_plan.line_plans if line_plan.changes
            ][:max_lines_per_invoice]
            hidden_lines = sum(1 for line_plan in invoice_plan.line_plans if line_plan.changes) - len(
                visible_line_plans
            )
            for line_plan in visible_line_plans:
                print(f"      line {line_plan.line.id}:")
                for change in line_plan.changes:
                    print(f"        {change.field}: {change.before} -> {change.after}")
            if hidden_lines > 0:
                print(f"      ... {hidden_lines} more changed line(s) omitted")


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
        f"[repair] Environment={settings.app_env} Database={masked_database_url(database_url)} Source={url_source} Apply={args.apply}",
        file=sys.stderr,
    )

    try:
        async with session_factory() as session:
            report = await build_report(
                session=session,
                student_ids=args.student_ids,
                student_numbers=args.student_numbers,
                all_students=args.all_students,
                tolerance=args.tolerance,
                database_label=masked_database_url(database_url),
            )
            report.summary.mode = "apply" if args.apply else "dry-run"

            if args.apply:
                apply_report(report)
                await session.commit()
    finally:
        await engine.dispose()

    if args.json:
        print(report_to_json(report))
    else:
        print_text_report(report, args.max_lines_per_invoice)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
