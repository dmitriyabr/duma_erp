"""Preserve allocation dates when correcting the recipient of a payment."""

from collections import deque
from datetime import UTC, datetime

from src.modules.payments.models import CreditAllocation
from src.modules.payments.transfers.schemas import TransferAllocationSlice, TransferInvoiceImpact


def allocation_schedule(
    allocations: list[CreditAllocation],
    impacts: list[TransferInvoiceImpact],
) -> list[TransferAllocationSlice]:
    """Consume original funding lots oldest first; only new credit gets today's date.

    The destination invoice shares are calculated once for the whole payment. Splitting
    those shares into dated lots preserves both that plan and each original timestamp.
    If destination debt is smaller, unused lots become credit, not newly dated income.
    """

    def utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    lots = deque(
        (utc(row.created_at), row.amount)
        for row in sorted(allocations, key=lambda row: (utc(row.created_at), row.id))
    )
    result = []
    for impact in impacts:
        remaining = impact.amount
        while remaining > 0:
            created_at, available = lots.popleft() if lots else (None, remaining)
            amount = min(available, remaining)
            result.append(
                TransferAllocationSlice(
                    invoice_id=impact.invoice_id,
                    amount=amount,
                    created_at=created_at,
                )
            )
            remaining -= amount
            if available > amount:
                lots.appendleft((created_at, available - amount))
    return result
