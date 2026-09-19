"""Account-scoped transaction locks for every mutation of the family ledger.

Acquire before reading balances/invoices, keep until the outer operation commits,
and lock multiple accounts in ascending order. Ownership is read again after waiting:
a payment/student may have moved while this transaction waited for its old account.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ValidationError
from src.modules.billing_accounts.models import BillingAccount


async def lock_accounts(db: AsyncSession, account_ids: Iterable[int]) -> None:
    ids = sorted(set(account_ids))
    if not ids:
        return
    with db.no_autoflush:
        rows = list(
            (
                await db.scalars(
                    select(BillingAccount.id)
                    .where(BillingAccount.id.in_(ids))
                    .order_by(BillingAccount.id)
                    .with_for_update()
                )
            ).all()
        )
    if len(rows) != len(ids):
        raise ValidationError("Billing account changed or no longer exists. Retry the operation")


async def lock_record_accounts(
    db: AsyncSession,
    records: Iterable[tuple[type, int]],
    *,
    account_ids: Iterable[int] = (),
) -> None:
    """Resolve owners using scalar reads, lock together, then verify those owners."""
    by_model: dict[type, set[int]] = {}
    for model, record_id in records:
        by_model.setdefault(model, set()).add(record_id)
    snapshots = []
    with db.no_autoflush:
        for model, record_ids in by_model.items():
            query = select(model.id, model.billing_account_id).where(model.id.in_(record_ids))
            owners = dict((await db.execute(query)).all())
            if set(owners) != record_ids or any(owner is None for owner in owners.values()):
                raise NotFoundError(f"{model.__name__} or its billing account not found")
            snapshots.append((query, owners))
        await lock_accounts(
            db,
            [
                *account_ids,
                *(owner for _, owners in snapshots for owner in owners.values()),
            ],
        )
        for query, owners in snapshots:
            if dict((await db.execute(query)).all()) != owners:
                raise ValidationError("Billing account ownership changed. Retry the operation")
