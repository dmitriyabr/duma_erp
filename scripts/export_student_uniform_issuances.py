#!/usr/bin/env python3
"""
Export issued uniform items per student.

Usage examples:
    python3 scripts/export_student_uniform_issuances.py
    railway run python3 scripts/export_student_uniform_issuances.py
    railway run python3 scripts/export_student_uniform_issuances.py --student-status active
    railway run python3 scripts/export_student_uniform_issuances.py --output-dir exports/uniform-export
    railway run python3 scripts/export_student_uniform_issuances.py --format both
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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.auth import models as _auth_models  # noqa: F401
from src.core.auth.models import User
from src.core.config import settings
from src.modules.inventory import models as _inventory_models  # noqa: F401
from src.modules.inventory.models import Issuance, IssuanceItem, IssuanceStatus, RecipientType
from src.modules.invoices import models as _invoice_models  # noqa: F401
from src.modules.items.models import Category, Item, ItemVariant, ItemVariantMembership
from src.modules.payments import models as _payment_models  # noqa: F401
from src.modules.reservations import models as _reservation_models  # noqa: F401
from src.modules.students.models import Grade, Student, StudentStatus
from src.shared.utils.money import round_money


@dataclass
class UniformIssueRecord:
    student_id: int
    student_number: str
    student_name: str
    grade: str
    student_status: str
    issuance_id: int
    issuance_number: str
    issuance_type: str
    reservation_id: int | None
    issued_at: datetime
    issued_by_name: str
    notes: str
    item_id: int
    item_sku: str
    item_name: str
    variant_names: str
    quantity: int
    unit_cost: Decimal


@dataclass
class StudentUniformSummaryRow:
    student_number: str
    student_name: str
    grade: str
    student_status: str
    distinct_uniform_items: int
    total_uniform_quantity: int
    first_issued_at: str
    last_issued_at: str
    issued_uniforms: str


@dataclass
class StudentUniformItemRow:
    student_number: str
    student_name: str
    grade: str
    student_status: str
    item_sku: str
    item_name: str
    variant_names: str
    total_quantity_issued: int
    issue_events_count: int
    first_issued_at: str
    last_issued_at: str


@dataclass
class StudentUniformMovementRow:
    issuance_number: str
    issued_at: str
    issuance_type: str
    student_number: str
    student_name: str
    grade: str
    student_status: str
    item_sku: str
    item_name: str
    variant_names: str
    quantity: int
    unit_cost: str
    issued_by_name: str
    reservation_id: str
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export issued uniform items per student. "
            "By default, reads completed student issuances for category 'Uniform'."
        )
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
        help=(
            "Directory to write export files into. "
            "Defaults to exports/uniform-issuances-<category>-<timestamp>."
        ),
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
        help="Filter exported students by current status. Default: all.",
    )
    parser.add_argument(
        "--category-name",
        default="Uniform",
        help="Exact item category name to export. Default: Uniform.",
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
    if hostname and hostname.endswith(".railway.internal") and not public_url:
        raise RuntimeError(
            "DATABASE_URL points to a Railway private host, but DATABASE_PUBLIC_URL is not set. "
            "For local railway run usage, add DATABASE_PUBLIC_URL from the Postgres service "
            "to the app service variables, or pass --database-url with a public Postgres URL."
        )

    return candidate, "DATABASE_URL"


def sanitize_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip())
    safe = safe.strip("-")
    return safe or "uniform"


def build_default_output_dir(category_name: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return project_root / "exports" / f"uniform-issuances-{sanitize_name(category_name)}-{stamp}"


def as_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return round_money(value)
    return round_money(Decimal(str(value)))


def money_str(value: Any) -> str:
    return f"{as_money(value):.2f}"


def dt_str(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        return value.isoformat(timespec="seconds")
    return value.astimezone(UTC).isoformat(timespec="seconds")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def load_variant_names_by_item_id(
    session: AsyncSession,
    item_ids: list[int],
) -> dict[int, str]:
    if not item_ids:
        return {}

    result = await session.execute(
        select(ItemVariantMembership.item_id, ItemVariant.name)
        .join(ItemVariant, ItemVariant.id == ItemVariantMembership.variant_id)
        .where(ItemVariantMembership.item_id.in_(item_ids))
        .order_by(ItemVariantMembership.item_id.asc(), ItemVariant.name.asc())
    )

    grouped: dict[int, list[str]] = defaultdict(list)
    for item_id, variant_name in result.all():
        if item_id is None or not variant_name:
            continue
        if variant_name not in grouped[int(item_id)]:
            grouped[int(item_id)].append(str(variant_name))

    return {item_id: ", ".join(names) for item_id, names in grouped.items()}


async def load_uniform_issue_records(
    session: AsyncSession,
    *,
    category_name: str,
    student_status: str,
) -> list[UniformIssueRecord]:
    query = (
        select(
            Student.id.label("student_id"),
            Student.student_number.label("student_number"),
            Student.first_name.label("first_name"),
            Student.last_name.label("last_name"),
            Student.status.label("student_status"),
            Grade.name.label("grade_name"),
            Issuance.id.label("issuance_id"),
            Issuance.issuance_number.label("issuance_number"),
            Issuance.issuance_type.label("issuance_type"),
            Issuance.reservation_id.label("reservation_id"),
            Issuance.issued_at.label("issued_at"),
            Issuance.notes.label("notes"),
            User.full_name.label("issued_by_name"),
            Item.id.label("item_id"),
            Item.sku_code.label("item_sku"),
            Item.name.label("item_name"),
            IssuanceItem.quantity.label("quantity"),
            IssuanceItem.unit_cost.label("unit_cost"),
        )
        .select_from(Issuance)
        .join(
            Student,
            Student.id == Issuance.recipient_id,
        )
        .outerjoin(Grade, Grade.id == Student.grade_id)
        .join(IssuanceItem, IssuanceItem.issuance_id == Issuance.id)
        .join(Item, Item.id == IssuanceItem.item_id)
        .join(Category, Category.id == Item.category_id)
        .outerjoin(User, User.id == Issuance.issued_by_id)
        .where(Issuance.recipient_type == RecipientType.STUDENT.value)
        .where(Issuance.status == IssuanceStatus.COMPLETED.value)
        .where(func.lower(Category.name) == category_name.strip().lower())
        .order_by(
            Grade.display_order.asc(),
            Grade.name.asc(),
            Student.student_number.asc(),
            Issuance.issued_at.asc(),
            Issuance.id.asc(),
            IssuanceItem.id.asc(),
        )
    )

    if student_status != "all":
        query = query.where(Student.status == student_status)

    rows = list((await session.execute(query)).all())
    variant_names_by_item_id = await load_variant_names_by_item_id(
        session,
        [int(row.item_id) for row in rows if row.item_id is not None],
    )

    records: list[UniformIssueRecord] = []
    for row in rows:
        student_name = f"{row.first_name or ''} {row.last_name or ''}".strip()
        records.append(
            UniformIssueRecord(
                student_id=int(row.student_id),
                student_number=str(row.student_number or ""),
                student_name=student_name,
                grade=str(row.grade_name or ""),
                student_status=str(row.student_status or ""),
                issuance_id=int(row.issuance_id),
                issuance_number=str(row.issuance_number or ""),
                issuance_type=str(row.issuance_type or ""),
                reservation_id=int(row.reservation_id) if row.reservation_id is not None else None,
                issued_at=row.issued_at,
                issued_by_name=str(row.issued_by_name or ""),
                notes=str(row.notes or ""),
                item_id=int(row.item_id),
                item_sku=str(row.item_sku or ""),
                item_name=str(row.item_name or ""),
                variant_names=variant_names_by_item_id.get(int(row.item_id), ""),
                quantity=int(row.quantity or 0),
                unit_cost=as_money(row.unit_cost),
            )
        )
    return records


def build_student_summary_rows(
    records: list[UniformIssueRecord],
) -> list[StudentUniformSummaryRow]:
    by_student: dict[int, dict[str, Any]] = {}

    for record in records:
        bucket = by_student.setdefault(
            record.student_id,
            {
                "student_number": record.student_number,
                "student_name": record.student_name,
                "grade": record.grade,
                "student_status": record.student_status,
                "total_uniform_quantity": 0,
                "first_issued_at": record.issued_at,
                "last_issued_at": record.issued_at,
                "items": defaultdict(int),
            },
        )
        bucket["total_uniform_quantity"] += record.quantity
        if record.issued_at < bucket["first_issued_at"]:
            bucket["first_issued_at"] = record.issued_at
        if record.issued_at > bucket["last_issued_at"]:
            bucket["last_issued_at"] = record.issued_at
        bucket["items"][(record.item_sku, record.item_name)] += record.quantity

    rows: list[StudentUniformSummaryRow] = []
    for data in by_student.values():
        item_entries = sorted(
            data["items"].items(),
            key=lambda item: (item[0][1], item[0][0]),
        )
        issued_uniforms = "; ".join(
            f"{item_name} ({item_sku}) x{quantity}"
            for (item_sku, item_name), quantity in item_entries
        )
        rows.append(
            StudentUniformSummaryRow(
                student_number=data["student_number"],
                student_name=data["student_name"],
                grade=data["grade"],
                student_status=data["student_status"],
                distinct_uniform_items=len(data["items"]),
                total_uniform_quantity=int(data["total_uniform_quantity"]),
                first_issued_at=dt_str(data["first_issued_at"]),
                last_issued_at=dt_str(data["last_issued_at"]),
                issued_uniforms=issued_uniforms,
            )
        )

    return rows


def build_student_item_rows(
    records: list[UniformIssueRecord],
) -> list[StudentUniformItemRow]:
    by_student_item: dict[tuple[int, int], dict[str, Any]] = {}

    for record in records:
        key = (record.student_id, record.item_id)
        bucket = by_student_item.setdefault(
            key,
            {
                "student_number": record.student_number,
                "student_name": record.student_name,
                "grade": record.grade,
                "student_status": record.student_status,
                "item_sku": record.item_sku,
                "item_name": record.item_name,
                "variant_names": record.variant_names,
                "total_quantity_issued": 0,
                "issue_events_count": 0,
                "first_issued_at": record.issued_at,
                "last_issued_at": record.issued_at,
            },
        )
        bucket["total_quantity_issued"] += record.quantity
        bucket["issue_events_count"] += 1
        if record.issued_at < bucket["first_issued_at"]:
            bucket["first_issued_at"] = record.issued_at
        if record.issued_at > bucket["last_issued_at"]:
            bucket["last_issued_at"] = record.issued_at

    rows: list[StudentUniformItemRow] = []
    for data in by_student_item.values():
        rows.append(
            StudentUniformItemRow(
                student_number=data["student_number"],
                student_name=data["student_name"],
                grade=data["grade"],
                student_status=data["student_status"],
                item_sku=data["item_sku"],
                item_name=data["item_name"],
                variant_names=data["variant_names"],
                total_quantity_issued=int(data["total_quantity_issued"]),
                issue_events_count=int(data["issue_events_count"]),
                first_issued_at=dt_str(data["first_issued_at"]),
                last_issued_at=dt_str(data["last_issued_at"]),
            )
        )

    return rows


def build_movement_rows(
    records: list[UniformIssueRecord],
) -> list[StudentUniformMovementRow]:
    rows = [
        StudentUniformMovementRow(
            issuance_number=record.issuance_number,
            issued_at=dt_str(record.issued_at),
            issuance_type=record.issuance_type,
            student_number=record.student_number,
            student_name=record.student_name,
            grade=record.grade,
            student_status=record.student_status,
            item_sku=record.item_sku,
            item_name=record.item_name,
            variant_names=record.variant_names,
            quantity=record.quantity,
            unit_cost=money_str(record.unit_cost),
            issued_by_name=record.issued_by_name,
            reservation_id=str(record.reservation_id or ""),
            notes=record.notes,
        )
        for record in records
    ]
    return rows


def to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [row.__dict__.copy() for row in rows]


def build_summary_payload(
    *,
    records: list[UniformIssueRecord],
    student_rows: list[StudentUniformSummaryRow],
    item_rows: list[StudentUniformItemRow],
    category_name: str,
) -> dict[str, Any]:
    unique_issuance_ids = {record.issuance_id for record in records}
    return {
        "category_name": category_name,
        "student_count": len(student_rows),
        "issuance_count": len(unique_issuance_ids),
        "issuance_item_rows": len(records),
        "student_item_rows": len(item_rows),
        "total_quantity_issued": sum(record.quantity for record in records),
    }


async def run_export(args: argparse.Namespace) -> int:
    database_url, source_name = resolve_database_url(args.database_url)
    engine = create_async_engine(database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            records = await load_uniform_issue_records(
                session,
                category_name=args.category_name,
                student_status=args.student_status,
            )

        student_rows = build_student_summary_rows(records)
        item_rows = build_student_item_rows(records)
        movement_rows = build_movement_rows(records)
        summary = build_summary_payload(
            records=records,
            student_rows=student_rows,
            item_rows=item_rows,
            category_name=args.category_name,
        )

        output_dir = (
            Path(args.output_dir)
            if args.output_dir
            else build_default_output_dir(args.category_name)
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        written_files: list[Path] = []

        if args.format in {"csv", "both"}:
            students_csv = output_dir / "student_uniforms_by_student.csv"
            write_csv(
                students_csv,
                to_dicts(student_rows),
                [
                    "student_number",
                    "student_name",
                    "grade",
                    "student_status",
                    "distinct_uniform_items",
                    "total_uniform_quantity",
                    "first_issued_at",
                    "last_issued_at",
                    "issued_uniforms",
                ],
            )
            written_files.append(students_csv)

            student_items_csv = output_dir / "student_uniforms_by_item.csv"
            write_csv(
                student_items_csv,
                to_dicts(item_rows),
                [
                    "student_number",
                    "student_name",
                    "grade",
                    "student_status",
                    "item_sku",
                    "item_name",
                    "variant_names",
                    "total_quantity_issued",
                    "issue_events_count",
                    "first_issued_at",
                    "last_issued_at",
                ],
            )
            written_files.append(student_items_csv)

            movement_csv = output_dir / "student_uniform_issue_movements.csv"
            write_csv(
                movement_csv,
                to_dicts(movement_rows),
                [
                    "issuance_number",
                    "issued_at",
                    "issuance_type",
                    "student_number",
                    "student_name",
                    "grade",
                    "student_status",
                    "item_sku",
                    "item_name",
                    "variant_names",
                    "quantity",
                    "unit_cost",
                    "issued_by_name",
                    "reservation_id",
                    "notes",
                ],
            )
            written_files.append(movement_csv)

        if args.format in {"json", "both"}:
            json_path = output_dir / "export.json"
            payload = {
                "generated_at": datetime.now(UTC).isoformat(),
                "database_source": source_name,
                "filters": {
                    "category_name": args.category_name,
                    "student_status": args.student_status,
                },
                "summary": summary,
                "students": to_dicts(student_rows),
                "student_items": to_dicts(item_rows),
                "movements": to_dicts(movement_rows),
            }
            json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            written_files.append(json_path)

        print(f"Category: {args.category_name}")
        print(f"Students exported: {summary['student_count']}")
        print(f"Issuances considered: {summary['issuance_count']}")
        print(f"Issuance rows considered: {summary['issuance_item_rows']}")
        print(f"Total quantity issued: {summary['total_quantity_issued']}")
        print(f"Output dir: {output_dir}")
        for path in written_files:
            print(f" - {path}")

        if not records:
            print("No completed student uniform issuances matched the filters.")
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
