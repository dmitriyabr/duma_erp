# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ERP system for a private school in Kenya (MVP version). The system handles:
- **Student Billing**: invoices, payments, discounts, credit balances, receipts
- **Inventory/Warehouse**: stock tracking, issue requests, uniform fulfillment
- **Procurement**: purchase orders, goods received, supplier payments/debts
- **Employee Compensations**: expense claims, payouts, employee balances

The full specification is in `erp_spec.md` (Russian language).

## Technology Stack (Recommended)

- **Backend**: Python (FastAPI/Django) or Node.js (NestJS)
- **Database**: PostgreSQL with DECIMAL(15,2) for money, JSON fields for allocations
- **Frontend**: React/Vue.js/Next.js with Tailwind/MUI/Ant Design
- **PDF Generation**: jsPDF, PDFKit, or WeasyPrint

## Development & CI

- **Backend tests**: Always run with **Python 3.11** via `uv run pytest tests/` (project uses uv; bare `python`/`python3` may be older and fail). **Never skip tests** before commit/merge.
- **Frontend**: `npm run build` in `frontend/`.

### Task completion checklist (обязательно перед «задача выполнена»)

После любой реализации фичи или отчёта:

1. **Документация** — обновить TASKS.md (отметить выполненные пункты), при необходимости MANAGER_REPORTS.md / ACCOUNTANT_REPORTS.md.
2. **Тесты** — написать/обновить тесты для нового кода; прогнать `uv run pytest tests/` и `npm run build`.
3. **Коммит** — зафиксировать изменения: `git add` нужных файлов, `git commit -m "..."` с осмысленным сообщением. **Без коммита задача не считается выполненной.**
4. По необходимости — push, merge (по процессу проекта).

## Architecture: Four Domains

```
STUDENTS & BILLING          INVENTORY & WAREHOUSE
- Student, Term             - Item, Category
- Invoice, InvoiceLine      - StockBalance, StockMovement
- Payment, CreditBalance    - IssueRequest, UniformFulfillment
- Discount, Receipt

PROCUREMENT & EXPENSES      EMPLOYEE COMPENSATIONS
- PurchaseOrder, POLine     - ExpenseClaim
- GoodsReceived (GRN)       - CompensationPayout
- ProcurementPayment        - EmployeeBalance
- SupplierDebt

CROSS-CUTTING: User, Role, AuditLog, Attachment, SystemSettings
```

## Key Business Rules

### Payment Allocation Priority
1. Invoices with requires_full_payment first (can be partially paid; fulfillment/issuance only when fully paid)
2. Invoices with partial_ok: remaining balance distributed proportionally by amount_due
3. Excess stays in CreditBalance. Auto-allocation runs on payment complete and on any invoice Issued (single issue, mass generate, generate for student); backend only, no frontend trigger after complete.

### Document Statuses
- **Invoice**: Draft → Issued → PartiallyPaid → Paid (or Cancelled)
- **Payment**: Posted (or Cancelled) - no editing, only cancellation
- **PurchaseOrder**: Draft → Ordered → PartiallyReceived → Received (or Cancelled)
- **ExpenseClaim**: Draft → PendingApproval → Approved/Rejected → PartiallyPaid → Paid

### Critical Constraints
- Stock balance must NEVER be negative - validate before Issue/WriteOff
- All financial operations must be atomic (database transactions)
- Document numbers: PREFIX-YYYY-NNNNNN (e.g., INV-2026-000123)
- Money: DECIMAL(15,2), currency KES, ROUND_HALF_UP
- Cancellation requires reason; cancelled documents stay in DB (not deleted)

### Automatic Triggers
- Payment on UniformBundle → creates UniformFulfillment when 100% paid
- Procurement payment by employee → auto-creates ExpenseClaim
- GRN approval → creates StockMovement(Receive), updates PO quantities
- Payment receipt → updates invoice status, student enrollment status

## Role Permissions

| Role | Key Capabilities |
|------|------------------|
| SuperAdmin | All operations, cancel payments, approve claims, manage users |
| Admin | CRUD students/invoices/POs, approve GRN/requests, issue stock |
| User | Create own claims/requests, view own data |
| Accountant | Read-only access to all data and reports |

## Database Conventions

- Primary keys: BIGINT AUTO_INCREMENT or UUID
- Foreign keys: ON DELETE RESTRICT (most), ON DELETE CASCADE (child records)
- Unique constraints on document numbers and business keys like (year, term_number)
- All entities should have created_at, updated_at, created_by timestamps
- Use JSON columns for allocation_details in payments

## API Design

RESTful with JWT authentication. Standard response format:
```json
{
  "success": true,
  "data": { ... },
  "message": "...",
  "errors": []
}
```

Key endpoints follow pattern: `/students`, `/invoices`, `/payments`, `/purchase-orders`, `/expense-claims`, `/inventory/items`, `/inventory/movements`

## Audit Requirements

Log all: CREATE/UPDATE on financial entities, APPROVE/CANCEL operations, all stock movements. Include old_values/new_values as JSON, user_id, timestamp, and optional comment.
