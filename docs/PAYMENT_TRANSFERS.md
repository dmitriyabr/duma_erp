# Payment recipient corrections

SuperAdmin can use **Incoming Payments → Transfer** to select another student,
enter a reason and review invoice allocations, credit balances and allocation dates.
The server rejects stale previews and payments with refunds or ambiguous funding.
Corrections retain the payment identity, receipt, reference and date, and record
previous ownership and allocations in the audit log.

## Ledger concurrency contract

Every operation that changes family credit or its invoice allocations must acquire
`billing_accounts.locking.lock_accounts` (or `lock_record_accounts`) **before** reading
the balance, eligibility, or invoice amounts. Locks are PostgreSQL row locks held
until transaction commit/rollback. Both transfer accounts and all accounts involved
in a membership move are locked in ascending ID order. Record ownership is checked
again after waiting; a changed owner requires a retry rather than locking another
account out of order.

Posting a payment and its preferred/automatic allocations share one transaction.
Nested allocation calls use `commit=False`. Do not add an intermediate commit.
Refresh ORM financial state after waiting; an identity-map object may predate the lock.
The same protocol applies to refunds, invoice discounts/cancellation, withdrawals,
account membership changes and cached balance updates. Table write locks are not a
substitute: they allow a concurrent caller to validate an obsolete balance.

## Allocation dates

The destination shares are planned once for the whole payment. Those shares are
split into funding lots from the original allocations, ordered by timestamp and ID.
Each lot retains its exact original `created_at`, including when lots cross month
boundaries or several lots fund one destination invoice. Only previously unallocated
money receives a new allocation date. The preview and audit include this schedule.

If destination debt is smaller than the old allocated amount, the unused portion
becomes account credit and is no longer allocated revenue; it is not moved into the
current month's income. When the destination can absorb all the old allocations,
the Cash-allocated P&L revenue total for each original period is preserved.

## Tests

`tests/modules/payments/test_payment_transfers.py` checks transfers, rollback, access,
preview staleness and the actual Cash-allocated P&L across historical periods.

Run `tests/modules/payments/test_payment_concurrency_postgres.py` with
`TEST_POSTGRES_URL` set to an asyncpg URL for a disposable PostgreSQL database.
Each test creates and drops its own schema. The tests inspect PostgreSQL blocking
PIDs to verify real waiting, then check balances after transfer/allocation/refund
races in both orderings. Without that variable these tests are explicitly skipped;
SQLite is not considered a concurrency test.
