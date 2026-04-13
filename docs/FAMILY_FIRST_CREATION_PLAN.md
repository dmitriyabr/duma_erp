# Family-First / Unified Admission Flow

## 1. Current Decision

The product flow is now unified:

1. Staff opens `Students -> New admission` (`/students/new`).
2. Staff enters the billing account / payer contact.
3. Staff adds one or more children in the same form.
4. Staff can optionally link already-admitted students into the same billing account.
5. The system creates one `BillingAccount` and all new `Student` records inside it.

There is no separate staff-facing choice between `New student` and `New family`.

The old `/billing/families/new` path is kept only as a compatibility redirect to `/students/new`.

## 2. Naming

Backend and database naming:
- Entity: `BillingAccount`
- Public account number: `account_number`
- Type: `account_type = individual | family`
- Contact fields currently remain named `primary_guardian_*` in the schema for compatibility.

UI naming:
- Menu label: `Billing Accounts`
- Create button: `New admission`
- Contact section: `Billing contact`
- Child section: `Children`

Avoid showing legacy `primary_guardian_*` labels in user-facing UI. Those fields are compatibility names, not a separate parent/guardian CRM model.

## 3. Business Model

`BillingAccount` is the financial owner of money.

Rules:
- Payments and credit allocations belong to `BillingAccount`.
- Invoices remain student-owned but store `billing_account_id` as a snapshot.
- Student screens show student-specific debt separately from shared account credit.
- Billing account screens aggregate members, invoices, payments, credit, debt, and statement.
- A `family` billing account can have one child and must still appear in the billing accounts list.
- The billing accounts list shows all accounts by default: `individual` and `family`.

## 4. Backend API

### `POST /billing-accounts`

Creates a billing account / admission.

Payload supports:
- `student_ids`: existing students to link.
- `new_children`: new students to create directly inside the billing account.

At least one child/member is required.

Example:

```json
{
  "display_name": "Catherine Adhiambo",
  "primary_guardian_name": "Catherine Adhiambo",
  "primary_guardian_phone": "+254700000000",
  "primary_guardian_email": "cat@example.com",
  "notes": null,
  "student_ids": [101],
  "new_children": [
    {
      "first_name": "John",
      "last_name": "Adhiambo",
      "gender": "male",
      "grade_id": 3,
      "transport_zone_id": null,
      "guardian_name": null,
      "guardian_phone": null,
      "guardian_email": null,
      "enrollment_date": null,
      "notes": null
    }
  ]
}
```

Child guardian fields can be omitted if they should inherit the billing contact from the account header.

### `POST /billing-accounts/{id}/children`

Creates a new student directly inside an existing billing account.

Used by the `Add child` action on billing account detail.

### `POST /billing-accounts/{id}/members`

Links existing students into an existing billing account.

Used by the `Link existing students` action.

### `POST /students`

Still supports standalone creation.

If `billing_account_id` is not provided, the system creates an `individual` account automatically.

If `billing_account_id` is provided, the student is created directly inside that existing shared billing account and no temporary individual account is created.

## 5. Frontend

### `/students/new`

Canonical admission entry point.

Sections:
- `Billing account / contact`
- `Children`
- `Link existing students`

Save button:
- `Create admission`

### `/billing/families`

Legacy path retained for routing compatibility, but UI label is `Billing Accounts`.

The page:
- shows both `individual` and `family` accounts by default;
- includes a `Type` column;
- has `New admission`, which routes to `/students/new`.

### `/billing/families/{accountId}`

Billing account detail page.

Actions:
- `Record payment`
- `Auto-allocate credit`
- `Edit`
- `Add child`
- `Link existing students`

## 6. Tests To Keep

Backend regression coverage should include:
- create billing account with one new child;
- create billing account with existing + new child;
- create student with explicit `billing_account_id`;
- add child to existing billing account;
- default `GET /billing-accounts` includes both `individual` and `family`;
- account with one child and `account_type=family` remains visible.

Frontend checks should cover:
- `/students/new` uses the unified admission form;
- `/billing/families/new` redirects to `/students/new`;
- Billing Accounts list does not send `account_type=family` by default.

## 7. Open Follow-Ups

Keep these as separate future features:
- remove/split member flow;
- merge duplicate billing accounts;
- printable billing account statement;
- M-Pesa matching by `billing_account_number`;
- reversal flow for moving completed payments between accounts.
