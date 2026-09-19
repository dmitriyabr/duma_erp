"""Run with TEST_POSTGRES_URL against a disposable PostgreSQL database.

Each test uses a separate schema. SQLite cannot exercise these row-lock races.
"""

import asyncio
import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.database.base import Base
from src.core.exceptions import ValidationError
from src.modules.billing_accounts.models import BillingAccount
from src.modules.invoices.models import Invoice
from src.modules.payments.models import CreditAllocation, Payment
from src.modules.payments.schemas import AllocationCreate, AutoAllocateRequest, PaymentRefundCreate
from src.modules.payments.service import PaymentService
from src.modules.payments.transfers.service import PaymentTransferService
from tests.modules.payments.test_payment_transfers import build_transfer_data, request


@pytest.fixture
async def pg_sessions():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set TEST_POSTGRES_URL to run PostgreSQL concurrency tests")
    schema = "payment_race_" + uuid.uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        await admin.dispose()


@pytest.fixture
async def db_session(pg_sessions):
    async with pg_sessions() as session:
        yield session


@pytest.fixture
async def transfer_data(db_session):
    return await build_transfer_data(db_session)


async def wait_for_account_lock(observer, pid):
    async with asyncio.timeout(8):
        while True:
            blocked = await observer.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}
            )
            if blocked:
                return
            await asyncio.sleep(0.02)


@pytest.mark.parametrize("operation", ["manual", "auto", "refund"])
async def test_waiting_financial_operation_rechecks_after_transfer(
    transfer_data,
    db_session,
    pg_sessions,
    monkeypatch,
    operation,
):
    data = transfer_data
    payment_id = data["payment"].id
    source_account_id = data["payment"].billing_account_id
    target_id = data["target"].id
    user_id = data["user"].id
    invoice_id = data["invoice1"].id
    payment_date = data["payment"].payment_date
    # Start with an unallocated payment so a stale balance would authorize spending it.
    for allocation_id in list((await db_session.scalars(select(CreditAllocation.id))).all()):
        await PaymentService(db_session).delete_allocation(allocation_id, user_id)
    preview = await PaymentTransferService(db_session).preview(payment_id, target_id)
    await db_session.rollback()
    ready, release = asyncio.Event(), asyncio.Event()
    async with pg_sessions() as moving, pg_sessions() as spending, pg_sessions() as observer:
        # Deliberately preload stale ORM state as a long-running request might.
        stale_account = await spending.get(BillingAccount, source_account_id)
        assert stale_account.cached_credit_balance == 6000
        invoice = await spending.get(Invoice, invoice_id)
        invoice_id = invoice.id
        pid = await spending.scalar(text("SELECT pg_backend_pid()"))
        transfer = PaymentTransferService(moving)
        audit_log = transfer.payments.audit.log

        async def pause_before_commit(*args, **kwargs):
            result = await audit_log(*args, **kwargs)
            if kwargs.get("action") == "payment.transfer":
                ready.set()
                await release.wait()
            return result

        monkeypatch.setattr(transfer.payments.audit, "log", pause_before_commit)
        transfer_task = asyncio.create_task(
            transfer.transfer(payment_id, request(preview, target_id), user_id)
        )
        await asyncio.wait_for(ready.wait(), 8)
        payments = PaymentService(spending)
        if operation == "manual":
            action = payments.allocate_manual(
                AllocationCreate(
                    billing_account_id=source_account_id,
                    invoice_id=invoice_id,
                    amount=Decimal("4000"),
                ),
                user_id,
            )
        elif operation == "auto":
            action = payments.allocate_auto(
                AutoAllocateRequest(billing_account_id=source_account_id), user_id
            )
        else:
            action = payments.refund_payment(
                payment_id,
                PaymentRefundCreate(
                    amount=Decimal("6000"),
                    refund_method="mpesa",
                    reference_number="TEST-REFUND",
                    reason="Concurrent refund",
                    refund_date=payment_date,
                ),
                user_id,
            )
        spending_task = asyncio.create_task(action)
        try:
            await wait_for_account_lock(observer, pid)
            assert not spending_task.done()
        finally:
            release.set()
        await asyncio.wait_for(transfer_task, 8)
        if operation == "auto":
            result = await asyncio.wait_for(spending_task, 8)
            assert result.total_allocated == 0
        else:
            with pytest.raises(ValidationError):
                await asyncio.wait_for(spending_task, 8)
        await spending.rollback()
    account = await db_session.get(BillingAccount, source_account_id, populate_existing=True)
    assert account.cached_credit_balance == 0
    assert (
        await db_session.scalar(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.billing_account_id == source_account_id,
            )
        )
        == 0
    )
    assert (
        await db_session.get(Payment, payment_id, populate_existing=True)
    ).student_id == target_id


