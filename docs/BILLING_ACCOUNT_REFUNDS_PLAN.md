# Billing Account Refunds

## 1. Decision

Refunds are implemented as billing-account-level financial documents.

The main business question is not "which original payment are we refunding?".
The main question is:

> Which billing account money leaves the school, and which invoice allocations must be reversed to make that possible?

Payment attribution remains useful for audit and over-refund prevention, but it should not be the primary admin workflow.

Target hierarchy:

1. `BillingAccountRefund` - one outgoing cash movement from a billing account.
2. `CreditAllocationReversal` - the invoice allocation impact caused by that refund.
3. Payment source attribution - internal/audit detail that prevents refunding more received cash than exists.


## 2. Implemented State

Current implementation is account-level:

- primary UI action: `Refund account credit` on `BillingAccountDetailPage`;
- API:
  - `POST /billing-accounts/{account_id}/refunds/preview`;
  - `GET /billing-accounts/{account_id}/refunds/allocation-options`;
  - `POST /billing-accounts/{account_id}/refunds`;
  - `GET /billing-accounts/{account_id}/refunds`;
  - `GET /billing-accounts/refunds/{refund_id}`;
  - `POST /payments/{payment_id}/refunds` remains as compatibility shortcut;
- DB:
  - `payment_refunds` is the refund header table;
  - `payment_refunds.refund_number` stores document numbers;
  - `payment_refunds.payment_id` is nullable legacy context for shortcut/old rows;
  - `payment_refund_sources` stores internal payment source attribution;
  - `credit_allocation_reversals.refund_id` links invoice impact to refund headers;
- bank reconciliation matches outgoing transactions to refund headers through existing `bank_transaction_matches.payment_refund_id`;
- reports/statements/accountant exports read refund header amount and payment source attribution.

This supports:

- one refund covering several payments;
- one outgoing bank transfer reconciled to one refund document;
- refunds where the original payments were already allocated across invoices;
- clear visibility into which invoices were reopened;
- manual UI selection of invoice allocations when the automatic newest-first impact is not the desired accounting treatment.


## 3. Product Goal

### 3.1. Admin workflow

On `BillingAccountDetailPage`, staff should have one primary action:

```text
Refund account credit
```

The dialog should collect:

- amount;
- refund date;
- method;
- reference number and/or proof text and/or proof attachment;
- reason;
- notes.

Before submit, the UI should show an impact preview:

- total refundable amount for the billing account;
- available free account credit used;
- amount that requires allocation reversal;
- invoices/allocations that will be reopened;
- resulting invoice paid/due changes;
- internal payment source attribution, as secondary detail.

The default path should be one action, one proof, one refund record.

### 3.2. Accountant workflow

Accountants should see:

- one refund row in the billing account refund history;
- one debit row in the billing account statement;
- one unmatched refund candidate in bank reconciliation;
- one outgoing bank transaction matched to one refund document.

The refund detail can expand into:

- affected invoices/allocation reversals;
- internal payment source attribution;
- proof/reference/download.


## 4. Data Model

### 4.1. Recommended domain names

Use the domain name `BillingAccountRefund`.

For migration safety, the physical table remains `payment_refunds` and is interpreted as the refund header. A later cleanup may rename it to `billing_account_refunds`, but that rename is not required for the account-level implementation.

Implemented v1:

- keep table `payment_refunds`;
- `refund_number`;
- nullable/deprecated `payment_id`;
- `payment_refund_sources`;
- code treats `payment_refunds` as account-level refund headers.

Clean long-term v2:

- rename `payment_refunds` to `billing_account_refunds`;
- rename reconciliation column `payment_refund_id` to `billing_account_refund_id`;
- keep compatibility views or migration shims only if needed.

### 4.2. Refund header

Target header fields:

