#!/usr/bin/env python3
"""
Export compact fee summary for the current active term.

Usage examples:
    python3 scripts/export_active_term_students_invoices.py
    railway run python3 scripts/export_active_term_students_invoices.py
    railway run python3 scripts/export_active_term_students_invoices.py --student-status active
    railway run python3 scripts/export_active_term_students_invoices.py --output-dir exports/term-export
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.auth import models as _auth_models  # noqa: F401
from src.modules.inventory import models as _inventory_models  # noqa: F401
from src.modules.invoices.models import Invoice, InvoiceStatus, InvoiceType
from src.modules.payments import models as _payment_models  # noqa: F401
from src.modules.reservations import models as _reservation_models  # noqa: F401
from src.modules.students.models import Grade, Student, StudentStatus
from src.modules.terms.models import Term, TermStatus
from src.shared.utils.money import round_money


@dataclass
class StudentFeeRow:
    student: str
    school_fee: str
    transport_fee: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export student school fee and transport fee totals for the current active term."
    )
    parser.add_argument(
        "--database-url",
        help=(
            "Optional database URL override. If omitted, uses DATABASE_URL and falls back "
            "to DATABASE_PUBLIC_URL when Railway injects an internal hostname."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to write export files into. Defaults to exports/active-term-<term>-<timestamp>.",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "json", "both"),
        default="csv",
        help="Output format. Default: csv.",
    )
    parser.add_argument(
        "--student-status",
        choices=("all", StudentStatus.ACTIVE.value, StudentStatus.INACTIVE.value),
        default="all",
        help="Filter exported students by status. Default: all.",
    )
    return parser.parse_args()


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


def as_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return round_money(value)
    return round_money(Decimal(str(value)))


def money_str(value: Any) -> str:
    return f"{as_money(value):.2f}"


def date_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def sanitize_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip())
    safe = safe.strip("-")
    return safe or "active-term"


def build_default_output_dir(term: Term) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return project_root / "exports" / f"active-term-{sanitize_name(term.display_name)}-{stamp}"


async def load_active_term(session: AsyncSession) -> Term:
    result = await session.execute(
        select(Term).where(Term.status == TermStatus.ACTIVE.value).order_by(Term.id.asc())
    )
    terms = list(result.scalars().all())
    if not terms:
        raise RuntimeError("No active term found.")
    if len(terms) > 1:
        names = ", ".join(term.display_name for term in terms)
        raise RuntimeError(f"More than one active term found: {names}")
    return terms[0]


async def load_students(session: AsyncSession, student_status: str) -> list[Student]:
    query = (
        select(Student)
        .options(
            selectinload(Student.grade),
            selectinload(Student.transport_zone),
        )
        .join(Grade, Student.grade_id == Grade.id)
        .order_by(Grade.display_order.asc(), Grade.name.asc(), Student.student_number.asc())
    )
    if student_status != "all":
        query = query.where(Student.status == student_status)
    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def load_term_invoices(session: AsyncSession, term_id: int) -> list[Invoice]:
    result = await session.execute(
        select(Invoice)
        .where(Invoice.term_id == term_id)
        .where(
            Invoice.status.notin_(
                (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value)
            )
        )
        .options(
            selectinload(Invoice.student).selectinload(Student.grade),
            selectinload(Invoice.student).selectinload(Student.transport_zone),
            selectinload(Invoice.lines),
        )
        .order_by(Invoice.student_id.asc(), Invoice.invoice_number.asc())
    )
    return list(result.scalars().unique().all())


def build_export_rows(
    students: list[Student],
    invoices: list[Invoice],
) -> tuple[list[StudentFeeRow], dict[str, Any]]:
    fee_totals_by_student: dict[int, dict[str, Decimal]] = defaultdict(
        lambda: {
            "school_fee": Decimal("0.00"),
            "transport_fee": Decimal("0.00"),
        }
    )

    for invoice in invoices:
        student = invoice.student
        totals = fee_totals_by_student[student.id]
        if invoice.invoice_type == InvoiceType.SCHOOL_FEE.value:
            totals["school_fee"] = as_money(totals["school_fee"]) + as_money(invoice.total)
        elif invoice.invoice_type == InvoiceType.TRANSPORT.value:
            totals["transport_fee"] = as_money(totals["transport_fee"]) + as_money(invoice.total)

    student_rows: list[StudentFeeRow] = []
    for student in students:
        totals = fee_totals_by_student[student.id]
        student_rows.append(
            StudentFeeRow(
                student=f"{student.student_number} - {student.full_name}",
                school_fee=money_str(totals["school_fee"]),
                transport_fee=money_str(totals["transport_fee"]),
            )
        )

    summary = {
        "student_count": len(student_rows),
        "invoice_count": len(invoices),
        "students_with_any_fee": sum(
            1
            for row in student_rows
            if as_money(row.school_fee) > Decimal("0.00")
            or as_money(row.transport_fee) > Decimal("0.00")
        ),
        "school_fee_total": money_str(sum(as_money(row.school_fee) for row in student_rows)),
        "transport_fee_total": money_str(sum(as_money(row.transport_fee) for row in student_rows)),
    }
    return student_rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [row.__dict__.copy() for row in rows]


async def run_export(args: argparse.Namespace) -> int:
    database_url, source_name = resolve_database_url(args.database_url)
    engine = create_async_engine(database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            term = await load_active_term(session)
            students = await load_students(session, args.student_status)
            invoices = await load_term_invoices(session, term.id)

        student_rows, summary = build_export_rows(students, invoices)

        output_dir = Path(args.output_dir) if args.output_dir else build_default_output_dir(term)
        output_dir.mkdir(parents=True, exist_ok=True)

        written_files: list[Path] = []

        if args.format in {"csv", "both"}:
            students_csv = output_dir / "student_fees.csv"
            write_csv(
                students_csv,
                [
                    {
                        "student": row.student,
                        "school fee": row.school_fee,
                        "transport fee": row.transport_fee,
                    }
                    for row in student_rows
                ],
                ["student", "school fee", "transport fee"],
            )
            written_files.append(students_csv)

        if args.format in {"json", "both"}:
            json_path = output_dir / "export.json"
            payload = {
                "generated_at": datetime.now(UTC).isoformat(),
                "database_source": source_name,
                "term": {
                    "id": term.id,
                    "display_name": term.display_name,
                    "status": term.status,
                    "start_date": date_str(term.start_date),
                    "end_date": date_str(term.end_date),
                },
                "summary": summary,
                "students": to_dicts(student_rows),
            }
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            written_files.append(json_path)

        print(f"Active term: {term.display_name} (id={term.id})")
        print(f"Students exported: {len(student_rows)}")
        print(f"Invoices considered: {summary['invoice_count']}")
        print(f"School fee total: {summary['school_fee_total']}")
        print(f"Transport fee total: {summary['transport_fee_total']}")
        print(f"Output dir: {output_dir}")
        for path in written_files:
            print(f" - {path}")
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run_export(args))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
