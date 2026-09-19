"""Pure invoice allocation policy shared by posting and transfer previews."""

from datetime import date
from decimal import Decimal
from itertools import groupby

from src.modules.invoices.models import Invoice, InvoiceType
from src.modules.terms.models import Term, TermStatus
from src.shared.utils.money import round_money


class InvoiceAllocationPolicy:
    """Stateless allocation calculations; never reads or writes the database."""

    @staticmethod
    def _money_to_cents(value: Decimal) -> int:
        return int((round_money(value) * 100).to_integral_value())

    @staticmethod
    def _cents_to_money(value: int) -> Decimal:
        return round_money(Decimal(value) / Decimal("100"))

    def _allocate_proportionally(
        self,
        total: Decimal,
        capacities: dict[int, Decimal],
    ) -> tuple[dict[int, Decimal], Decimal]:
        """Distribute invoice-level paid amount across line capacities by net remaining."""
        allocations = {key: Decimal("0.00") for key in capacities}
        total = round_money(total)
        if total <= 0:
            return allocations, Decimal("0.00")

        capacity_cents = {
            key: max(0, self._money_to_cents(value)) for key, value in capacities.items()
        }
        total_capacity_cents = sum(capacity_cents.values())
        if total_capacity_cents <= 0:
            return allocations, total

        total_cents = max(0, self._money_to_cents(total))
        if total_cents >= total_capacity_cents:
            for key, cents in capacity_cents.items():
                allocations[key] = self._cents_to_money(cents)
            return allocations, self._cents_to_money(total_cents - total_capacity_cents)

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
            allocations[key] = self._cents_to_money(cents)

        return allocations, self._cents_to_money(leftover_cents)

    @staticmethod
    def _allocation_type_bucket(invoice: Invoice) -> int:
        """Put paid activities ahead of every other invoice type."""
        return 0 if invoice.invoice_type == InvoiceType.ACTIVITY.value else 1

    def _allocation_term_bucket(
        self,
        invoice: Invoice,
        active_term: Term | None,
    ) -> tuple[int, int, int]:
        """Return a sortable bucket where older academic debt wins before current debt."""
        term = invoice.term

        if term is not None:
            if active_term is not None:
                invoice_key = (term.year, term.term_number)
                active_key = (active_term.year, active_term.term_number)
                if invoice_key < active_key:
                    bucket = 0
                elif invoice_key == active_key:
                    bucket = 1
                else:
                    bucket = 2
            elif term.status == TermStatus.CLOSED.value:
                bucket = 0
            else:
                bucket = 1
            return (bucket, term.year, term.term_number)

        if active_term is not None and active_term.start_date is not None:
            invoice_date = invoice.due_date or invoice.issue_date
            if invoice_date is not None and invoice_date < active_term.start_date:
                return (0, 9999, 99)

        return (3, 9999, 99)

    def _allocation_priority_key(
        self,
        invoice: Invoice,
        active_term: Term | None,
    ) -> tuple[int, int, int, int, date, int]:
        fallback_date = invoice.due_date or invoice.issue_date or date.max
        return (
            self._allocation_type_bucket(invoice),
            *self._allocation_term_bucket(invoice, active_term),
            fallback_date,
            invoice.id,
        )

    def plan_allocations(
        self, invoices: list[Invoice], active_term: Term | None, amount: Decimal
    ) -> list[tuple[Invoice, Decimal]]:
        remaining = round_money(amount)
        plan = []
        ordered = sorted(invoices, key=lambda row: self._allocation_priority_key(row, active_term))
        for _, group in groupby(
            ordered,
            key=lambda row: (
                self._allocation_type_bucket(row),
                *self._allocation_term_bucket(row, active_term),
            ),
        ):
            if remaining <= 0:
                break
            rows = list(group)
            for invoice in rows:
                if invoice.requires_full_payment and remaining > 0:
                    allocated = min(remaining, round_money(invoice.amount_due))
                    if allocated > 0:
                        plan.append((invoice, allocated))
                        remaining = round_money(remaining - allocated)
            partial = {
                row.id: row for row in rows if not row.requires_full_payment and row.amount_due > 0
            }
            amounts, _ = self._allocate_proportionally(
                remaining, {key: row.amount_due for key, row in partial.items()}
            )
            for key, allocated in amounts.items():
                if allocated > 0:
                    plan.append((partial[key], allocated))
                    remaining = round_money(remaining - allocated)
        return plan