| Field | Notes |
| --- | --- |
| id | Primary key |
| refund_number | Human-readable number, e.g. `RFND-2026-000001` |
| billing_account_id | Required owner of money |
| amount | Total outgoing refund amount |
| refund_date | Date used for statement/reconciliation |
| refund_method | M-Pesa, bank transfer, cash, etc. |
| reference_number | External reference |
| proof_text | Manual confirmation text |
| proof_attachment_id | Confirmation file |
| reason | Required |
| notes | Optional |
| status | `posted` for v1; later `voided` if needed |
| refunded_by_id | User |
| created_at / updated_at | Audit timestamps |

Existing `payment_refunds.payment_id` is legacy context only:

- nullable;
- not used as owner of the refund;
- retained temporarily for backward compatibility and old rows.

### 4.3. Payment source attribution

Add a line/source table:

```text
payment_refund_sources
  id
  refund_id
  payment_id
  amount
  created_at
```

Purpose:

- prevent over-refunding received cash;
- explain which completed payments fund the refund;
- support old payment-level refund history.

This table is not the main user-facing object. Admins do not normally need to select these rows.

Default source attribution:

- latest refundable completed payments first;
- only within the same billing account;
- never exceed `payment.amount - sum(existing refund source amounts for that payment)`.

Reasoning:

- source attribution is a cash/audit constraint;
- allocation reversal is the business impact users care about.

### 4.4. Allocation reversals

Extend `credit_allocation_reversals`:

```text
credit_allocation_reversals
  id
  credit_allocation_id
  refund_id nullable
  amount
  reason
  reversed_by_id
  reversed_at
```

`refund_id` links invoice impact to the refund document.

V1 can keep the current behavior:

- create a reversal row;
- reduce `credit_allocations.amount`;
- recalculate invoice line paid amounts and invoice status.

Longer-term ledger improvement:

- store original allocation amount immutably;
- compute current allocation as `allocation.amount - sum(reversals)`;
- avoid mutating historical allocation rows.

That is cleaner but bigger and not required for account-level refunds.

### 4.5. Bank reconciliation

Reconciliation should match outgoing bank transactions to the refund header, not to each payment source.

For pragmatic v1:

- keep `bank_transaction_matches.payment_refund_id`;
- treat it as pointing to the refund header.

If/when table names are cleaned up:

- add `bank_transaction_matches.billing_account_refund_id`;
- backfill from old `payment_refund_id`;
- deprecate `payment_refund_id`.


## 5. Refund Calculation

### 5.1. Definitions

For a billing account:

```text
completed_payments_total = sum(completed payments)
posted_refunds_total = sum(posted refunds)
current_allocated_total = sum(current credit_allocations.amount)
available_credit = completed_payments_total - posted_refunds_total - current_allocated_total
refundable_total = completed_payments_total - posted_refunds_total
```

Validation:

```text
refund.amount <= refundable_total
```

If:

```text
refund.amount <= available_credit
```

then no invoices need to be reopened.

If:

```text
refund.amount > available_credit
```

then:

```text
amount_to_reopen = refund.amount - available_credit
```

and allocation reversals are required.

### 5.2. Why allocations matter more than payments

Payments explain where cash originally came from.

Allocations explain which invoices were considered paid.

Refunding cash affects the billing account. If free credit is insufficient, the system must reopen paid invoice value. Therefore the important user-facing decision is which allocations to reverse, because that changes:

- invoice status;
- invoice amount due;
- student/family statement;
- aged receivables;
- parent-facing balance.


## 6. Allocation Reversal Strategy

### 6.1. Default automatic strategy

Default v1 strategy:

1. Use free account credit first.
2. If more is needed, reverse current allocations from newest to oldest:
   - `CreditAllocation.created_at desc`;
   - `CreditAllocation.id desc`.
3. Never reverse more than the allocation's current amount.
4. Recalculate invoice line paid amounts and invoice status after reversals.

Reasoning:

- newest allocations are less likely to belong to closed historical periods;
- this is predictable;
- it avoids forcing admins into low-level payment selection for common cases.

### 6.2. Manual impact override

The preview now supports an advanced/manual mode.

Admin/accountant can choose:

- invoice;
- allocation;
- reversal amount.

The UI loads selectable rows from:

```text
GET /billing-accounts/{account_id}/refunds/allocation-options
```

Each option includes business context, not just ids:

