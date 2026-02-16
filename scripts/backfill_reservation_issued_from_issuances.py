#!/usr/bin/env python3
"""
Backfill reservation_items.quantity_issued from actual COMPLETED issuances.

Why:
Older versions cancelled issuances returned stock but did not roll back
reservation_items.quantity_issued. This makes Reservations UI show wrong "issued"
numbers even though the issuance is cancelled.

Strategy (safe + idempotent):
- Find ReservationItems affected by CANCELLED issuances (or by filters).
- For each ReservationItem, recompute quantity_issued as:
    SUM(issuance_items.quantity) for issuances.status == 'completed'
    where issuance_items.reservation_item_id == reservation_item.id
- Update Reservation.status accordingly (unless it is already cancelled).

Usage:
  python3 scripts/backfill_reservation_issued_from_issuances.py --dry-run --issuance-id 123
  python3 scripts/backfill_reservation_issued_from_issuances.py --confirm --issuance-id 123

Note:
  This script does NOT touch stock. It only fixes reservation progress counters.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database.session import async_session
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.inventory.models import Issuance, IssuanceItem, IssuanceStatus
from src.modules.reservations.models import Reservation, ReservationItem, ReservationStatus


def _calc_reservation_status(items: list[ReservationItem]) -> str:
    total_required = sum(int(i.quantity_required) for i in items)
    total_issued = sum(int(i.quantity_issued) for i in items)
    if total_required > 0 and total_issued >= total_required:
        return ReservationStatus.FULFILLED.value
    if total_issued > 0:
        return ReservationStatus.PARTIAL.value
    return ReservationStatus.PENDING.value


async def _get_affected_reservation_item_ids(
    session: AsyncSession,
    *,
    issuance_id: int | None,
    reservation_id: int | None,
) -> list[int]:
    q = (
        select(func.distinct(IssuanceItem.reservation_item_id))
        .select_from(IssuanceItem)
        .join(Issuance, Issuance.id == IssuanceItem.issuance_id)
        .where(IssuanceItem.reservation_item_id.is_not(None))
        .where(Issuance.status == IssuanceStatus.CANCELLED.value)
    )
    if issuance_id is not None:
        q = q.where(Issuance.id == issuance_id)
    if reservation_id is not None:
        q = q.where(Issuance.reservation_id == reservation_id)
    rows = (await session.execute(q)).all()
    return [int(r[0]) for r in rows if r[0] is not None]


async def _recompute_quantity_issued(
    session: AsyncSession, reservation_item_id: int
) -> int:
    q = (
        select(func.coalesce(func.sum(IssuanceItem.quantity), 0))
        .select_from(IssuanceItem)
        .join(Issuance, Issuance.id == IssuanceItem.issuance_id)
        .where(IssuanceItem.reservation_item_id == reservation_item_id)
        .where(Issuance.status == IssuanceStatus.COMPLETED.value)
    )
    value = (await session.execute(q)).scalar_one()
    return int(value or 0)


async def backfill(
    session: AsyncSession,
    *,
    issuance_id: int | None,
    reservation_id: int | None,
    dry_run: bool,
) -> None:
    affected_item_ids = await _get_affected_reservation_item_ids(
        session, issuance_id=issuance_id, reservation_id=reservation_id
    )
    affected_item_ids = sorted(set(affected_item_ids))
    if not affected_item_ids:
        print("✅ Nothing to fix: no ReservationItems referenced by cancelled issuances.")
        return

    print(f"🔎 Affected ReservationItems: {len(affected_item_ids)}")

    changed_items = 0
    touched_reservation_ids: set[int] = set()

    for rid in affected_item_ids:
        res_item = (
            await session.execute(
                select(ReservationItem)
                .where(ReservationItem.id == rid)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not res_item:
            raise NotFoundError(f"ReservationItem with id {rid} not found")

        correct_issued = await _recompute_quantity_issued(session, rid)
        current_issued = int(res_item.quantity_issued)

        if correct_issued < 0:
            raise ValidationError(
                f"Computed issued is negative for ReservationItem {rid}: {correct_issued}"
            )
        if correct_issued > int(res_item.quantity_required):
            # Not necessarily fatal (partial business changes), but suspicious.
            print(
                f"⚠️  ReservationItem {rid}: computed issued {correct_issued} "
                f"> required {int(res_item.quantity_required)}"
            )

        if current_issued != correct_issued:
            changed_items += 1
            print(
                f"- ReservationItem {rid}: issued {current_issued} -> {correct_issued} "
                f"(reservation_id={int(res_item.reservation_id)}, item_id={int(res_item.item_id)})"
            )
            res_item.quantity_issued = correct_issued
            touched_reservation_ids.add(int(res_item.reservation_id))

    # Recompute reservation status for touched reservations
    changed_reservations = 0
    for res_id in sorted(touched_reservation_ids):
        reservation = (
            await session.execute(
                select(Reservation)
                .where(Reservation.id == res_id)
                .options(selectinload(Reservation.items))
            )
        ).scalar_one_or_none()
        if not reservation:
            raise NotFoundError(f"Reservation with id {res_id} not found")
        if reservation.status == ReservationStatus.CANCELLED.value:
            continue
        before = reservation.status
        after = _calc_reservation_status(list(reservation.items or []))
        if before != after:
            changed_reservations += 1
            print(f"- Reservation {res_id}: status {before} -> {after}")
            reservation.status = after

    if dry_run:
        await session.rollback()
        print(
            f"\n🧪 DRY-RUN: would change {changed_items} reservation_items and "
            f"{changed_reservations} reservations."
        )
        return

    await session.commit()
    print(
        f"\n✅ Applied: changed {changed_items} reservation_items and "
        f"{changed_reservations} reservations."
    )


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill reservation_items.quantity_issued from completed issuances"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes, rollback at end")
    parser.add_argument("--confirm", action="store_true", help="Apply changes (COMMIT)")
    parser.add_argument("--issuance-id", type=int, default=None, help="Limit to a single issuance id")
    parser.add_argument("--reservation-id", type=int, default=None, help="Limit to a single reservation id")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("❌ ERROR: specify --dry-run or --confirm")
        sys.exit(1)
    if args.dry_run and args.confirm:
        print("❌ ERROR: choose only one of --dry-run / --confirm")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("BACKFILL RESERVATION ISSUED QUANTITIES")
    print("=" * 70)
    print(f"\n🌍 Environment: {settings.app_env}")
    print(
        f"🗄️  DB: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'unknown'}"
    )
    print(f"🔧 Mode: {'DRY-RUN' if args.dry_run else 'APPLY (COMMIT)'}")
    if args.issuance_id is not None:
        print(f"🎯 Filter: issuance_id={args.issuance_id}")
    if args.reservation_id is not None:
        print(f"🎯 Filter: reservation_id={args.reservation_id}")

    if args.confirm:
        print("\n⚠️  This will UPDATE reservation quantities in the database.")
        print("💡 Make a DB backup before running on production.")
        response = input("\n❓ Type 'APPLY RESERVATION BACKFILL' to continue: ")
        if response != "APPLY RESERVATION BACKFILL":
            print("\n❌ Cancelled by user")
            sys.exit(0)

    async with async_session() as session:
        await backfill(
            session,
            issuance_id=args.issuance_id,
            reservation_id=args.reservation_id,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    asyncio.run(main())

