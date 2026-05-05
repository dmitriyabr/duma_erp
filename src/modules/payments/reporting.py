"""Shared reporting helpers for student payments, refunds, and allocation history."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.payments.models import (
    CreditAllocation,
    CreditAllocationReversal,
    Payment,
    PaymentRefund,
    PaymentStatus,
)
from src.shared.utils.money import round_money


def _normalize_ids(values: Iterable[int] | None) -> list[int] | None:
    if values is None:
        return None
    normalized = [int(value) for value in values if value is not None]
    return normalized


def _payment_total_query(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
    payment_method: str | None = None,
    billing_account_ids: Iterable[int] | None = None,
):
    account_ids = _normalize_ids(billing_account_ids)
    query = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == PaymentStatus.COMPLETED.value
    )
    if date_from is not None:
        query = query.where(Payment.payment_date >= date_from)
    if date_to is not None:
        query = query.where(Payment.payment_date <= date_to)
    if date_lt is not None:
        query = query.where(Payment.payment_date < date_lt)
    if date_lte is not None:
        query = query.where(Payment.payment_date <= date_lte)
    if payment_method is not None:
        query = query.where(Payment.payment_method == payment_method)
    if account_ids is not None:
        if not account_ids:
            return None
        query = query.where(Payment.billing_account_id.in_(account_ids))
    return query


def _refund_total_query(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
    payment_method: str | None = None,
    billing_account_ids: Iterable[int] | None = None,
):
    account_ids = _normalize_ids(billing_account_ids)
    query = select(func.coalesce(func.sum(PaymentRefund.amount), 0)).select_from(
        PaymentRefund
    )
    if payment_method is not None:
        query = query.join(Payment, Payment.id == PaymentRefund.payment_id)
        query = query.where(Payment.payment_method == payment_method)
    if date_from is not None:
        query = query.where(PaymentRefund.refund_date >= date_from)
    if date_to is not None:
        query = query.where(PaymentRefund.refund_date <= date_to)
    if date_lt is not None:
        query = query.where(PaymentRefund.refund_date < date_lt)
    if date_lte is not None:
        query = query.where(PaymentRefund.refund_date <= date_lte)
    if account_ids is not None:
        if not account_ids:
            return None
        query = query.where(PaymentRefund.billing_account_id.in_(account_ids))
    return query


async def get_student_payment_total(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
    payment_method: str | None = None,
    billing_account_ids: Iterable[int] | None = None,
) -> Decimal:
    query = _payment_total_query(
        date_from=date_from,
        date_to=date_to,
        date_lt=date_lt,
        date_lte=date_lte,
        payment_method=payment_method,
        billing_account_ids=billing_account_ids,
    )
    if query is None:
        return Decimal("0.00")
    result = await db.execute(query)
    return Decimal(str(result.scalar() or 0))


async def get_student_refund_total(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
    payment_method: str | None = None,
    billing_account_ids: Iterable[int] | None = None,
) -> Decimal:
    query = _refund_total_query(
        date_from=date_from,
        date_to=date_to,
        date_lt=date_lt,
        date_lte=date_lte,
        payment_method=payment_method,
        billing_account_ids=billing_account_ids,
    )
    if query is None:
        return Decimal("0.00")
    result = await db.execute(query)
    return Decimal(str(result.scalar() or 0))


async def get_net_student_cash_total(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
    payment_method: str | None = None,
    billing_account_ids: Iterable[int] | None = None,
) -> Decimal:
    payments_total = await get_student_payment_total(
        db,
        date_from=date_from,
        date_to=date_to,
        date_lt=date_lt,
        date_lte=date_lte,
        payment_method=payment_method,
        billing_account_ids=billing_account_ids,
    )
    refunds_total = await get_student_refund_total(
        db,
        date_from=date_from,
        date_to=date_to,
        date_lt=date_lt,
        date_lte=date_lte,
        payment_method=payment_method,
        billing_account_ids=billing_account_ids,
    )
    return round_money(payments_total - refunds_total)


async def get_student_payment_totals_by_account(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
) -> dict[int, Decimal]:
    query = (
        select(
            Payment.billing_account_id,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .where(
            Payment.status == PaymentStatus.COMPLETED.value,
            Payment.billing_account_id.isnot(None),
        )
        .group_by(Payment.billing_account_id)
    )
    if date_from is not None:
        query = query.where(Payment.payment_date >= date_from)
    if date_to is not None:
        query = query.where(Payment.payment_date <= date_to)
    if date_lt is not None:
        query = query.where(Payment.payment_date < date_lt)
    if date_lte is not None:
        query = query.where(Payment.payment_date <= date_lte)
    result = await db.execute(query)
    return {int(row[0]): Decimal(str(row[1] or 0)) for row in result.all() if row[0] is not None}


async def get_student_refund_totals_by_account(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    date_lt: date | None = None,
    date_lte: date | None = None,
) -> dict[int, Decimal]:
    query = (
        select(
            PaymentRefund.billing_account_id,
            func.coalesce(func.sum(PaymentRefund.amount), 0).label("total"),
        )
        .where(PaymentRefund.billing_account_id.isnot(None))
        .group_by(PaymentRefund.billing_account_id)
    )
    if date_from is not None:
        query = query.where(PaymentRefund.refund_date >= date_from)
    if date_to is not None:
        query = query.where(PaymentRefund.refund_date <= date_to)
    if date_lt is not None:
        query = query.where(PaymentRefund.refund_date < date_lt)
    if date_lte is not None:
        query = query.where(PaymentRefund.refund_date <= date_lte)
    result = await db.execute(query)
    return {int(row[0]): Decimal(str(row[1] or 0)) for row in result.all() if row[0] is not None}


async def get_student_payment_totals_by_account_day(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    payment_method: str | None = None,
) -> dict[tuple[int, date], Decimal]:
    query = (
        select(
            Payment.billing_account_id,
            Payment.payment_date,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .where(
            Payment.status == PaymentStatus.COMPLETED.value,
            Payment.payment_date >= date_from,
            Payment.payment_date <= date_to,
            Payment.billing_account_id.isnot(None),
        )
        .group_by(Payment.billing_account_id, Payment.payment_date)
    )
    if payment_method is not None:
        query = query.where(Payment.payment_method == payment_method)
    result = await db.execute(query)
    return {
        (int(row[0]), row[1]): Decimal(str(row[2] or 0))
        for row in result.all()
        if row[0] is not None and row[1] is not None
    }


async def get_student_refund_totals_by_account_day(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    payment_method: str | None = None,
) -> dict[tuple[int, date], Decimal]:
    query = (
        select(
            PaymentRefund.billing_account_id,
            PaymentRefund.refund_date,
            func.coalesce(func.sum(PaymentRefund.amount), 0).label("total"),
        )
        .select_from(PaymentRefund)
        .where(
            PaymentRefund.refund_date >= date_from,
            PaymentRefund.refund_date <= date_to,
            PaymentRefund.billing_account_id.isnot(None),
        )
        .group_by(PaymentRefund.billing_account_id, PaymentRefund.refund_date)
    )
    if payment_method is not None:
        query = query.join(Payment, Payment.id == PaymentRefund.payment_id)
        query = query.where(Payment.payment_method == payment_method)
    result = await db.execute(query)
    return {
        (int(row[0]), row[1]): Decimal(str(row[2] or 0))
        for row in result.all()
        if row[0] is not None and row[1] is not None
    }


async def get_student_payment_totals_by_method(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
) -> dict[str | None, Decimal]:
    query = (
        select(
            Payment.payment_method,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .where(
            Payment.status == PaymentStatus.COMPLETED.value,
            Payment.payment_date >= date_from,
            Payment.payment_date <= date_to,
        )
        .group_by(Payment.payment_method)
    )
    result = await db.execute(query)
    return {row[0]: Decimal(str(row[1] or 0)) for row in result.all()}


async def get_student_refund_totals_by_method(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
) -> dict[str | None, Decimal]:
    query = (
        select(
            Payment.payment_method,
            func.coalesce(func.sum(PaymentRefund.amount), 0).label("total"),
        )
        .select_from(PaymentRefund)
        .join(Payment, Payment.id == PaymentRefund.payment_id)
        .where(
            PaymentRefund.refund_date >= date_from,
            PaymentRefund.refund_date <= date_to,
        )
        .group_by(Payment.payment_method)
    )
    result = await db.execute(query)
    return {row[0]: Decimal(str(row[1] or 0)) for row in result.all()}


async def get_student_refund_totals_by_payment_id(
    db: AsyncSession,
    payment_ids: Iterable[int],
) -> dict[int, Decimal]:
    normalized_ids = _normalize_ids(payment_ids) or []
    if not normalized_ids:
        return {}
    query = (
        select(
            PaymentRefund.payment_id,
            func.coalesce(func.sum(PaymentRefund.amount), 0).label("total"),
        )
        .where(PaymentRefund.payment_id.in_(normalized_ids))
        .group_by(PaymentRefund.payment_id)
    )
    result = await db.execute(query)
    return {int(row[0]): Decimal(str(row[1] or 0)) for row in result.all()}


def build_allocation_reversal_totals_subquery(alias_name: str = "allocation_reversal_totals"):
    return (
        select(
            CreditAllocationReversal.credit_allocation_id.label("allocation_id"),
            func.coalesce(func.sum(CreditAllocationReversal.amount), 0).label(
                "reversed_total"
            ),
        )
        .group_by(CreditAllocationReversal.credit_allocation_id)
    ).subquery(alias_name)


def build_future_allocation_reversal_totals_subquery(
    as_at_date: date,
    *,
    inclusive: bool = False,
    alias_name: str = "future_allocation_reversal_totals",
):
    reversal_date = func.date(CreditAllocationReversal.reversed_at)
    query = select(
        CreditAllocationReversal.credit_allocation_id.label("allocation_id"),
        func.coalesce(func.sum(CreditAllocationReversal.amount), 0).label(
            "reversed_total"
        ),
    )
    if inclusive:
        query = query.where(reversal_date >= as_at_date)
    else:
        query = query.where(reversal_date > as_at_date)
    return query.group_by(CreditAllocationReversal.credit_allocation_id).subquery(
        alias_name
    )