- invoice number;
- invoice type/status;
- issue/due dates;
- student name;
- current allocation amount;
- current invoice paid/due totals.

Backend validation:

- selected allocations must belong to the same billing account;
- selected reversal total must equal `amount_to_reopen`;
- no selected reversal can exceed current allocation amount;
- cancelled/void invoices should not receive new allocation changes unless explicitly supported by a later correction flow.

### 6.3. Relationship to payment source attribution

Payment source attribution should not dictate allocation reversal by default.

Example:

- Payment A was used to pay Invoice 1 and Invoice 2.
- Payment B is still free credit.
- Parent requests a refund.

The system should first consume free account credit, regardless of which payment originally created it. Only if invoices must be reopened should the UI focus on affected invoice allocations.

The source attribution lines can still be created automatically so audit can answer "which payment capacity did this refund consume?"


## 7. API Design

### 7.1. Preview

```text
POST /billing-accounts/{account_id}/refunds/preview
```

Payload:

```json
{
  "amount": "7000.00",
  "refund_date": "2026-05-06",
  "allocation_reversals": [
    {
      "allocation_id": 123,
      "amount": "2500.00"
    }
  ]
}
```

Response:

```json
{
  "billing_account_id": 1,
  "amount": "7000.00",
  "refundable_total": "12000.00",
  "available_credit_used": "3000.00",
  "amount_to_reopen": "4000.00",
  "allocation_reversals": [
    {
      "allocation_id": 123,
      "invoice_id": 55,
      "invoice_number": "INV-2026-000055",
      "invoice_type": "school_fee",
      "invoice_status": "paid",
      "due_date": "2026-05-31",
      "student_name": "Jane Doe",
      "current_allocation_amount": "5000.00",
      "reversal_amount": "4000.00",
      "invoice_amount_due_before": "0.00",
      "invoice_amount_due_after": "4000.00"
    }
  ],
  "payment_sources": [
    {
      "payment_id": 77,
      "payment_number": "PAY-2026-000077",
      "source_amount": "7000.00"
    }
  ]
}
```

### 7.2. Manual allocation options

```text
GET /billing-accounts/{account_id}/refunds/allocation-options
```

Response rows:

```json
{
  "allocation_id": 123,
  "invoice_id": 55,
  "invoice_number": "INV-2026-000055",
  "student_id": 10,
  "student_name": "Jane Doe",
  "invoice_type": "school_fee",
  "invoice_status": "paid",
  "issue_date": "2026-05-01",
  "due_date": "2026-05-31",
  "current_allocation_amount": "5000.00",
  "invoice_paid_total": "5000.00",
  "invoice_amount_due": "0.00",
  "invoice_total": "5000.00"
}
```

### 7.3. Create account-level refund

```text
POST /billing-accounts/{account_id}/refunds
```

Payload:

```json
{
  "amount": "7000.00",
  "refund_date": "2026-05-06",
  "refund_method": "bank_transfer",
  "reference_number": "BANK-RFND-123",
  "proof_text": null,
  "proof_attachment_id": 501,
  "reason": "Parent requested refund",
  "notes": null,
  "allocation_reversals": [
    {
      "allocation_id": 123,
      "amount": "4000.00"
    }
  ]
}
```

If `allocation_reversals` is omitted, backend uses the automatic strategy and returns the applied impact.

### 7.4. History and detail

```text
GET /billing-accounts/{account_id}/refunds
GET /billing-accounts/refunds/{refund_id}
```

The detail response should include:

- header;
- payment source attribution;
- allocation reversals;
- bank reconciliation match status.

### 7.4. Compatibility endpoint

Keep:

```text
POST /payments/{payment_id}/refunds
```

but implement it as a shortcut:

- resolve `billing_account_id` from the payment;
- create one account-level refund;
- create a payment source line constrained to that payment;
- still compute allocation impact at billing-account level.

This keeps existing UI/API users working while moving the domain model forward.


## 8. UI Design

### 8.1. Billing account detail

Add:

- primary button: `Refund account credit`;
- section/table: `Refunds`;
- refund detail drawer/dialog.