async def test_two_manual_allocations_cannot_spend_the_same_balance(
    transfer_data, db_session, pg_sessions, monkeypatch
):
    data = transfer_data
    user_id, account_id, invoice_id = (
        data["user"].id,
        data["payment"].billing_account_id,
        data["invoice1"].id,
    )
    for allocation_id in list((await db_session.scalars(select(CreditAllocation.id))).all()):
        await PaymentService(db_session).delete_allocation(allocation_id, user_id)
    ready, release = asyncio.Event(), asyncio.Event()
    async with pg_sessions() as first, pg_sessions() as second, pg_sessions() as observer:
        service = PaymentService(first)
        log = service.audit.log

        async def pause(*args, **kwargs):
            result = await log(*args, **kwargs)
            ready.set()
            await release.wait()
            return result

        monkeypatch.setattr(service.audit, "log", pause)
        payload = AllocationCreate(
            billing_account_id=account_id, invoice_id=invoice_id, amount=Decimal("4000")
        )
        winner = asyncio.create_task(service.allocate_manual(payload, user_id))
        await asyncio.wait_for(ready.wait(), 8)
        pid = await second.scalar(text("SELECT pg_backend_pid()"))
        loser = asyncio.create_task(PaymentService(second).allocate_manual(payload, user_id))
        try:
            await wait_for_account_lock(observer, pid)
        finally:
            release.set()
        await asyncio.wait_for(winner, 8)
        with pytest.raises(ValidationError, match="Insufficient balance"):
            await asyncio.wait_for(loser, 8)
        await second.rollback()
    account = await db_session.get(BillingAccount, account_id, populate_existing=True)
    assert account.cached_credit_balance == 2000


async def test_transfer_waits_for_an_earlier_allocation_and_revalidates(
    transfer_data, db_session, pg_sessions, monkeypatch
):
    data = transfer_data
    user_id, account_id, invoice_id = (
        data["user"].id,
        data["payment"].billing_account_id,
        data["invoice1"].id,
    )
    payment_id, target_id = data["payment"].id, data["target"].id
    for allocation_id in list((await db_session.scalars(select(CreditAllocation.id))).all()):
        await PaymentService(db_session).delete_allocation(allocation_id, user_id)
    preview = await PaymentTransferService(db_session).preview(payment_id, target_id)
    await db_session.rollback()
    ready, release = asyncio.Event(), asyncio.Event()
    async with pg_sessions() as allocating, pg_sessions() as moving, pg_sessions() as observer:
        payments = PaymentService(allocating)
        # Pause at the balance read: no ledger writes yet, but the account is locked.
        read_balance = payments.get_student_balance

        async def pause_balance(*args, **kwargs):
            balance = await read_balance(*args, **kwargs)
            ready.set()
            await release.wait()
            return balance

        monkeypatch.setattr(payments, "get_student_balance", pause_balance)
        winner = asyncio.create_task(
            payments.allocate_manual(
                AllocationCreate(
                    billing_account_id=account_id,
                    invoice_id=invoice_id,
                    amount=Decimal("4000"),
                ),
                user_id,
            )
        )
        await asyncio.wait_for(ready.wait(), 8)
        pid = await moving.scalar(text("SELECT pg_backend_pid()"))
        loser = asyncio.create_task(
            PaymentTransferService(moving).transfer(
                payment_id, request(preview, target_id), user_id
            )
        )
        try:
            await wait_for_account_lock(observer, pid)
        finally:
            release.set()
        await asyncio.wait_for(winner, 8)
        with pytest.raises(ValidationError, match="not fully linked"):
            await asyncio.wait_for(loser, 8)
    account = await db_session.get(BillingAccount, account_id, populate_existing=True)
    assert account.cached_credit_balance == 2000
    assert (
        await db_session.get(Payment, payment_id, populate_existing=True)
    ).billing_account_id == account_id
