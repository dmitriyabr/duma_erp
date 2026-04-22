# Real-Cash Profit & Loss (`cash_allocated`) Plan

## 1. Problem

Current financial reports answer two different questions, but neither answers the management question
"how much real money did we collect by revenue bucket, and what profit does that leave us with?":

- `Profit & Loss` is currently invoice-based:
  - revenue is recognized by `Invoice.issue_date`;
  - grouping is driven by coarse `invoice_type`;
  - this explains billed revenue, but not collected cash.
- `Cash Flow` is currently cash-based:
  - inflows are real completed payments;
  - inflows are attributed only by allocations created on the same day;
  - anything not attributable that same day is shown as `Unallocated / Credit`;
  - this keeps cash totals correct, but the report is weak as a margin view.

Management needs one familiar P&L-shaped report that can answer both questions:

1. `Accrual / Invoiced` - what we billed.
2. `Real Cash / Allocated` - what cash is already paid and attributable to a revenue bucket.

Additionally:

- revenue needs finer buckets than the current `invoice_type`;
- `Uniform Sales` must be a separate revenue line;
- term filtering is useful for revenue origin analysis, but current expense data is not term-tagged.


## 2. Product Decision

Do not create a second standalone report.

Extend the existing `Profit & Loss` report with a new `basis` filter:

- `basis=accrual` - current behavior, kept as default for backward compatibility.
- `basis=cash_allocated` - new management view, labeled in UI as `Real Cash (Allocated)`.

Recommended API shape:

```text
GET /api/v1/reports/profit-loss
  ?date_from=2026-01-01
  &date_to=2026-01-31
  &basis=accrual|cash_allocated
  &term_id=123                # optional
  &breakdown=monthly          # optional
  &format=xlsx                # optional
```

Rationale:

- one screen, one export, one mental model;
- basis becomes a first-class reporting dimension;
- frontend keeps the same layout and only switches data basis;
- future comparisons between billed and cash-collected P&L become straightforward.


## 3. Shared Revenue Bucket Taxonomy

Revenue grouping must stop relying only on `Invoice.invoice_type`.

Introduce a shared reporting helper that derives a `revenue_bucket` per invoice line.
This helper should be reused by:

- accrual P&L;
- cash-allocated P&L;
- future cash-flow inflow labeling improvements.

Recommended bucket set:

- `school_fee` -> `School Fee`
- `transport` -> `Transport`
- `activity` -> `Activities`
- `uniform_sales` -> `Uniform Sales`
- `admission_fee` -> `Admission Fee`
- `interview_fee` -> `Interview Fee`
- `other_fees` -> `Other Fees`

Recommended derivation order:

1. If `invoice.invoice_type == school_fee` -> `school_fee`
2. If `invoice.invoice_type == transport` -> `transport`
3. If `invoice.invoice_type == activity` -> `activity`
4. Else if `line.kit.sku_code == ADMISSION-FEE` -> `admission_fee`
5. Else if `line.kit.sku_code == INTERVIEW-FEE` -> `interview_fee`
6. Else if `line.kit.category.name == "Uniform"` -> `uniform_sales`
7. Else -> `other_fees`

Why line-level classification is required:

- current initial-fees invoice is `invoice_type=adhoc`, but contains separate admission and interview lines;
- uniform sales are usually kits/products, not a dedicated `invoice_type`;
- grouping by invoice header alone is too coarse for real margin analysis.

Important rule:

- this taxonomy should be treated as a reporting concern first;
- no new `invoice_type` is required for v1;
- if the taxonomy spreads into more features later, it can be promoted into a stored model field.


## 4. `basis=accrual`

This mode stays available and remains the default.

Revenue logic:

- recognize revenue by `Invoice.issue_date`;
- include invoices with statuses `issued`, `partially_paid`, `paid`;
- aggregate by `revenue_bucket` derived from invoice lines;
- compute:
  - `gross_revenue = sum(line.line_total)`
  - `total_discounts = sum(line.discount_amount)`
  - `net_revenue = gross_revenue - total_discounts`

Expense logic:

- keep current behavior for backward compatibility:
  - source = `ProcurementPayment(status=posted)` by `payment_date`;
  - no `company_paid` filter in accrual mode;
  - employee-paid claims continue to count as economic expense at expense date;
  - `CompensationPayout` is not counted again.

Implementation note:

- even in `accrual` mode, revenue should move from `invoice_type` grouping to line-level `revenue_bucket`
  grouping, otherwise `Uniform Sales`, `Admission Fee`, and `Interview Fee` will still be hidden inside
  `adhoc / Other Fees`.


## 5. `basis=cash_allocated`