Refunds table columns:

- date;
- refund number;
- method;
- reference;
- amount;
- reconciliation status;
- proof/download;
- actions.

Refund dialog:

1. Enter amount/proof/reason.
2. Load preview.
3. Show impact:
   - free credit used;
   - invoices reopened;
   - payment source attribution collapsed by default.
4. Confirm.

### 8.2. Student payment tab and payment receipts

Payment rows can still show:

- refunded amount;
- still refundable;
- refund status.

The `Refund` action can remain as a convenience action, but it should be secondary to account-level refund.

### 8.3. Bank reconciliation

Show refund header candidates:

- refund number;
- date;
- billing account;
- amount;
- reference/proof.

Manual match should match one outgoing transaction to one refund header.

### 8.4. Statement

Billing account statement should show one refund debit row per refund header.

Allocation reversals should also be explainable, either:

- nested under refund detail; or
- shown as separate informational rows if needed for invoice history.

Do not show multiple debit rows just because multiple payment sources were attributed internally.


## 9. Reporting

Reports should use refund header amount for cash outflow/refund totals.

Payment-level `refunded_amount` should be derived from `payment_refund_sources`, not from `payment_refunds.payment_id`.

Invoice outstanding should be derived from current allocations after reversal.

Allocation-based reports must account for reversals so historical periods remain explainable.


## 10. Migration Status

### Phase 1. Schema

Implemented by Alembic revision `049_account_level_payment_refunds`:

- `payment_refunds.refund_number`;
- nullable/deprecated `payment_refunds.payment_id`;
- `payment_refund_sources`;
- `credit_allocation_reversals.refund_id`;
- indexes/FKs.

Backfill:

- for each existing `payment_refunds` row, create one `payment_refund_sources` row using old `payment_id` and `amount`;
- generate `refund_number` for old rows;
- leave existing `credit_allocation_reversals.refund_id` nullable unless a safe backfill path exists.

### Phase 2. Service layer

Implemented account-level refund service:

- preview;
- create;
- allocation reversal selection;
- source attribution;
- invoice recalculation;
- audit.

Old payment-level refund endpoint calls the account-level service.

### Phase 3. API and UI

Implemented:

- account refund preview endpoint;
- account refund create endpoint;
- refund list/detail endpoints;
- billing account refund UI;
- refund history/detail;
- updated reconciliation candidate labels.

### Phase 4. Reconciliation and reporting

Implemented:

- reconciliation matches header refund;
- exports use refund header;
- payment rows derive refund status from source attribution;
- statements show one refund debit row.

### Phase 5. Cleanup

Optional:

- rename table/class from `PaymentRefund` to `BillingAccountRefund`;
- rename `payment_refund_id` in bank matches;
- remove legacy direct use of `payment_refunds.payment_id`.


## 11. Test Plan

Backend tests implemented:

- refund fully covered by free account credit;
- refund requiring one allocation reversal;
- refund requiring multiple allocation reversals across invoices/students;
- refund amount exceeds refundable total;
- refund source attribution across multiple payments;
- old `POST /payments/{payment_id}/refunds` compatibility path;
- bank reconciliation matches one transaction to one refund;
- statement shows one refund debit row;
- payment rows show derived refunded/refundable amounts.

Manual/follow-up QA:

- billing account refund dialog preview;
- validation messages for missing proof/reference;
- refund history table;
- reconciliation unmatched refund candidate;
- payment-level shortcut still works.


## 12. Open Decisions

1. Should manual impact override be exposed in UI?
   Current state: backend schema accepts manual allocation reversal requests; UI uses automatic newest-first preview/create.

2. Should manual impact override be available to Admin only or also Accountant?
   Current state: SuperAdmin/Admin can create refunds; Accountant can reconcile and inspect.

3. Should refund documents be voidable?
   Recommendation: not in v1; add a separate void/reversal flow later if needed.

4. Should physical DB names be cleaned up immediately?
   Recommendation: no. Keep `payment_refunds` as header for v1 to reduce migration risk, but document the domain as `BillingAccountRefund`.
