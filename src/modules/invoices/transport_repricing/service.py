"""Atomic repricing of generated transport invoices, including paid invoices."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit.service import AuditService
from src.core.exceptions import ValidationError
from src.modules.billing_accounts.locking import lock_record_accounts
from src.modules.discounts.models import Discount
from src.modules.invoices.models import Invoice, InvoiceLine
from src.modules.invoices.service import InvoiceService
from src.modules.invoices.transport_repricing.models import TransportRepricing
from src.modules.invoices.transport_repricing.schemas import RepricingPreview, RepricingRequest
from src.modules.payments.models import CreditAllocation, CreditAllocationReversal
from src.modules.payments.service import PaymentService
from src.modules.students.models import Student
from src.modules.terms.models import Term, TermStatus, TransportPricing, TransportZone
from src.shared.utils.money import round_money

ZERO = Decimal("0.00")


@dataclass
class RepricingPlan:
    invoice: Invoice
    line: InvoiceLine
    zone_id: int
    discounts: list[tuple[Discount, Decimal]]
    releases: list[tuple[CreditAllocation, Decimal]]
    preview: RepricingPreview


class TransportRepricingService:
    def __init__(self, db: AsyncSession, *, actor_is_super_admin: bool = False):
        self.db = db
        self.actor_is_super_admin = actor_is_super_admin
        self.invoices = InvoiceService(db)
        self.payments = PaymentService(db)
        self.audit = AuditService(db)

    async def preview(self, invoice_id: int) -> RepricingPreview:
        return (await self._plan(invoice_id)).preview

    async def _plan(self, invoice_id: int) -> RepricingPlan:
        # The same account lock is used by allocations, refunds, transfers and profile edits.
        await lock_record_accounts(self.db, [(Invoice, invoice_id)])
        invoice = await self.invoices.get_invoice_by_id(invoice_id)
        if invoice.invoice_type != "transport" or invoice.status not in (
            "issued",
            "partially_paid",
            "paid",
        ):
            raise ValidationError("Select an issued transport invoice to recalculate")
        if invoice.status == "paid" and not self.actor_is_super_admin:
            raise ValidationError("Only SuperAdmin can recalculate a paid invoice")
        term = await self.db.scalar(
            select(Term)
            .where(Term.id == invoice.term_id)
            .execution_options(populate_existing=True)
            .with_for_update(read=True)
        )
        if term is None or term.status != TermStatus.ACTIVE.value:
            raise ValidationError("Transport can only be recalculated for the active term")
        student = await self.db.scalar(
            select(Student)
            .where(Student.id == invoice.student_id)
            .execution_options(populate_existing=True)
        )
        if student.billing_account_id != invoice.billing_account_id:
            raise ValidationError("Student and invoice billing accounts do not match")
        if student.status != "active":
            raise ValidationError("Transport can only be recalculated for an active student")
        zone = (
            await self.db.get(TransportZone, student.transport_zone_id)
            if student.transport_zone_id
            else None
        )
        if zone is None:
            raise ValidationError("Set the student's new transport zone first")
        pricing = await self.db.scalar(
            select(TransportPricing)
            .where(
                TransportPricing.term_id == term.id,
                TransportPricing.zone_id == zone.id,
            )
            .execution_options(populate_existing=True)
            .with_for_update(read=True)
        )
        if pricing is None or pricing.transport_fee_amount < 0:
            raise ValidationError("Set a transport price for this zone and term first")
        # Generated term invoices have one zone-priced service with quantity one.
        # Custom multi-line invoices require a separate explicit correction workflow.
        if len(invoice.lines) != 1:
            raise ValidationError("Recalculation requires a single whole-term transport line")
        line = invoice.lines[0]
        if (
            line.quantity != 1
            or not line.kit
            or line.kit.price_type != "by_zone"
            or line.kit.item_type != "service"
        ):
            raise ValidationError("The invoice does not contain a whole-term zone-priced service")
        discounts = list(
            (
                await self.db.scalars(
                    select(Discount)
                    .where(Discount.invoice_line_id == line.id)
                    .order_by(Discount.id)
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        manual_discount = line.discount_amount - sum((d.calculated_amount for d in discounts), ZERO)
        if manual_discount < 0:
            raise ValidationError("Resolve inconsistent invoice discounts before recalculating")
        price = round_money(pricing.transport_fee_amount)
        recalculated = []
        for discount in discounts:
            if discount.value_type == "percentage":
                amount = round_money(price * discount.value / 100)
            elif discount.value_type == "fixed":
                amount = min(round_money(discount.value), price)
            else:
                raise ValidationError("Unsupported invoice discount type")
            recalculated.append((discount, amount))
        new_discount = round_money(manual_discount + sum((a for _, a in recalculated), ZERO))
        if new_discount > price or new_discount < 0:
            raise ValidationError("Existing discounts exceed the new fee. Adjust discounts first")
        new_total = round_money(price - new_discount)
        adjustment = round_money(line.adjustment_amount)
        if new_total < adjustment:
            raise ValidationError("Existing invoice adjustments exceed the new fee")
        allocations = list(
            (
                await self.db.scalars(
                    select(CreditAllocation)
                    .where(CreditAllocation.invoice_id == invoice.id)
                    .order_by(CreditAllocation.created_at.desc(), CreditAllocation.id.desc())
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        paid = round_money(sum((a.amount for a in allocations), ZERO))
        if (
            paid != invoice.paid_total
            or paid != line.paid_amount
            or any(
                a.billing_account_id != invoice.billing_account_id
                or a.invoice_line_id not in (None, line.id)
                or a.amount < 0
                for a in allocations
            )
        ):
            raise ValidationError("Resolve inconsistent invoice allocations before recalculating")
        released = round_money(max(ZERO, paid - (new_total - adjustment)))
        remaining = released
        releases = []
        for allocation in allocations:
            amount = min(remaining, allocation.amount)
            if amount > 0:
                releases.append((allocation, amount))
                remaining -= amount
        balance = await self.payments.get_student_balance(student.id)
        credit = round_money(
            balance.total_payments - balance.total_refunded - balance.total_allocated
        )
        preview = RepricingPreview(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            student_name=student.full_name,
            term_name=term.display_name,
            zone_name=zone.zone_name,
            price_before=line.unit_price,
            price_after=price,
            discount_before=line.discount_amount,
            discount_after=new_discount,
            total_before=invoice.total,
            total_after=new_total,
            paid_before=paid,
            paid_after=paid - released,
            due_before=invoice.amount_due,
            due_after=new_total - adjustment - paid + released,
            credit_before=credit,
            credit_after=credit + released,
            released_credit=released,
            changed=price != line.unit_price or new_discount != line.discount_amount,
        )
        fingerprint = {
            "preview": preview.model_dump(mode="json"),
            "zone_id": zone.id,
            "account_id": invoice.billing_account_id,
            "status": invoice.status,
            "line_id": line.id,
            "adjustment": str(adjustment),
            "discounts": [
                (d.id, d.value_type, str(d.value), str(d.calculated_amount)) for d in discounts
            ],
            "allocations": [
                (a.id, str(a.amount), a.source_payment_id, a.created_at.isoformat())
                for a in allocations
            ],
        }
        preview.preview_token = hashlib.sha256(
            json.dumps(fingerprint, sort_keys=True).encode()
        ).hexdigest()
        return RepricingPlan(invoice, line, zone.id, recalculated, releases, preview)

    async def apply(
        self, invoice_id: int, data: RepricingRequest, user_id: int
    ) -> RepricingPreview:
        plan = await self._plan(invoice_id)
        preview = plan.preview
        if data.preview_token != preview.preview_token:
            raise ValidationError(
                "Invoice, zone or payments changed. Review the recalculation again"
            )
        if not preview.changed:
            return preview
        invoice, line = plan.invoice, plan.line
        now = datetime.now(UTC)
        self.db.add(
            TransportRepricing(
                invoice_id=invoice.id,
                invoice_line_id=line.id,
                zone_id=plan.zone_id,
                gross_before=line.line_total,
                net_before=line.net_amount,
                gross_after=preview.price_after,
                net_after=preview.total_after,
                released_credit=preview.released_credit,
                reason=data.reason,
                created_by_id=user_id,
                created_at=now,
            )
        )
        for allocation, amount in plan.releases:
            self.db.add(
                CreditAllocationReversal(
                    credit_allocation_id=allocation.id,
                    amount=amount,
                    reason=data.reason,
                    reversed_by_id=user_id,
                    reversed_at=now,
                )
            )
            allocation.amount = round_money(allocation.amount - amount)
        line.unit_price = preview.price_after
        line.discount_amount = preview.discount_after
        for discount, amount in plan.discounts:
            discount.calculated_amount = amount
        self.invoices._recalculate_line(line)
        await self.db.flush()
        await self.payments._update_invoice_paid_amounts(invoice)
        await self.payments._update_billing_account_balance_cache(invoice.billing_account_id)
        await self.audit.log(
            action="invoice.recalculate_transport",
            entity_type="Invoice",
            entity_id=invoice.id,
            user_id=user_id,
            comment=data.reason,
            old_values={
                "price": str(preview.price_before),
                "discount": str(preview.discount_before),
                "total": str(preview.total_before),
                "paid": str(preview.paid_before),
            },
            new_values={
                **preview.model_dump(mode="json"),
                "zone_id": plan.zone_id,
                "reversals": [
                    {"allocation_id": a.id, "amount": str(amount)} for a, amount in plan.releases
                ],
            },
        )
        await self.db.commit()
        return preview
