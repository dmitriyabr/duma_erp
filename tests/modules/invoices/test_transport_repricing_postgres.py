"""Run with TEST_POSTGRES_URL; verify actual account-row contention."""

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from src.core.exceptions import ValidationError
from src.modules.invoices.models import Invoice
from src.modules.invoices.transport_repricing.service import TransportRepricingService
from src.modules.payments.models import CreditAllocationReversal
from src.modules.payments.schemas import AllocationCreate
from src.modules.payments.service import PaymentService
from tests.modules.invoices.test_transport_repricing import build_repricing_data, request
from tests.modules.payments.test_payment_concurrency_postgres import (
    pg_sessions,  # noqa: F401 -- shared isolated PostgreSQL fixture
    wait_for_account_lock,
)


@pytest.mark.parametrize("operation", ["allocation", "second_repricing"])
async def test_waiting_operation_refreshes_state_after_repricing(
    pg_sessions, monkeypatch, operation  # noqa: F811 -- imported pytest fixture
):
    async with pg_sessions() as setup:
        data = await build_repricing_data(setup, Decimal("2000"), Decimal("1000"))
        invoice_id, student_id, user_id = data["invoice"].id, data["student"].id, data["user"].id
        preview = await TransportRepricingService(setup, actor_is_super_admin=True).preview(
            invoice_id
        )
        await setup.commit()
    ready, release = asyncio.Event(), asyncio.Event()
    async with pg_sessions() as correcting, pg_sessions() as waiting, pg_sessions() as observer:
        stale = await waiting.get(Invoice, invoice_id)
        assert stale.amount_due == 3000
        pid = await waiting.scalar(text("SELECT pg_backend_pid()"))
        service = TransportRepricingService(correcting, actor_is_super_admin=True)
        audit = service.audit.log

        async def pause(**kwargs):
            result = await audit(**kwargs)
            ready.set()
            await release.wait()
            return result

        monkeypatch.setattr(service.audit, "log", pause)
        applying = asyncio.create_task(service.apply(invoice_id, request(preview), user_id))
        await asyncio.wait_for(ready.wait(), 8)
        if operation == "allocation":
            action = PaymentService(waiting).allocate_manual(
                AllocationCreate(
                    student_id=student_id,
                    invoice_id=invoice_id,
                    amount=Decimal("1000"),
                ),
                user_id,
            )
        else:
            action = TransportRepricingService(waiting, actor_is_super_admin=True).apply(
                invoice_id, request(preview), user_id
            )
        blocked = asyncio.create_task(action)
        try:
            await wait_for_account_lock(observer, pid)
            assert not blocked.done()
            release.set()
            await applying
            with pytest.raises(ValidationError):
                await blocked
            await waiting.rollback()
            invoice = await observer.get(Invoice, invoice_id)
            assert invoice.total == invoice.paid_total == 1000
            assert invoice.amount_due == 0
            assert await observer.scalar(select(func.sum(CreditAllocationReversal.amount))) == 1000
        finally:
            release.set()
            await asyncio.gather(applying, blocked, return_exceptions=True)
