"""Whole-term corrections preserve cash, historical revenue and concurrency tokens."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from src.core.audit.models import AuditLog
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import UserRole
from src.core.exceptions import ValidationError
from src.main import app
from src.modules.discounts.models import Discount
from src.modules.invoices.transport_repricing.models import TransportRepricing
from src.modules.invoices.transport_repricing.schemas import RepricingRequest
from src.modules.invoices.transport_repricing.service import TransportRepricingService
from src.modules.payments.models import CreditAllocationReversal, Payment
from src.modules.payments.schemas import AllocationCreate, PaymentCreate
from src.modules.payments.service import PaymentService
from src.modules.reports.service import ReportsService
from src.modules.terms.models import Term, TransportPricing, TransportZone
from tests.modules.payments.test_payments import TestPaymentService as PaymentFixtures


async def build_repricing_data(db_session, paid=Decimal("5000"), price=Decimal("3000")):
    data = await PaymentFixtures()._setup_test_data(db_session)
    invoice = data["invoice1"]
    zone = TransportZone(zone_name="New zone", zone_code="NEW")
    term = Term(
        year=2026,
        term_number=3,
        display_name="2026-T3",
        status="Active",
        created_by_id=data["user"].id,
    )
    db_session.add_all([zone, term])
    await db_session.flush()
    data["student"].transport_zone_id = zone.id
    data["kit"].price_type = "by_zone"
    invoice.invoice_type = "transport"
    invoice.term_id = term.id
    line = invoice.lines[0]
    line.quantity = 1
    line.unit_price = Decimal("5000")
    pricing = TransportPricing(term_id=term.id, zone_id=zone.id, transport_fee_amount=price)
    db_session.add(pricing)
    # Other family invoices stay unchanged and must not receive released credit automatically.
    await db_session.commit()
    payments = PaymentService(db_session)
    payment = await payments.create_payment(
        PaymentCreate(
            student_id=data["student"].id,
            amount=Decimal("6000"),
            payment_method="mpesa",
            reference="TRANSPORT-TEST",
            payment_date=date(2026, 9, 1),
        ),
        data["user"].id,
    )
    payment.status = "completed"
    await db_session.flush()
    await payments._update_billing_account_balance_cache(invoice.billing_account_id)
    await db_session.commit()
    allocation = None
    if paid:
        allocation = await payments.allocate_manual(
            AllocationCreate(
                student_id=data["student"].id,
                invoice_id=invoice.id,
                amount=paid,
            ),
            data["user"].id,
        )
        allocation.created_at = datetime(2026, 9, 1, tzinfo=UTC)
        await db_session.commit()
    return {
        **data,
        "invoice": invoice,
        "line": line,
        "zone": zone,
        "term": term,
        "pricing": pricing,
        "payment": payment,
        "allocation": allocation,
    }


def request(preview):
    return RepricingRequest(preview_token=preview.preview_token, reason="Moved home; whole term")


@pytest.mark.parametrize(
    "paid,price,expected_due,expected_credit",
    [
        (5000, 3000, 0, 3000),
        (2000, 3000, 1000, 4000),
        (5000, 7000, 2000, 1000),
        (0, 3000, 3000, 6000),
        (5000, 0, 0, 6000),
    ],
)
async def test_reprice_keeps_cash_and_returns_only_excess(
    db_session, paid, price, expected_due, expected_credit
):
    data = await build_repricing_data(db_session, Decimal(paid), Decimal(price))
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    invoice = data["invoice"]
    identity = (invoice.invoice_number, invoice.issue_date, data["payment"].payment_date)
    before = await db_session.scalar(select(func.count()).select_from(AuditLog))
    preview = await service.preview(invoice.id)
    assert invoice.total == 5000
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == before
    assert preview.due_after == expected_due
    assert preview.credit_after == expected_credit
    await service.apply(invoice.id, request(preview), data["user"].id)
    await db_session.refresh(invoice)
    assert (invoice.invoice_number, invoice.issue_date, data["payment"].payment_date) == identity
    assert invoice.total == price
    assert invoice.amount_due == expected_due
    assert invoice.paid_total == min(paid, price)
    balance = await service.payments.get_student_balance(data["student"].id)
    assert balance.available_balance == expected_credit
    assert balance.total_payments == 6000
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 1
    assert await db_session.scalar(select(func.count()).select_from(TransportRepricing)) == 1
    if data["allocation"]:
        await db_session.refresh(data["allocation"])
        assert data["allocation"].created_at.date() == date(2026, 9, 1)
        assert data["allocation"].amount == min(paid, price)
    assert data["invoice2"].paid_total == 0


async def test_prior_cash_report_unchanged_and_reversal_reported_today(db_session):
    data = await build_repricing_data(db_session)
    reports = ReportsService(db_session)
    before = await reports._profit_loss_period_cash_allocated(date(2026, 9, 1), date(2026, 9, 30))
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    preview = await service.preview(data["invoice"].id)
    await service.apply(data["invoice"].id, request(preview), data["user"].id)
    after = await reports._profit_loss_period_cash_allocated(date(2026, 9, 1), date(2026, 9, 30))
    assert before["net_revenue"] == after["net_revenue"] == 5000
    assert before["gross_revenue"] == after["gross_revenue"] == 5000
    reversal = await db_session.scalar(select(CreditAllocationReversal))
    assert reversal.refund_id is None
    day = reversal.reversed_at.date()
    correction = await reports._profit_loss_period_cash_allocated(day, day)
    assert correction["net_revenue"] == -2000


@pytest.mark.parametrize("change", ["price", "zone", "allocation", "discount"])
async def test_stale_preview_rejected(db_session, change):
    data = await build_repricing_data(db_session)
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    preview = await service.preview(data["invoice"].id)
    if change == "price":
        data["pricing"].transport_fee_amount = 4000
    elif change == "zone":
        data["student"].transport_zone_id = None
    elif change == "allocation":
        await service.payments.delete_allocation(data["allocation"].id, data["user"].id)
    else:
        data["line"].discount_amount = 100
    await db_session.commit()
    with pytest.raises(ValidationError):
        await service.apply(data["invoice"].id, request(preview), data["user"].id)
    assert await db_session.scalar(select(func.count()).select_from(TransportRepricing)) == 0


async def test_percentage_and_fixed_discounts_recalculate(db_session):
    data = await build_repricing_data(db_session)
    line = data["line"]
    discount = Discount(
        invoice_line_id=line.id,
        value_type="percentage",
        value=10,
        calculated_amount=500,
        applied_by_id=data["user"].id,
    )
    fixed = Discount(
        invoice_line_id=line.id,
        value_type="fixed",
        value=100,
        calculated_amount=100,
        applied_by_id=data["user"].id,
    )
    db_session.add_all([discount, fixed])
    # Make the pre-existing 600 discount consistent with allocations first.
    await PaymentService(db_session).delete_allocation(data["allocation"].id, data["user"].id)
    line.discount_amount = 600
    line.net_amount = 4400
    line.remaining_amount = 4400
    data["invoice"].discount_total = 600
    data["invoice"].total = data["invoice"].amount_due = 4400
    await db_session.commit()
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    preview = await service.preview(data["invoice"].id)
    assert preview.discount_after == 400
    assert preview.total_after == 2600
    await service.apply(data["invoice"].id, request(preview), data["user"].id)
    assert discount.calculated_amount == 300
    assert fixed.calculated_amount == 100


async def test_repeated_confirmation_cannot_release_twice(db_session):
    data = await build_repricing_data(db_session)
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    preview = await service.preview(data["invoice"].id)
    await service.apply(data["invoice"].id, request(preview), data["user"].id)
    with pytest.raises(ValidationError, match="changed"):
        await service.apply(data["invoice"].id, request(preview), data["user"].id)
    assert await db_session.scalar(select(func.sum(CreditAllocationReversal.amount))) == 2000
    assert not (await service.preview(data["invoice"].id)).changed


async def test_failure_rolls_back_price_reversals_and_balance(db_session, monkeypatch):
    data = await build_repricing_data(db_session)
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    invoice_id, account_student_id = data["invoice"].id, data["student"].id
    preview = await service.preview(invoice_id)
    monkeypatch.setattr(service.audit, "log", AsyncMock(side_effect=RuntimeError("audit failed")))
    with pytest.raises(RuntimeError):
        await service.apply(invoice_id, request(preview), data["user"].id)
    await db_session.rollback()
    invoice = await service.invoices.get_invoice_by_id(invoice_id)
    assert invoice.total == invoice.paid_total == 5000
    assert (
        await service.payments.get_student_balance(account_student_id)
    ).available_balance == 1000
    assert await db_session.scalar(select(func.count()).select_from(TransportRepricing)) == 0
    assert await db_session.scalar(select(func.count()).select_from(CreditAllocationReversal)) == 0


@pytest.mark.parametrize(
    "role,allowed",
    [(UserRole.SUPER_ADMIN, True), (UserRole.ADMIN, True), (UserRole.ACCOUNTANT, False)],
)
async def test_endpoint_permissions(db_session, client, role, allowed):
    data = await build_repricing_data(db_session, Decimal("2000"))
    data["user"].role = role
    app.dependency_overrides[get_current_user] = lambda: data["user"]
    url = f"/api/v1/invoices/{data['invoice'].id}/recalculate-transport"
    response = await client.post(url + "/preview")
    assert response.status_code == (200 if allowed else 403)
    if allowed:
        response = await client.post(
            url,
            json={
                "preview_token": response.json()["data"]["preview_token"],
                "reason": "Moved home",
            },
        )
        assert response.status_code == 200
    else:
        response = await client.post(url, json={"preview_token": "a" * 64, "reason": "Moved home"})
        assert response.status_code == 403


@pytest.mark.parametrize(
    "invalid",
    [
        "closed_term",
        "missing_zone",
        "missing_price",
        "cancelled",
        "custom_quantity",
        "excess_discount",
    ],
)
async def test_invalid_repricing_is_read_only(db_session, invalid):
    data = await build_repricing_data(db_session)
    if invalid == "closed_term":
        data["term"].status = "Closed"
    elif invalid == "missing_zone":
        data["student"].transport_zone_id = None
    elif invalid == "missing_price":
        await db_session.delete(data["pricing"])
    elif invalid == "cancelled":
        data["invoice"].status = "cancelled"
    elif invalid == "custom_quantity":
        data["line"].quantity = 2
    else:
        data["line"].discount_amount = 4000
    await db_session.commit()
    with pytest.raises(ValidationError):
        await TransportRepricingService(db_session, actor_is_super_admin=True).preview(
            data["invoice"].id
        )
    assert await db_session.scalar(select(func.count()).select_from(TransportRepricing)) == 0
    assert data["allocation"].amount == 5000


async def test_multiple_reprices_preserve_discounted_cash_history(db_session):
    data = await build_repricing_data(db_session, Decimal("0"))
    line, invoice = data["line"], data["invoice"]
    discount = Discount(
        invoice_line_id=line.id,
        value_type="percentage",
        value=10,
        calculated_amount=500,
        applied_by_id=data["user"].id,
    )
    db_session.add(discount)
    line.discount_amount = 500
    line.net_amount = line.remaining_amount = 4500
    invoice.discount_total = 500
    invoice.total = invoice.amount_due = 4500
    await db_session.commit()
    allocation = await PaymentService(db_session).allocate_manual(
        AllocationCreate(
            student_id=data["student"].id,
            invoice_id=invoice.id,
            invoice_line_id=line.id,
            amount=Decimal("4500"),
        ),
        data["user"].id,
    )
    allocation.created_at = datetime(2026, 9, 1, tzinfo=UTC)
    await db_session.commit()
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    for price in (3000, 2000, 6000, 0):
        data["pricing"].transport_fee_amount = price
        await db_session.commit()
        preview = await service.preview(invoice.id)
        await service.apply(invoice.id, request(preview), data["user"].id)
    reports = ReportsService(db_session)
    september = await reports._profit_loss_period_cash_allocated(
        date(2026, 9, 1), date(2026, 9, 30)
    )
    assert september["gross_revenue"] == 5000
    assert september["net_revenue"] == 4500
    assert september["total_discounts"] == 500
    day = (await db_session.scalar(select(CreditAllocationReversal))).reversed_at.date()
    corrections = await reports._profit_loss_period_cash_allocated(day, day)
    assert corrections["gross_revenue"] == -5000
    assert corrections["net_revenue"] == -4500
    assert (
        await service.payments.get_student_balance(data["student"].id)
    ).available_balance == 6000


async def test_admin_cannot_reprice_a_fully_paid_invoice(db_session, client):
    data = await build_repricing_data(db_session)
    data["user"].role = UserRole.ADMIN
    app.dependency_overrides[get_current_user] = lambda: data["user"]
    response = await client.post(
        f"/api/v1/invoices/{data['invoice'].id}/recalculate-transport/preview"
    )
    assert response.status_code == 422
    assert "SuperAdmin" in response.text


async def test_fixed_discount_is_capped_at_new_price(db_session):
    data = await build_repricing_data(db_session, Decimal("0"), Decimal("50"))
    line = data["line"]
    discount = Discount(
        invoice_line_id=line.id,
        value_type="fixed",
        value=100,
        calculated_amount=100,
        applied_by_id=data["user"].id,
    )
    db_session.add(discount)
    line.discount_amount = 100
    line.net_amount = line.remaining_amount = 4900
    data["invoice"].discount_total = 100
    data["invoice"].total = data["invoice"].amount_due = 4900
    await db_session.commit()
    service = TransportRepricingService(db_session, actor_is_super_admin=True)
    preview = await service.preview(data["invoice"].id)
    assert preview.total_after == 0
    assert preview.discount_after == 50
    await service.apply(data["invoice"].id, request(preview), data["user"].id)
    assert discount.calculated_amount == 50