### 5.1. Core Meaning

This mode answers:

> "What paid money is already attributable to a concrete revenue bucket?"

This is not a raw bank-inflow report.
It is a cash-based P&L view built on top of allocations.

Revenue is recognized when cash has both:

1. entered the system as a completed payment, and
2. been allocated to an invoice.

Unallocated credit is not revenue yet in this report.


### 5.2. Revenue Date Rule

Use `CreditAllocation.created_at::date` as the report date for `cash_allocated` revenue.

Why this is the correct v1 rule:

- allocations are the first moment when cash becomes attributable to a revenue bucket and a term;
- the system already preserves `CreditAllocation.created_at` during `undo-reallocate`, specifically so
  allocation-based reports do not move between periods;
- the current cash-flow report's "same-day allocation only" rule is too conservative for a management
  profitability view.

Consequences:

- a payment completed on January 31 and allocated on February 2 appears in February `cash_allocated` P&L;
- `cash_allocated` P&L is expected to differ from raw cash inflow totals in `Cash Flow` for the same period;
- this is intentional.


### 5.3. Revenue Source

Source rows:

- `CreditAllocation` with `created_at::date in [date_from, date_to]`
- joined to target `Invoice`, `InvoiceLine`, `Kit`, `Category`

Revenue recognized in this mode is based on allocated net money.

At the top level:

- `cash_net_revenue = sum(allocation.amount)` after line-share reconstruction

To preserve the familiar P&L structure, the report should also expose:

- `cash_gross_revenue`
- `cash_discounts`
- `cash_net_revenue`

These are "cash-equivalent" gross/discount views, not original invoiced totals.


### 5.4. Reconstructing Line Shares

Allocations may be:

- line-specific: `invoice_line_id` is set;
- invoice-level: `invoice_line_id is null`.

The report needs line-level shares because revenue buckets are line-based.

Recommended reconstruction algorithm per invoice:

1. Load invoice lines with:
   - `line_total`
   - `discount_amount`
   - `net_amount`
2. Load all allocations for the invoice ordered by:
   - `created_at asc`
   - `id asc`
3. Maintain remaining `net_amount` capacity per line.
4. For each allocation:
   - if `invoice_line_id` is set, consume directly from that line;
   - otherwise distribute across remaining line capacities proportionally;
   - reduce remaining capacities accordingly.
5. Only allocation shares whose allocation date falls inside the requested period contribute to the report.

This mirrors the existing invoice-level proportional logic already used to rebuild line paid amounts.

Important limitation:

- historical exact line replay is only fully reliable while invoice financial lines remain effectively immutable
  after issue;
- if the product later needs strict audit-grade historical replay for edited invoices, the system should persist
  normalized allocation-to-line shares at write time instead of reconstructing them at report time.


### 5.5. Converting Net Collected Money into Gross / Discount / Net

After line-share reconstruction, each line has:

- `allocated_net_in_period`

For each line:

- if `line.net_amount == 0`, skip the line for cash revenue purposes;
- otherwise:

```text
collection_ratio = allocated_net_in_period / line.net_amount
cash_gross_for_line = round(line.line_total * collection_ratio)
cash_discount_for_line = round(line.discount_amount * collection_ratio)
cash_net_for_line = allocated_net_in_period
```

Aggregate those values by `revenue_bucket`.

This keeps the P&L structure readable:

- gross billed equivalent collected in cash;
- discounts attributable to the collected share;
- net cash-attributable revenue.


## 6. Expense Logic by Basis

### 6.1. `accrual`

Keep current behavior:

- source = `ProcurementPayment(status=posted)`;
- no `company_paid` filter;
- employee-paid expense claims count on expense date;
- grouped by `PaymentPurpose.name`.


### 6.2. `cash_allocated`

Use actual company cash outflow.

Recommended sources:

1. Supplier / procurement payments:
   - `ProcurementPayment(status=posted, company_paid=true)`
   - grouped by `PaymentPurpose.name`
   - date = `payment_date`
2. Employee reimbursements:
   - `CompensationPayout`
   - one dedicated line: `Employee Compensations`
   - date = `payout_date`

Explicit exclusions in `cash_allocated`:

- `ProcurementPayment(company_paid=false)` created from employee claims;
- `ExpenseClaim` rows themselves;
- any cancelled payment / rejected claim.

Why:

- employee-paid claims are real economic expense, but not real school cash outflow until reimbursement;
- `cash_allocated` mode must answer the real-money question, not the economic-accrual question.


## 7. Term Filter

### 7.1. Revenue

`term_id` is safe and useful on the revenue side in both bases:

- `accrual`:
  - filter invoice lines by `Invoice.term_id == term_id`
- `cash_allocated`:
  - filter allocation-derived revenue by target `Invoice.term_id == term_id`

This lets management answer:

- how much of this period's billed revenue belongs to a term;
- how much allocated cash was collected against a term.


### 7.2. Expenses

Current expense data is not term-scoped.

There is no reliable `term_id` on:

- `ProcurementPayment`
- `CompensationPayout`
- `ExpenseClaim`

Therefore:

- do not pretend term-filtered expenses are exact;
- do not silently filter expenses by unrelated heuristics;
- document and surface the limitation explicitly.

Recommended v1 behavior:

- `term_id` filters revenue only;
- expenses remain company-wide within the selected date range;
- response should expose metadata such as:

```text
term_filter_applies_to_revenue_only = true
```

- UI should show a note when `term_id` is used:
  - `Revenue is filtered to the selected term. Expenses remain date-based company expenses.`

This makes the feature useful without overstating term profitability precision.

Recommended future improvement:

- add optional cost-center / term attribution for procurement and compensation expenses before treating
  term-filtered net profit as a strict accounting number.


## 8. Monthly Breakdown Rules

These rules apply to both `accrual` and `cash_allocated` modes.

1. Monthly buckets must respect the selected date range.
   - first month starts at `max(date_from, first_day_of_month)`
   - last month ends at `min(date_to, last_day_of_month)`
2. Monthly values must be returned as explicit `0.00`, not omitted keys.
3. Sum of monthly columns must equal the report total.
4. `breakdown=monthly` should be a presentation breakdown only; it must not change total logic.

This avoids the current class of confusion where monthly columns and total can disagree for partial-month ranges.


## 9. Excel / Export Behavior

Excel export should reuse the same payload shape as JSON.

For both bases:

- keep the same layout as current P&L;
- include the selected `basis` in the title / metadata row;
- include the selected term name when `term_id` is present;
- if `term_filter_applies_to_revenue_only=true`, include a visible note in the sheet header.

Recommended title examples:

- `Profit & Loss (Accrual): 2026-01-01 to 2026-01-31`
- `Profit & Loss (Real Cash / Allocated): 2026-01-01 to 2026-01-31`


## 10. Why This Is Better Than Reusing Cash Flow Directly

`Cash Flow` should keep answering the raw liquidity question:

- how much money came in;
- how much money went out;
- what remains as cash / credit.

`cash_allocated` P&L should answer the management profitability question:

- which paid money belongs to which revenue stream;
- what is the margin after real outflows;
- how uniforms compare against their dedicated expense bucket.

Do not force one report to answer both questions.
Keep:

- `Cash Flow` = liquidity view
- `Profit & Loss (cash_allocated)` = attributable cash profitability view


## 11. Acceptance Rules

The implementation is correct only if all of the following are true:

1. `basis=accrual` preserves current totals, except for the intentional improvement of line-level revenue buckets.
2. `basis=cash_allocated` revenue is based on `CreditAllocation.created_at`, not `Payment.payment_date`.
3. `undo-reallocate` does not move historical cash-P&L revenue between periods.
4. Unallocated payment credit does not appear inside cash-P&L revenue totals.
5. `cash_allocated` expenses count actual school cash outflow only:
   - supplier payments paid by company,
   - compensation payouts,
   - no duplicate counting of claims.
6. `Uniform Sales` appears as a dedicated revenue line.
7. Admission and interview fees are not buried inside `Other Fees`.
8. When `term_id` is used, the response clearly states that expenses are not truly term-scoped yet.
9. Monthly columns always add up to the total.
10. Months with no activity show `0.00`, not a missing value.


## 12. Suggested Implementation Order

1. Introduce shared `revenue_bucket` helper on invoice lines.
2. Refactor accrual P&L to use line-level buckets.
3. Add `basis` filter to `/reports/profit-loss`.
4. Implement `cash_allocated` revenue from allocation history.
5. Switch `cash_allocated` expenses to actual cash outflow rules.
6. Add `Uniform Sales` bucket.
7. Add optional `term_id` with explicit revenue-only semantics.
8. Fix monthly breakdown clipping and zero-filling for both bases.


## 13. Future Work

Not required for v1, but worth keeping in mind:

- persist normalized allocation-to-line shares for exact historical replay;
- add stored `revenue_bucket` or `revenue_stream` on `InvoiceLine` if it becomes widely reused;
- add cost-center / term attribution to procurement and compensation expenses;
- add a dedicated `Uniform Margin` view if management wants revenue, COGS, and gross margin for uniforms as
  a focused analysis.
