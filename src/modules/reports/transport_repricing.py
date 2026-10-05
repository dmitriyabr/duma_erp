"""Cash events retain the transport price in force when money was allocated."""

from datetime import UTC, date, datetime
from decimal import Decimal

from src.modules.invoices.models import InvoiceLine
from src.modules.invoices.transport_repricing.models import TransportRepricing
from src.modules.payments.models import CreditAllocation, CreditAllocationReversal
from src.shared.utils.money import round_money


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def transport_cash_totals(
    line: InvoiceLine,
    revisions: list[TransportRepricing],
    allocations: list[tuple[CreditAllocation, Decimal]],
    reversals: list[CreditAllocationReversal],
    date_from: date,
    date_to: date,
) -> tuple[Decimal, Decimal]:
    """Return gross/net from ledger events, without capping history at today's fee.

    Reversals use their original allocation's gross/net ratio, so a subsequent
    price or discount change cannot rewrite a previously reported receipt.
    """

    def ratio_at(allocated_at: datetime) -> Decimal:
        gross, net = line.line_total, line.net_amount
        for revision in revisions:
            if _utc(revision.created_at) > _utc(allocated_at):
                gross, net = revision.gross_before, revision.net_before
                break
        return gross / net if net > 0 else Decimal("1")

    gross = net = Decimal("0.00")
    for allocation, original_amount in allocations:
        if date_from <= _utc(allocation.created_at).date() <= date_to:
            net += original_amount
            gross += round_money(original_amount * ratio_at(allocation.created_at))
    for reversal in reversals:
        if date_from <= _utc(reversal.reversed_at).date() <= date_to:
            net -= reversal.amount
            gross -= round_money(reversal.amount * ratio_at(reversal.allocation.created_at))
    return round_money(gross), round_money(net)
