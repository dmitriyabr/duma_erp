# Student Withdrawal Settlement

## 1. Decision

Student withdrawal is a separate accounting workflow.

It must not be hidden inside refund logic.

Refund answers:

```text
How much money leaves the school and goes back to the parent?
```

Withdrawal settlement answers:

```text
Why does this student no longer owe the full open invoice balance, and what part of paid money is retained?
```

For MVP, settlement calculation is manual. The system should not automatically calculate the value of issued uniform, consumed services, admission fees, or penalties. Accountant/Admin enters the final amounts and selects invoice actions.


## 2. Problem

Current student deactivation only changes `students.status` to `inactive`.

Existing invoices remain unchanged:

- unpaid invoices remain outstanding debt;
- partially paid invoices remain partially paid;
- paid invoices remain paid;
- future automatic invoice generation skips inactive students.

That is technically safe, but incomplete for real withdrawal cases.

Example:

1. Student is enrolled.
2. School issues invoices.
3. Parent pays part or all of the invoices.
4. Some uniform/items are issued.
5. Parent withdraws the child.
6. School should refund only the refundable part.
7. Remaining debt should be cancelled or written off if it is no longer collectible.

Refund alone cannot solve this. If refund reverses allocations, invoices may correctly become `partially_paid`, but that also means the system still expects the parent to pay the reopened balance.


## 3. MVP Scope

### 3.1. In Scope

Create a manual `WithdrawalSettlement` document that can:

- record the business decision for a student's withdrawal;
- cancel unpaid invoices;
- write off unpaid/partially paid remaining invoice balances;
- create a normal account-level refund;
- deactivate the student after successful settlement;
- preserve proof, notes, approval and audit trail.

### 3.2. Out of Scope for MVP

Do not automatically calculate:

- issued uniform value;
- inventory returned/not returned;
- consumed tuition period;
- non-refundable admission/interview fee rules;
- penalty formulas;
- refundable amount.

The UI may display relevant context, but the accountant/admin enters the settlement amounts manually.


## 4. Business Rules

### 4.1. Refund is Cash Only

Use existing `BillingAccountRefund` for actual outgoing cash.

Refund may reverse invoice allocations, but it should not decide whether the reopened debt is collectible.

### 4.2. Write-off/Credit Adjustment Closes Non-Collectible Debt

If the school decides not to collect an open invoice balance, use settlement write-off/credit adjustment.

This is not cash movement.

It should reduce invoice receivables and aged debt, with audit fields explaining why.

### 4.3. Retained Amount Is Manual

Retained amount is what the school keeps because value was delivered or the amount is non-refundable.

Examples:

- issued uniform;
- admission fee;
- interview fee;
- consumed school days/weeks;
- withdrawal/admin penalty.

The system records this as part of settlement summary. It does not need to create cash movement.

### 4.4. Final Balance Should Be Explicit

After settlement preview, the user should see:

- total paid;
- total retained;
- total refund;
- total written off/cancelled;
- remaining collectible debt.

Most withdrawal cases should end with remaining collectible debt = `0.00`, but the workflow should allow non-zero debt if the school still intends to collect it.


## 5. Recommended Data Model

### 5.1. Settlement Header

```text
withdrawal_settlements
  id
  settlement_number
  student_id
  billing_account_id
  settlement_date
  status                 draft | posted | voided
  retained_amount
  deduction_amount
  write_off_amount
  refund_amount
  remaining_collectible_debt
  reason
  notes
  proof_attachment_id
  created_by_id
  approved_by_id nullable
  posted_at nullable
  created_at
  updated_at
```

MVP can post immediately if we do not want approval states yet:

- create as `posted`;
- keep `approved_by_id = current_user.id`;
- add explicit approval workflow later if needed.

### 5.2. Settlement Lines

```text
withdrawal_settlement_lines
  id
  settlement_id
  invoice_id nullable
  invoice_line_id nullable
  action                keep_charged | cancel_unpaid | write_off | refund_allocation | deduction
  amount
  notes
  created_at
```

Line meanings:

- `keep_charged`: amount remains earned/retained by the school.
- `cancel_unpaid`: invoice has no paid amount and is cancelled.
- `write_off`: open receivable is reduced because school will not collect it.
- `refund_allocation`: allocation amount that should be reopened and refunded through account refund.
- `deduction`: manual non-refundable/penalty amount not tied to one invoice line.

### 5.3. Invoice Adjustment

Add a receivable-side adjustment table, separate from cash refunds:

```text
invoice_adjustments
  id
  adjustment_number
  invoice_id
  settlement_id nullable
  adjustment_type       withdrawal_write_off | credit_note | correction
  amount
  reason
  notes
  created_by_id
  created_at
```

For MVP, `withdrawal_write_off` is enough.

Longer-term, this can become a more general credit note module.


## 6. Posting Behavior

When posting a settlement:

1. Validate student and billing account.
2. Validate all selected invoices belong to the student's billing account.
3. Validate invoice actions are consistent:
   - `cancel_unpaid` only if invoice can be cancelled and `paid_total = 0`;
   - `write_off` cannot exceed invoice open amount;
   - `refund_allocation` must be backed by existing refundable account credit/payment capacity;
   - no action should mutate `cancelled` or `void` invoices unless explicitly supported later.
4. Create `withdrawal_settlements` header and lines.
5. Cancel selected unpaid invoices.
6. Create invoice adjustments for selected write-offs and recalculate invoice totals/status.
7. If `refund_amount > 0`, create `BillingAccountRefund` using existing refund service.
8. Deactivate the student.
9. Sync billing account/student balance caches.
10. Commit atomically.

If any step fails, no partial settlement should remain.


## 7. Manual Calculation Example

Input:

```text
Parent paid:                      50,000
Uniform issued/kept charged:       8,000
Admission non-refundable:          5,000
Withdrawal/admin deduction:        2,000
Refund to parent:                 35,000
Debt to write off/cancel:          remaining open invoice balance
```

Result:

- uniform/admission/deduction are documented as retained;
- refund document posts `35,000` outgoing cash;
- refund allocation reversals reopen only the invoice allocations selected for refund;
- write-off/cancel actions close any remaining non-collectible invoice balances;
- student becomes inactive;
- statement/audit explain both cash movement and debt cleanup.


## 8. API Design

### 8.1. Preview

```text
POST /students/{student_id}/withdrawal-settlements/preview
```

Payload:

```json
{
  "settlement_date": "2026-05-10",
  "reason": "Parent withdrew student",
  "retained_amount": "13000.00",
  "deduction_amount": "2000.00",
  "refund": {
    "amount": "35000.00",
    "refund_method": "bank_transfer",
    "reference_number": "BANK-RFND-123",
    "proof_text": "Manual confirmation",
    "proof_attachment_id": null,
    "allocation_reversals": [
      {
        "allocation_id": 123,
        "amount": "35000.00"
      }
    ]
  },
  "invoice_actions": [
    {
      "invoice_id": 55,
      "action": "write_off",
      "amount": "4000.00",
      "notes": "Withdrawal settlement"
    },
    {
      "invoice_id": 56,
      "action": "cancel_unpaid",
      "amount": "3000.00",
      "notes": "No service delivered"
    }
  ],
  "notes": "Manual settlement approved by accountant"
}
```

Response:

```json
{
  "student_id": 10,
  "billing_account_id": 2,
  "total_paid": "50000.00",
  "current_outstanding_debt": "7000.00",
  "retained_amount": "13000.00",
  "deduction_amount": "2000.00",
  "write_off_amount": "4000.00",
  "cancelled_amount": "3000.00",
  "refund_amount": "35000.00",
  "remaining_collectible_debt_after": "0.00",
  "invoice_impacts": [
    {
      "invoice_id": 55,
      "invoice_number": "INV-2026-000055",
      "student_name": "Jane Doe",
      "action": "write_off",
      "amount": "4000.00",
      "amount_due_before": "4000.00",
      "amount_due_after": "0.00"
    }
  ],
  "refund_preview": {
    "amount": "35000.00",
    "amount_to_reopen": "35000.00",
    "allocation_reversals": []
  },
  "warnings": []
}
```

### 8.2. Create/Post

```text
POST /students/{student_id}/withdrawal-settlements
```

Same payload as preview. The response returns settlement detail plus created `refund_id` if any.

### 8.3. History

```text
GET /students/{student_id}/withdrawal-settlements
GET /withdrawal-settlements/{settlement_id}
```


## 9. UI Design

### 9.1. Entry Point

Add a `Withdraw` action on student detail and billing account student row.

Do not overload the plain `Deactivate` button.

### 9.2. Settlement Dialog/Page

Recommended layout:

1. Student and billing account summary.
2. Current invoices table:
   - invoice number;
   - type/status/date;
   - paid total;
   - amount due;
   - issued/reservation context if available;
   - action selector.
3. Manual settlement amounts:
   - retained amount;
   - deduction amount;
   - refund amount;
   - write-off amount.
4. Refund allocation selector:
   - reuse account refund manual allocation UI.
5. Proof/reason/notes.
6. Preview.
7. Confirm and deactivate.

### 9.3. UX Rules

- The UI should show calculation totals, but not pretend it knows the correct settlement.
- Manual totals must reconcile before submit.
- If remaining collectible debt after settlement is non-zero, show it clearly.
- If refund amount is non-zero, proof/reference should be required.
- If write-off amount is non-zero, reason should be required.


## 10. Reporting and Accounting

Refunds:

- cash outflow;
- bank reconciliation candidate;
- statement debit row.

Write-offs/credit adjustments:

- reduce receivables;
- should appear in receivables/aged debt reports;
- should not appear as cash outflow.

Retained/deduction amounts:

- documented in settlement summary;
- may later feed revenue/adjustment reporting if accounting rules require it.


## 11. Open Questions

1. Should settlement require approval before posting?
   - MVP recommendation: post immediately for SuperAdmin/Admin, allow Accountant only if business approves.

2. Should write-off reduce invoice `total` or store adjustments separately and compute net due?
   - Recommendation: store adjustments separately and compute net due from invoice total minus allocations minus adjustments. This preserves the original invoice.
   - Shortcut MVP can mutate invoice/line remaining values only if we accept less auditability.

3. Should issued inventory returns be part of withdrawal?
   - MVP recommendation: no automatic return calculation. Use existing issuance cancellation/return workflow if items are physically returned.

4. Should `Deactivate` offer settlement automatically when open invoices exist?
   - Recommendation: yes. If open invoices or refundable credit exist, show `Withdraw / Settle` instead of plain deactivation.


## 12. Implementation Phases

### Phase 1 - Documentation and Product Contract

- This document.
- Update refund docs to clarify refund vs settlement.

### Phase 2 - Minimal Backend

- `withdrawal_settlements`;
- `withdrawal_settlement_lines`;
- `invoice_adjustments`;
- preview/create/list/detail endpoints;
- service posts settlement atomically.

### Phase 3 - UI

- withdrawal page/dialog;
- invoice action table;
- manual totals;
- reuse refund allocation selector;
- preview and submit.

### Phase 4 - Reporting

- include invoice adjustments in aged receivables and student balances;
- show settlement history on student/billing account;
- export settlement/write-off rows for accountant.

### Phase 5 - Automation Later

- automatically calculate issued uniform value;
- support returned items;
- configurable non-refundable fee policies;
- approval workflow;
- settlement void/reversal.
