"""Payment correction integration tests against real allocation and balance services."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from src.core.audit.models import AuditLog
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import UserRole
from src.core.exceptions import ValidationError
from src.main import app
from src.modules.billing_accounts.models import BillingAccount
from src.modules.invoices.models import Invoice
from src.modules.payments.models import (
    CreditAllocation,
    CreditAllocationReversal,
    Payment,
    PaymentRefund,
    PaymentRefundSource,
)
from src.modules.payments.schemas import PaymentCreate
from src.modules.payments.service import PaymentService
from src.modules.payments.transfers.schemas import TransferRequest
from src.modules.payments.transfers.service import PaymentTransferService
from src.modules.students.models import Student
from tests.modules.payments.test_payments import TestPaymentService as PaymentFixtures


async def build_transfer_data(db_session):
    data = await PaymentFixtures()._setup_test_data(db_session)
    student = data["student"]
    account = BillingAccount(
        account_number="FAM-TRANSFER", display_name="Correct family", created_by_id=data["user"].id
    )
    db_session.add(account)
    await db_session.flush()
    target = Student(
        student_number="STU-TRANSFER-2640",
        first_name="Correct",
        last_name="Student",
        gender="male",
        grade_id=student.grade_id,
        billing_account_id=account.id,
        guardian_name="Parent",
        guardian_phone="+254712345678",
        created_by_id=data["user"].id,
    )
    db_session.add(target)
    await db_session.flush()
    invoices = []
    for index, amount in enumerate((Decimal("3000"), Decimal("2000"))):
        invoice = Invoice(
            invoice_number=f"INV-TRANSFER-{index}",
            student_id=target.id,
            billing_account_id=account.id,
            invoice_type="adhoc",
            status="issued",
            issue_date=date.today(),
            subtotal=amount,
            discount_total=0,
            total=amount,
            paid_total=0,
            amount_due=amount,
            created_by_id=data["user"].id,
        )
        db_session.add(invoice)
        invoices.append(invoice)
    await db_session.commit()
    payments = PaymentService(db_session)
    payment = await payments.create_payment(
        PaymentCreate(
            student_id=student.id,
            amount=Decimal("6000"),
            payment_method="mpesa",
            payment_date=date.today(),
            reference="UIIE66RF8K",
        ),
        data["user"].id,
    )
    payment = await payments.complete_payment(payment.id, data["user"].id)
    return {**data, "target": target, "target_invoices": invoices, "payment": payment}


@pytest.fixture
async def transfer_data(db_session):
    return await build_transfer_data(db_session)


def request(preview, target_id):
    return TransferRequest(
        target_student_id=target_id,
        reason="Parent entered 264 instead of 2640",
        preview_token=preview.preview_token,
    )


async def test_preview_is_read_only_and_transfer_preserves_payment(transfer_data, db_session):
    data = transfer_data
    payment = data["payment"]
    original = (
        payment.id,
        payment.payment_number,
        payment.receipt_number,
        payment.reference,
        payment.amount,
        payment.payment_date,
    )
    service = PaymentTransferService(db_session)
    before_audit = await db_session.scalar(select(func.count()).select_from(AuditLog))
    preview = await service.preview(payment.id, data["target"].id)
    assert [row.amount for row in preview.new_allocations] == [Decimal("3000"), Decimal("2000")]
    assert sum(row.amount for row in preview.removed_allocations) == Decimal("6000")
    assert preview.target_credit_after == Decimal("1000")
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == before_audit
    assert payment.student_id == data["student"].id
    result = await service.transfer(
        payment.id, request(preview, data["target"].id), data["user"].id
    )
    await db_session.refresh(payment)
    assert original == (
        payment.id,
        payment.payment_number,
        payment.receipt_number,
        payment.reference,
        payment.amount,
        payment.payment_date,
    )
    assert payment.student_id == data["target"].id
    assert payment.billing_account_id == data["target"].billing_account_id
    assert result.target_credit_after == Decimal("1000")
    for key in ("invoice1", "invoice2", "invoice3"):
        await db_session.refresh(data[key])
        assert data[key].paid_total == 0
        assert data[key].amount_due == data[key].total
    for invoice in data["target_invoices"]:
        await db_session.refresh(invoice)
        assert invoice.amount_due == 0
    source_balance = await PaymentService(db_session).get_student_balance(data["student"].id)
    target_balance = await PaymentService(db_session).get_student_balance(data["target"].id)
    assert source_balance.available_balance == 0
    assert target_balance.available_balance == 1000
    assert await db_session.scalar(select(func.count()).select_from(CreditAllocationReversal)) == 0
    log = await db_session.scalar(select(AuditLog).where(AuditLog.action == "payment.transfer"))
    assert sum(Decimal(row["amount"]) for row in log.old_values["allocations"]) == 6000
    assert log.old_values["student_id"] == data["student"].id
    assert log.new_values["target"]["student_id"] == data["target"].id
    assert log.comment == "Parent entered 264 instead of 2640"


async def test_stale_preview_and_duplicate_transfer_are_rejected(transfer_data, db_session):
    data = transfer_data
    service = PaymentTransferService(db_session)
    payment_id, target_id, user_id = data["payment"].id, data["target"].id, data["user"].id
    preview = await service.preview(payment_id, target_id)
    invoice = data["target_invoices"][0]
    invoice.total += 100
    invoice.amount_due += 100
    await db_session.commit()
    with pytest.raises(ValidationError, match="changed"):
        await service.transfer(payment_id, request(preview, target_id), user_id)
    preview = await service.preview(payment_id, target_id)
    await service.transfer(payment_id, request(preview, target_id), user_id)
    with pytest.raises(ValidationError, match="different student"):
        await service.transfer(payment_id, request(preview, target_id), user_id)


async def test_failure_rolls_back_all_financial_changes(transfer_data, db_session, monkeypatch):
    data = transfer_data
    service = PaymentTransferService(db_session)
    payment_id, target_id, source_id, user_id = (
        data["payment"].id,
        data["target"].id,
        data["student"].id,
        data["user"].id,
    )
    preview = await service.preview(payment_id, target_id)
    monkeypatch.setattr(
        service.payments, "allocate_manual", AsyncMock(side_effect=RuntimeError("posting failed"))
    )
    with pytest.raises(RuntimeError, match="posting failed"):
        await service.transfer(payment_id, request(preview, target_id), user_id)
    payment = await db_session.get(Payment, payment_id)
    assert payment.student_id == source_id
    assert await db_session.scalar(select(func.sum(CreditAllocation.amount))) == 6000
    assert await db_session.scalar(select(func.count()).select_from(CreditAllocationReversal)) == 0
    assert (
        await db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "payment.transfer")
        )
        == 0
    )


@pytest.mark.parametrize(
    "kind", ["legacy_refund", "sourced_refund", "unknown_allocation", "pending", "same_student"]
)
async def test_unsafe_transfers_are_blocked(transfer_data, db_session, kind):
    data = transfer_data
    payment = data["payment"]
    if kind in ("legacy_refund", "sourced_refund"):
        refund = PaymentRefund(
            payment_id=payment.id if kind == "legacy_refund" else None,
            billing_account_id=payment.billing_account_id,
            amount=1,
            refund_date=date.today(),
            reason="Refund",
            refunded_by_id=data["user"].id,
        )
        db_session.add(refund)
        await db_session.flush()
        if kind == "sourced_refund":
            db_session.add(
                PaymentRefundSource(refund_id=refund.id, payment_id=payment.id, amount=1)
            )
    elif kind == "unknown_allocation":
        row = await db_session.scalar(select(CreditAllocation).limit(1))
        row.source_payment_id = None
    elif kind == "pending":
        payment.status = "pending"
    await db_session.commit()
    target_id = payment.student_id if kind == "same_student" else data["target"].id
    with pytest.raises(ValidationError):
        await PaymentTransferService(db_session).preview(payment.id, target_id)


async def test_same_family_changes_recipient_without_reallocating(transfer_data, db_session):
    data = transfer_data
    data["target"].billing_account_id = data["student"].billing_account_id
    await db_session.commit()
    service = PaymentTransferService(db_session)
    preview = await service.preview(data["payment"].id, data["target"].id)
    assert preview.new_allocations == preview.removed_allocations == []
    await service.transfer(data["payment"].id, request(preview, data["target"].id), data["user"].id)
    assert await db_session.scalar(select(func.sum(CreditAllocation.amount))) == 6000
    assert await db_session.scalar(select(func.count()).select_from(CreditAllocationReversal)) == 0


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.USER])
async def test_only_superadmin_can_preview_or_transfer(transfer_data, client, role):
    data = transfer_data
    user = data["user"]
    user.role = role.value
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        for suffix in ("transfer/preview", "transfer"):
            response = await client.post(
                f"/api/v1/payments/{data['payment'].id}/{suffix}",
                json={
                    "target_student_id": data["target"].id,
                    "reason": "Correction",
                    "preview_token": "0" * 64,
                },
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_transfer_preserves_each_allocation_period_in_cash_pnl(transfer_data, db_session):
    from collections import defaultdict
    from datetime import UTC, datetime

    from src.modules.invoices.models import InvoiceLine
    from src.modules.reports.schemas import ProfitLossBasis
    from src.modules.reports.service import ReportsService

    data = transfer_data
    timestamps = [
        datetime(2026, 7, 31, 23, 59, tzinfo=UTC),
        datetime(2026, 8, 5, tzinfo=UTC),
        datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
    ]
    originals = list(
        (await db_session.scalars(select(CreditAllocation).order_by(CreditAllocation.id))).all()
    )
    expected = {}
    for row, timestamp in zip(originals, timestamps, strict=True):
        row.created_at = timestamp
        expected[timestamp.isoformat()] = row.amount
    # Both destination invoices have real lines so the actual P&L path can classify revenue.
    for invoice, amount in zip(
        data["target_invoices"], [Decimal("4000"), Decimal("2000")], strict=True
    ):
        invoice.subtotal = invoice.total = invoice.amount_due = amount
        db_session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                kit_id=data["kit"].id,
                description="Fees",
                quantity=int(amount / 1000),
                unit_price=1000,
                line_total=amount,
                discount_amount=0,
                net_amount=amount,
                paid_amount=0,
                remaining_amount=amount,
            )
        )
    await db_session.commit()
    reports = ReportsService(db_session)
    periods = [
        (date(2026, 7, 1), date(2026, 7, 31)),
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 30)),
    ]
    before = [
        await reports.profit_loss(start, end, basis=ProfitLossBasis.CASH_ALLOCATED)
        for start, end in periods
    ]
    service = PaymentTransferService(db_session)
    preview = await service.preview(data["payment"].id, data["target"].id)
    assert all(part.created_at is not None for part in preview.allocation_schedule)
    await service.transfer(data["payment"].id, request(preview, data["target"].id), data["user"].id)
    after = [
        await reports.profit_loss(start, end, basis=ProfitLossBasis.CASH_ALLOCATED)
        for start, end in periods
    ]
    assert [row["net_revenue"] for row in before] == [
        Decimal("3000"),
        Decimal("3000"),
        Decimal("0"),
    ]
    assert [row["net_revenue"] for row in after] == [row["net_revenue"] for row in before]
    actual = defaultdict(Decimal)
    for row in (await db_session.scalars(select(CreditAllocation))).all():
        actual[row.created_at.replace(tzinfo=UTC).isoformat()] += row.amount
    assert dict(actual) == expected


async def test_transfer_dates_only_previously_unallocated_money_today(transfer_data, db_session):
    from datetime import UTC, datetime

    data = transfer_data
    original = list(
        (await db_session.scalars(select(CreditAllocation).order_by(CreditAllocation.id))).all()
    )
    # Release one lot before transfer. Only the remaining lots have recognized income dates.
    await PaymentService(db_session).delete_allocation(original[-1].id, data["user"].id)
    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    for row in original[:-1]:
        row.created_at = timestamp
    await db_session.commit()
    preview = await PaymentTransferService(db_session).preview(
        data["payment"].id, data["target"].id
    )
    assert (
        sum(part.amount for part in preview.allocation_schedule if part.created_at is not None)
        == 4800
    )
    assert (
        sum(part.amount for part in preview.allocation_schedule if part.created_at is None) == 200
    )


async def test_payment_completion_keeps_allocation_in_the_same_transaction(
    transfer_data, db_session, monkeypatch
):
    data = transfer_data
    service = PaymentService(db_session)
    user_id = data["user"].id
    payment = await service.create_payment(
        PaymentCreate(
            student_id=data["student"].id,
            amount=Decimal("100"),
            payment_method="mpesa",
            payment_date=date.today(),
            reference="ATOMIC-COMPLETION",
        ),
        user_id,
    )
    payment_id = payment.id
    monkeypatch.setattr(
        service, "allocate_auto", AsyncMock(side_effect=RuntimeError("Allocation failed"))
    )
    with pytest.raises(RuntimeError, match="Allocation failed"):
        await service.complete_payment(payment_id, user_id)
    await db_session.rollback()
    payment = await db_session.get(Payment, payment_id)
    assert payment.status == "pending"
    assert payment.receipt_number is None


@pytest.mark.parametrize("legacy_timing", ["before", "after"])
async def test_fully_attributed_payment_transfers_without_touching_legacy_allocations(
    transfer_data,
    db_session,
    legacy_timing,
):
    from datetime import UTC, datetime, timedelta

    data = transfer_data
    payments = PaymentService(db_session)
    # A different receipt has old allocations without source_payment_id. The selected
    # 6,000 payment is completely traced, so that unrelated history must not block it.
    other = await payments.create_payment(
        PaymentCreate(
            student_id=data["student"].id,
            amount=Decimal("1000"),
            payment_method="mpesa",
            payment_date=date.today(),
            reference="UNRELATED-LEGACY-RECEIPT",
        ),
        data["user"].id,
    )
    await payments.complete_payment(other.id, data["user"].id)
    unrelated = list(
        (
            await db_session.scalars(
                select(CreditAllocation)
                .where(
                    CreditAllocation.source_payment_id == other.id,
                )
                .order_by(CreditAllocation.id)
            )
        ).all()
    )
    legacy_date = (
        datetime(2026, 2, 6, tzinfo=UTC)
        if legacy_timing == "before"
        else datetime.now(UTC) + timedelta(days=1)
    )
    for row in unrelated:
        row.source_payment_id = None
        row.created_at = legacy_date
    await db_session.commit()
    snapshot = {row.id: (row.invoice_id, row.amount) for row in unrelated}
    transfer = PaymentTransferService(db_session)
    preview = await transfer.preview(data["payment"].id, data["target"].id)
    assert sum(row.amount for row in preview.removed_allocations) == 6000
    assert preview.source_credit_after == 0
    await transfer.transfer(
        data["payment"].id, request(preview, data["target"].id), data["user"].id
    )
    for row in unrelated:
        await db_session.refresh(row)
        assert row.source_payment_id is None
        assert (row.invoice_id, row.amount) == snapshot[row.id]
        assert row.created_at.replace(tzinfo=UTC) == legacy_date
    source = await payments.get_student_balance(data["student"].id)
    assert source.available_balance == 0
    assert (
        await db_session.scalar(
            select(func.sum(CreditAllocation.amount)).where(
                CreditAllocation.billing_account_id == data["student"].billing_account_id,
            )
        )
        == 1000
    )
