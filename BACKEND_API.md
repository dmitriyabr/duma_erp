# Backend API (консолидированная документация)

Актуальная сводка по бэкенду: структуры, правила и все API‑эндпоинты.
Спецификация `erp_spec.md` и статус/решения в `TASKS.md` сведены сюда, чтобы читать было удобно.

Важно:
- разделы без пометки описывают текущую реализованную систему;
- отдельные блоки с пометкой `Planned / not implemented yet` фиксируют согласованный целевой дизайн для budget advances, чтобы продуктовые и технические решения не потерялись между `docs/` и `TASKS.md`.

## 1. Базовые сведения

- **Base URL:** `/api/v1`
- **Auth:** JWT Bearer (`Authorization: Bearer <token>`)
- **Роли:** `SuperAdmin`, `Admin`, `User`, `Accountant`
- **Деньги:** `DECIMAL(15,2)`, округление `ROUND_HALF_UP`
- **Номера документов:** `PREFIX-YYYY-NNNNNN`

## 2. Формат ответов

### 2.1. Успешный ответ (ApiResponse)
```
{
  "success": true,
  "data": ...,
  "message": "..."
}
```

Для части системных эндпоинтов используется `SuccessResponse` (тот же формат,
но без поля `errors`).

### 2.2. Пагинация
```
{
  "success": true,
  "data": {
    "items": [...],
    "total": 123,
    "page": 1,
    "limit": 50,
    "pages": 3
  }
}
```

### 2.3. Ошибки (ErrorResponse)
```
{
  "success": false,
  "data": null,
  "message": "Validation error",
  "errors": [
    {"field": "field_name", "message": "Reason"}
  ]
}
```

## 3. Ключевые бизнес‑правила

- **Invoices:** `draft → issued → partially_paid → paid` (есть `cancelled`, `void`)
- **Payments:** `pending → completed | cancelled`
- **Allocation priority:** 1) счета с `requires_full_payment` (Kit) — в первую очередь, допускается частичная оплата; 2) счета с `partial_ok` — остаток распределяется пропорционально по `amount_due`.
- **Credit balance:** вычисляется как `SUM(completed payments) - SUM(allocations)`
- **Auto-allocation (бэкенд):** запускается при завершении платежа (`POST .../complete`) и при любом выставлении счёта в Issued: одиночное (POST `.../issue`), массовая генерация (`generate-term-invoices`), генерация по студенту (`generate-term-invoices/student`). Фронт не вызывает аллокацию после complete — всё делает бэкенд.
- **Employee balance:** при запросе баланса сотрудника (`GET .../payouts/employees/{id}/balance`) баланс всегда пересчитывается по одобренным claims и выплатам (approved claims − payouts).
- **Reservation:** создаётся сразу после issue инвойса по строкам с Kit (product), до оплаты; выдача может быть частичной или полной.
- **Catalog:** продажи идут через `Kit` (invoice lines используют только `kit_id`).
  - Для **editable uniform kits** фактический состав строки хранится в `InvoiceLineComponent`, а цена и правила оплаты — на уровне `Kit`.
- **Stock:** остатки не могут уходить в минус.
- **Cancellations:** по причине, данные не удаляются.

## 4. Enum‑значения (сокращённо)

- **StudentStatus:** `active`, `inactive`
- **Gender:** `male`, `female`
- **TermStatus:** `Draft`, `Active`, `Closed`
- **InvoiceType:** `school_fee`, `transport`, `adhoc`, `activity`
- **InvoiceStatus:** `draft`, `issued`, `partially_paid`, `paid`, `cancelled`, `void`
- **PaymentMethod:** `mpesa`, `bank_transfer`
- **PaymentStatus:** `pending`, `completed`, `cancelled`
- **ItemType:** `service`, `product`
- **PriceType:** `standard`, `by_grade`, `by_zone`
- **DiscountValueType:** `fixed`, `percentage`
- **StudentDiscountAppliesTo:** `school_fee`
- **ReservationStatus:** `pending`, `partial`, `fulfilled`, `cancelled`
- **MovementType:** `receipt`, `issue`, `reserve`, `unreserve`, `adjustment`
- **IssuanceType:** `internal`, `reservation`
- **RecipientType:** `employee`, `department`, `student`, `other` (для `other` — recipient_id не передаётся, только recipient_name)
- **IssuanceStatus:** `completed`, `cancelled`
- **PurchaseOrderStatus:** `draft`, `ordered`, `partially_received`, `received`, `cancelled`, `closed`
- **GoodsReceivedStatus:** `draft`, `approved`, `cancelled`
- **ProcurementPaymentStatus:** `posted`, `cancelled`
- **ProcurementPaymentMethod:** `mpesa`, `bank`, `cash`, `other`
- **ExpenseClaimStatus:** `draft`, `pending_approval`, `needs_edit`, `approved`, `rejected`, `partially_paid`, `paid`
- **PayoutMethod:** `mpesa`, `bank`, `cash`, `other`

## 5. Эндпоинты по модулям

### 5.1. Auth
- `POST /auth/login` — логин, токены
- `POST /auth/refresh` — обновление токенов
- `GET /auth/me` — текущий пользователь

### 5.2. Users
- `GET /users` — список (фильтры: `role`, `is_active`, `search`, `page`, `limit`)
- `GET /users/{user_id}`
- `POST /users`
- `PUT /users/{user_id}`
- `POST /users/{user_id}/deactivate`
- `POST /users/{user_id}/activate`
- `POST /users/{user_id}/set-password`
- `POST /users/{user_id}/remove-password`
- `POST /users/me/change-password`

### 5.2.1. Employees (HR)
- `GET /employees` — список сотрудников (filters: `status`, `search`, `page`, `limit`)
  - roles: `SuperAdmin`, `Admin`, `Accountant`
- `GET /employees/{employee_id}` — карточка сотрудника
  - roles: `SuperAdmin`, `Admin`, `Accountant`
- `POST /employees` — создание сотрудника (поддерживает `salary` и attachment_id полей)
  - roles: `SuperAdmin`, `Admin`
- `PUT /employees/{employee_id}` — обновление сотрудника (поддерживает `salary`; очистку nullable полей через `null`)
  - roles: `SuperAdmin`, `Admin`
- `DELETE /employees/{employee_id}` — удаление сотрудника
  - roles: `SuperAdmin`, `Admin`
  - при ссылках из других таблиц возвращает `409`
- `POST /employees/import-csv` — импорт сотрудников из CSV Google Form
  - body: `multipart/form-data`, поле `file`
  - result: `{ rows_processed, employees_created, employees_updated, errors[] }`
  - roles: `SuperAdmin`, `Admin`
- `GET /employees/export?format=csv` — экспорт сотрудников в CSV (включая `salary`, attachment download)
  - roles: `SuperAdmin`, `Admin`, `Accountant`

### 5.3. Terms & Pricing
- `GET /terms` — список (filter: `year`)
- `GET /terms/active`
- `GET /terms/{term_id}`
- `POST /terms`
- `PUT /terms/{term_id}`
- `POST /terms/{term_id}/activate`
- `POST /terms/{term_id}/close`
- `PUT /terms/{term_id}/price-settings` — bulk price settings
- `PUT /terms/{term_id}/transport-pricing` — bulk transport pricing
- `GET /terms/transport-zones`
- `POST /terms/transport-zones`
- `PUT /terms/transport-zones/{zone_id}`
- `GET /terms/fixed-fees`
- `POST /terms/fixed-fees`
- `PUT /terms/fixed-fees/{fee_id}`

### 5.4. Items & Kits
- `POST /items/categories`
- `GET /items/categories`
- `GET /items/categories/{category_id}`
- `PATCH /items/categories/{category_id}`
- `POST /items` — складские позиции (inventory)
- `GET /items` — filters: `category_id`, `item_type`, `include_inactive`
- `GET /items/{item_id}`
- `PATCH /items/{item_id}`
- `GET /items/{item_id}/price-history`
- `POST /items/kits` — создание кита (поддерживает editable kits с `items.source_type = 'item' | 'variant'` и полем `is_editable_components`)
- `GET /items/kits`
- `GET /items/kits/{kit_id}`
- `PATCH /items/kits/{kit_id}`
- `GET /items/kits/{kit_id}/price-history`
- `POST /items/variants` — создать группу взаимозаменяемых items (модель/линейка размеров)
- `GET /items/variants` — список variants (с их items)
- `GET /items/variants/{variant_id}` — вариант с его items
- `PATCH /items/variants/{variant_id}` — обновить имя/активность и полный список `item_ids`

### 5.5. Students & Grades
- `POST /students/grades`
- `GET /students/grades`
- `GET /students/grades/{grade_id}`
- `PATCH /students/grades/{grade_id}`
- `POST /students` — при создании автоматически создаётся billing account; optional `billing_account_id` позволяет создать нового ребёнка сразу внутри существующего account без временного отдельного account
- `GET /students` — filters: `status`, `grade_id`, `transport_zone_id`, `search`, `page`, `limit`; в response есть `billing_account_id`, `billing_account_number`, `billing_account_name`, `billing_account_member_count`. Если `include_balance=true`, то `available_balance` = shared credit linked billing account, а `outstanding_debt` / `balance` считаются по конкретному ученику, без долгов siblings.
- `GET /students/{student_id}` — response также содержит linked billing account summary
- `PATCH /students/{student_id}`
- `POST /students/{student_id}/activate`
- `POST /students/{student_id}/deactivate`

### 5.5.1. Billing Accounts
- `GET /billing-accounts` — filters: `search`, `page`, `limit`; возвращает все billing accounts, независимо от количества linked students
- `POST /billing-accounts` — создать billing account / admission. Payload поддерживает `student_ids` для already admitted students и `new_children` для unified admission flow; можно создать billing account с одним или несколькими детьми
- `GET /billing-accounts/{account_id}` — header account + members + balances
- `PATCH /billing-accounts/{account_id}` — обновить account name, billing contact, notes
- `POST /billing-accounts/{account_id}/members` — добавить existing students в существующий billing account; student из single-student account может быть перенесён, student из уже shared account требует отдельного split/merge flow
- `POST /billing-accounts/{account_id}/children` — создать нового ребёнка сразу внутри существующего billing account; child может унаследовать guardian contact из account header
- `GET /billing-accounts/{account_id}/statement` — account statement по общему кошельку (`date_from`, `date_to`)
- `BillingAccount` — канонический owner of money: payments и credit allocations привязываются к account, invoices хранят snapshot `billing_account_id`, а student response показывает linked billing account metadata. Разделения `individual/family` и поля `account_type` больше нет: один account может иметь одного или нескольких students.

### 5.5.2. Paid Activities
- `POST /activities` — создать платную активность и snapshot audience (`audience_type = all_active | grades | manual`, для `grades` передаются `grade_ids`, для `manual` — `student_ids`)
- `GET /activities` — filters: `status`, `search`, `page`, `limit`
- `GET /activities/{activity_id}` — activity header + participants roster + linked invoice/payment status
- `PATCH /activities/{activity_id}` — обновление метаданных; audience можно менять только пока по activity ещё не создавались invoices
- `POST /activities/{activity_id}/participants` — ручное добавление ученика в roster (`student_id`, optional `selected_amount`)
- `POST /activities/{activity_id}/participants/{participant_id}/exclude` — исключить ученика; если activity invoice неоплачен, он автоматически переводится в `cancelled`
- `POST /activities/{activity_id}/generate-invoices` — массово создать missing invoices типа `activity` для всех `planned` participants и затем запустить auto-allocation по затронутым ученикам
- При создании activity система автоматически создаёт service `Kit` в категории `Activities`; invoice line использует snapshot `selected_amount`, поэтому изменение activity amount влияет только на будущие invoices без переписывания старых строк

### 5.6. Invoices
- `POST /invoices`
- `GET /invoices` — filters: `student_id`, `billing_account_id`, `term_id`, `invoice_type`, `status`, `search`, `page`, `limit`
- `GET /invoices/outstanding-totals` — query: `student_ids` (строка, comma-separated, напр. `1,2,3`). Ответ: `{ totals: [{ student_id, total_due }] }` — сумма amount_due по неоплаченным/не отменённым счетам по студентам.
- `GET /invoices/{invoice_id}`
- `POST /invoices/{invoice_id}/lines`
- `DELETE /invoices/{invoice_id}/lines/{line_id}`
- `PATCH /invoices/{invoice_id}/lines/{line_id}/discount`
- `POST /invoices/{invoice_id}/issue`
- `POST /invoices/{invoice_id}/cancel`
- `POST /invoices/generate-term-invoices` — roles: `SUPER_ADMIN`, `ADMIN` (создаёт отдельный invoice с admission+interview, если их ещё не было)
- `POST /invoices/generate-term-invoices/student` — roles: `SUPER_ADMIN`, `ADMIN` (аналогично для одного студента)
  - При отсутствии price settings для grade/zone запись пропускается (bulk).

### 5.7. Discounts
- `POST /discounts/reasons`
- `GET /discounts/reasons`
- `GET /discounts/reasons/{reason_id}`
- `PATCH /discounts/reasons/{reason_id}`
- `POST /discounts/apply`
- `DELETE /discounts/{discount_id}`
- `GET /discounts/line/{invoice_line_id}`
- `POST /discounts/student`
- `GET /discounts/student` — filters: `student_id`, `include_inactive`, `page`, `limit`
- `GET /discounts/student/{discount_id}`
- `PATCH /discounts/student/{discount_id}`

### 5.8. Attachments (подтверждения платежей)
- `POST /attachments` — загрузка файла (image/PDF/CSV). Тело: `multipart/form-data`, поле `file`. Допустимые типы: image/jpeg, image/png, image/gif, image/webp, application/pdf, text/csv. Макс. 10 MB. Ответ: `{ id, file_name, content_type, file_size, created_at }`. Роль: SuperAdmin, Admin, User.
- `GET /attachments/{attachment_id}` — метаданные вложения.
- `GET /attachments/{attachment_id}/download` — скачать файл (для просмотра подтверждения). Роль: любой авторизованный.

### 5.9. Payments & Allocations
- `POST /payments` — обязателен **либо** `student_id`, **либо** `billing_account_id`; также обязателен **либо** `reference`, **либо** `confirmation_attachment_id` (подтверждение файлом). Optional `preferred_invoice_id` позволяет сначала аллоцировать этот платёж в конкретный invoice этого billing account, а только остаток отправить в общий auto-allocation.
- `GET /payments` — filters: `student_id`, `billing_account_id`, `status`, `payment_method`, `search`, `date_from`, `date_to`, `page`, `limit`. `search` ищет по `payment_number`, `receipt_number`, `reference`, `student first/last name`, `student_number`. В выдаче списка есть `student_name`, `student_number`, `billing_account_number`, `billing_account_name`.
- `GET /payments/{payment_id}`
- `PATCH /payments/{payment_id}`
- `POST /payments/{payment_id}/complete`
- `POST /payments/{payment_id}/cancel`
- `POST /payments/{payment_id}/refunds` — compatibility shortcut для refund от конкретного completed payment. Внутри создаёт account-level refund document, пишет source attribution на этот payment и при нехватке free billing-account credit откатывает allocations на уровне billing account.
- `POST /billing-accounts/{account_id}/refunds/preview` — preview account-level refund: refundable total, free credit, amount to reopen, affected allocations/invoices and payment source attribution. Optional `allocation_reversals: [{ allocation_id, amount }]` lets the UI preview a manual invoice/allocation selection.
- `GET /billing-accounts/{account_id}/refunds/allocation-options` — current refundable invoice allocations for manual refund impact selection. Includes invoice number/type/status/dates, student name, current allocation amount, paid total, amount due and invoice total.
- `POST /billing-accounts/{account_id}/refunds` — создать account-level refund document. Требует amount, refund_date, reason и proof: `reference_number`, `proof_text` или `proof_attachment_id`. По умолчанию free credit используется первым, затем allocation reversals newest-first. Optional `allocation_reversals` must exactly equal `amount_to_reopen` and lets admins choose which invoice allocations are reopened.
- `GET /billing-accounts/{account_id}/refunds` — refund history по billing account, включая payment sources и allocation reversals.
- `GET /billing-accounts/refunds/{refund_id}` — detail конкретного refund document.
- `POST /payments/students/balances-batch` — body: `{ student_ids: number[] }`. Ответ: `{ balances: StudentBalance[] }` — по каждому ученику: shared `available_balance` billing account, student-specific `outstanding_debt` и student-facing `balance`; общий credit не размазывается как личный баланс каждого ребёнка.
- `GET /payments/students/{student_id}/balance` — response возвращает billing account metadata, `available_balance` как shared credit account, а `outstanding_debt` / `balance` как student-specific position; общий credit не атрибутируется одному ребёнку, поэтому `balance` не включает долги siblings и не дублирует shared credit как личный баланс ученика
- `GET /payments/students/{student_id}/statement` — `date_from`, `date_to`; statement строится по linked billing account wallet; entries содержат `entry_type`, `payment_id`, `allocation_id`, `invoice_id`, чтобы allocation можно было откатить
- `POST /payments/allocations/auto` — body принимает `student_id` или `billing_account_id`; порядок: previous-term debt first, затем active/current term, затем future/no-term invoices; внутри одного term bucket `requires_full` invoices идут перед proportional partial allocation
- `POST /payments/allocations/manual` — body принимает `student_id` или `billing_account_id`
- `DELETE /payments/allocations/{allocation_id}` — отменить allocation и вернуть сумму в billing account credit
- `POST /payments/allocations/{allocation_id}/undo-reallocate` — атомарно отменить allocation и сразу запустить auto-allocation заново по тому же billing account; новые allocations сохраняют исходный `created_at`, чтобы allocation-based reports/exports не переезжали в период фактического исправления

### 5.9.1. M-Pesa C2B (Paybill) Webhooks
- `POST /c2b/validation/{token}` — публичный endpoint (без JWT) для validation callback (token берётся из `MPESA_WEBHOOK_TOKEN`)
- `POST /c2b/confirmation/{token}` — публичный endpoint (без JWT) для confirmation callback; создаёт completed payment и запускает auto-allocation по Admission# (BillRefNumber)
- `GET /mpesa/c2b/events/unmatched` — список unmatched событий (roles: SuperAdmin, Admin)
- `POST /mpesa/c2b/events/{event_id}/link` — ручная привязка unmatched события к студенту (roles: SuperAdmin, Admin)
- `POST /mpesa/c2b/sandbox/topup` — dev-only симуляция incoming confirmation (roles: SuperAdmin, Admin; disabled in production)

### 5.10. Inventory
- `GET /inventory/stock` — filters: `include_zero`, `category_id`, `page`, `limit`
- `GET /inventory/stock/{item_id}`
- `POST /inventory/receive`
- `POST /inventory/adjust`
- `POST /inventory/writeoff`
- `POST /inventory/inventory-count`
- `POST /inventory/issue`
- `GET /inventory/movements` — filters: `item_id`, `movement_type`, `page`, `limit`
- `GET /inventory/movements/{item_id}` — `page`, `limit`
- `POST /inventory/issuances` — создание internal issuance (recipient_type, recipient_id?, recipient_name, items: [{ item_id, quantity }], notes?). Поддерживает несколько items в одном issuance. Форма выдачи комплектом: страница `/inventory/issue` (см. docs/ISSUE_FORM.md).
- `GET /inventory/issuances` — filters: `issuance_type`, `recipient_type`, `recipient_id`, `page`, `limit`
- `GET /inventory/issuances/{issuance_id}`
- `POST /inventory/issuances/{issuance_id}/cancel`
- `GET /inventory/bulk-upload/export` — выгрузка текущего склада в CSV (attachment `stock_export.csv`). Колонки: category, item_name, sku, quantity, unit_cost. UTF-8 BOM. Роль: Admin.
- `POST /inventory/bulk-upload` — массовая загрузка остатков из CSV. Тело: `multipart/form-data`: `file` (CSV), `mode` (обязательно: `overwrite` | `update`). Режим overwrite: обнуляет quantity_on_hand по всем продуктам (только если нигде нет reserved), затем выставляет значения из CSV. Режим update: только для строк из CSV выставляет quantity_on_hand (adjustment до целевого значения). CSV: обязательные колонки category, item_name, quantity; опционально sku, unit_cost. Reserved в CSV не участвует. Ответ: `{ rows_processed, items_created, errors: [{ row, message }] }`. Роль: Admin.

### 5.11. Reservations
- `GET /reservations` — filters: `student_id`, `invoice_id`, `status`, `page`, `limit`
- `GET /reservations/{reservation_id}`
- `POST /reservations/{reservation_id}/issue`
- `POST /reservations/{reservation_id}/cancel`

### 5.12. Procurement
- `POST /procurement/purchase-orders`
- `GET /procurement/purchase-orders` — filters: `status`, `supplier_name`, `date_from`, `date_to`, `page`, `limit`
- `GET /procurement/purchase-orders/{po_id}`
- `PUT /procurement/purchase-orders/{po_id}`
- `POST /procurement/purchase-orders/{po_id}/submit`
- `POST /procurement/purchase-orders/{po_id}/close`
- `POST /procurement/purchase-orders/{po_id}/cancel`
- `GET /procurement/purchase-orders/bulk-upload/template` — скачать CSV-шаблон линий PO: заголовки, одна строка-пример, затем все product items (sku + item_name заполнены, quantity_expected и unit_price пустые). Роль: Admin.
- `POST /procurement/purchase-orders/bulk-upload/parse-lines` — разобрать CSV в линии (PO не создаётся). Тело: `multipart/form-data`, файл `file` (CSV). Колонки: sku, item_name, quantity_expected, unit_price. Ответ: `{ lines: [{ item_id?, description, quantity_expected, unit_price }], errors: [{ row, message }] }`. Роль: Admin.
- `POST /procurement/grns`
- `GET /procurement/grns` — filters: `po_id`, `status`, `date_from`, `date_to`, `page`, `limit`
- `GET /procurement/grns/{grn_id}`
- `POST /procurement/grns/{grn_id}/approve`
- `POST /procurement/grns/{grn_id}/cancel`
- `POST /procurement/grns/{grn_id}/rollback` — **SUPER_ADMIN only**. Откат approved GRN: отменяет этот GRN, откатывает `quantity_received` по линиям PO и (если `track_to_warehouse=true`) создаёт компенсационные stock movements, чтобы вернуть склад. Ограничения: для затронутых items не должно быть более поздних `receipt`-движений (иначе нельзя безопасно восстановить average cost). Если по PO уже есть оплаты (`paid_total > 0`), откат всё равно возможен — в этом случае после rollback `debt_amount` может стать отрицательным (это фактически аванс поставщику: “paid, not received”).
- `POST /procurement/payment-purposes`
- `GET /procurement/payment-purposes` — optional filter: `purpose_type=expense|fee`
- `PUT /procurement/payment-purposes/{purpose_id}`
- `POST /procurement/payments`
- `GET /procurement/payments` — filters: `po_id`, `purpose_id`, `budget_id`, `company_paid`, `status`, `date_from`, `date_to`, `page`, `limit`
- `GET /procurement/payments/{payment_id}`
- `POST /procurement/payments/{payment_id}/cancel`
> Note: если `employee_paid_id` указан (то есть платил сотрудник, `company_paid=false`), то `payment_method` канонизируется в `employee` (это не способ оплаты компании, а маркер “paid by employee”).
> Note: если указан `budget_id`, payment канонизируется в `funding_source=budget`. Для `company_paid=true` это прямой расход бюджета: он сразу уменьшает budget headroom и не создаёт claim.

### 5.13. Compensations
- `POST /compensations/claims` — создать out-of-pocket claim (без PO/GRN; для сотрудника возврат денег). Под капотом создаёт `ProcurementPayment` без PO (универсальный журнал расходов) и привязывает его к claim. Опционально поддерживает `fee_amount` (+ отдельный proof): в этом случае создаётся второй linked payment (purpose="Transaction Fees") и fee включается в total claim amount.
- `GET /compensations/claims` — filters: `employee_id`, `status`, `date_from`, `date_to`, `page`, `limit`
- `GET /compensations/claims/{claim_id}`
- `GET /compensations/claims/employees/{employee_id}/totals` — totals для сотрудника (включая pending approval): total claimed, pending approval, approved totals, paid totals, owed.
- `PATCH /compensations/claims/{claim_id}` — обновить claim в статусе `needs_edit` (или legacy `draft`), синхронизируя linked procurement payment
- `POST /compensations/claims/{claim_id}/submit` — отправить claim (`needs_edit`/legacy `draft`) обратно на approve
- `POST /compensations/claims/{claim_id}/send-to-edit` — только `SuperAdmin`; перевести `pending_approval -> needs_edit` с обязательным комментарием (`auto_created_from_payment=true` не поддерживается)
- `POST /compensations/claims/{claim_id}/approve` — при `approve=false` linked `ProcurementPayment` (и fee payment, если есть) переводится в `cancelled` (расход не признан компанией).
- `POST /compensations/payouts`
- `GET /compensations/payouts` — filters: `employee_id`, `date_from`, `date_to`, `page`, `limit`
- `GET /compensations/payouts/{payout_id}`
- `GET /compensations/payouts/employees/{employee_id}/balance`

> Note: compensations поддерживает два flow:
> - reimbursement: `employee paid with personal funds -> claim -> approve -> payout`
> - budget-funded claim: `budget advance issued earlier -> claim -> reserve allocations -> approve -> paid without payout`
>
> Отдельный direct-spend сценарий, когда компания платит поставщику сама, идёт через `POST /procurement/payments` с `company_paid=true` и `budget_id`.

### 5.13.1. Budgets / Budget Advances

Source of truth:
- `docs/BUDGET_ADVANCES_PLAN.md`
- `TASKS.md` (секция `6.4 Budget Advances / Предвыданные бюджеты`)

Текущие endpoints:

- `POST /budgets`
- `GET /budgets` — filters: `status`, `purpose_id`, `employee_id`, `page`, `limit`
- `GET /budgets/my/budgets`
- `GET /budgets/{budget_id}`
- `PATCH /budgets/{budget_id}` — `SuperAdmin` only
- `POST /budgets/{budget_id}/activate`
- `GET /budgets/{budget_id}/closure` — open advances, overdue, unresolved claims, transferable amount
- `POST /budgets/{budget_id}/close`
- `POST /budgets/{budget_id}/cancel`
- `POST /budgets/advances`
- `GET /budgets/advances` — filters: `budget_id`, `employee_id`, `status`, `page`, `limit`
- `GET /budgets/my/advances` — filters: `status`, `page`, `limit`
- `GET /budgets/advances/{advance_id}`
- `POST /budgets/advances/{advance_id}/issue`
- `POST /budgets/advances/{advance_id}/transfer`
- `POST /budgets/advances/{advance_id}/close`
- `POST /budgets/advances/{advance_id}/cancel`
- `POST /budgets/advances/{advance_id}/returns`
- `GET /budgets/advances/{advance_id}/returns`
- `GET /budgets/transfers` — filters: `budget_id`, `employee_id`, `page`, `limit`
- `GET /budgets/transfers/{transfer_id}`
- `GET /budgets/{budget_id}/my-available-balance`

Claim integration:

- `POST /compensations/claims` и `PATCH /compensations/claims/{claim_id}` принимают:
  - `funding_source`
  - `budget_id?`
- если `funding_source=budget`, то:
  - claim создаётся как budget-funded;
  - при submit backend создаёт `BudgetClaimAllocation(reserved)`;
  - при approve claim закрывается из ранее выданных advances и не попадает в payout flow.

### 5.14. Bank statements / Reconciliation

Импорт банковской выписки (Stanbic CSV), хранение файла в storage/S3 и сверка транзакций с:
- `ProcurementPayment` где `company_paid=true`
- `CompensationPayout`

- `POST /bank-statements/imports` — upload CSV (`multipart/form-data`, поле `file`). Роли: SuperAdmin, Admin.
- `GET /bank-statements/imports` — список импортов (включая вычисленный `range_from/range_to`).
- `GET /bank-statements/imports/{import_id}` — детали + строки выписки (пагинация `page/limit`, фильтры `only_unmatched`, `txn_type`). Возвращает только **исходящие** транзакции (debits).
- `GET /bank-statements/transactions` — общий список **исходящих** bank transfers (debits), фильтры: `date_from`, `date_to`, `txn_type` (например `TRF`, `CHG`, `TAX`), `matched`, `entity_type`, `search`, `page`, `limit`.
- `GET /bank-statements/txn-types` — список доступных `txn_type` (Type) для outgoing транзакций, опционально фильтры `date_from/date_to`.
- `POST /bank-statements/imports/{import_id}/auto-match` — авто‑матчинг (amount/date + эвристики по reference). Роли: SuperAdmin, Admin. Один `ProcurementPayment` / `CompensationPayout` может быть сматчен максимум с одной транзакцией; уже сматченные документы пропускаются.
- `GET /bank-statements/imports/{import_id}/reconciliation` — summary по импорту: unmatched transactions + unmatched payments/payouts.
- `GET /bank-statements/imports/{import_id}/reconciliation?ignore_range=true` — то же, но **без** фильтра по `Range From/To` из выписки (удобно для свежесозданных документов вне диапазона).
- `POST /bank-statements/transactions/{bank_transaction_id}/match` — manual match (body: `entity_type`, `entity_id`). Роли: SuperAdmin, Admin.
- `DELETE /bank-statements/transactions/{bank_transaction_id}/match` — убрать match. Роли: SuperAdmin, Admin.

Planned extension for budget advances (not implemented yet):
- outgoing transactions смогут матчиться на `BudgetAdvance`;
- incoming return transactions смогут матчиться на `BudgetAdvanceReturn`;
- это потребует расширения `BankTransactionMatch` и reconciliation summary.

### 5.xx. Accountant exports (CSV)

- `GET /accountant/export/student-payments` — completed student/billing-account receipts за период (CSV). Для shared billing account CSV включает `Billing Account#`, `Billing Account Name`, `Billing Contact`; поля `Student Name`, `Admission#`, `Grade` содержат roster всех linked students account, чтобы общий account payment не выглядел как личный платеж reference-student.
- `GET /accountant/export/student-balance-changes` — student-level ledger за период (CSV): opening balance, invoices как debit, credit allocations как credit, running balance. Raw payment на общий account не дублируется по детям; student balance меняется только после allocation на invoice конкретного student. CSV включает billing account columns.
- `GET /accountant/export/bank-transfers` — outgoing bank transfers (debits) за период + matched document numbers (CSV).
- `GET /accountant/export/bank-statement-files` — список импортированных выписок за период + download links (CSV).

---

## 6. Payloads (схемы запросов/ответов)

Ниже перечислены актуальные поля схем, используемых эндпоинтами.
Все ответы обёрнуты в `ApiResponse`, а списки — в `PaginatedResponse`.

### 6.1. Auth
- `LoginRequest`: `email`, `password`
- `LoginResponse`: `user`, `access_token`, `refresh_token`, `token_type`
- `RefreshRequest`: `refresh_token`
- `TokenResponse`: `access_token`, `refresh_token`, `token_type`
- `UserResponse`: `id`, `email`, `full_name`, `phone`, `role`, `is_active`, `last_login_at`, `created_at`

### 6.2. Users
- `UserCreate`: `email`, `password?`, `full_name`, `phone?`, `role`
- `UserUpdate`: `email?`, `full_name?`, `phone?`, `role?`
- `SetPassword`: `password`
- `ChangeOwnPassword`: `current_password`, `new_password`
- `UserResponse`: `id`, `email`, `full_name`, `phone?`, `role`, `is_active`, `can_login`, `last_login_at?`, `created_at`, `updated_at`
- `UserListFilters`: `role?`, `is_active?`, `search?`, `page`, `limit`

### 6.3. Terms & Pricing
- `TermCreate`: `year`, `term_number`, `display_name?`, `start_date?`, `end_date?`
- `TermUpdate`: `display_name?`, `start_date?`, `end_date?`
- `TermResponse`: `id`, `year`, `term_number`, `display_name`, `status`, `start_date?`, `end_date?`, `created_at`, `updated_at`
- `TermDetailResponse`: `TermResponse` + `price_settings[]`, `transport_pricings[]`
- `PriceSettingCreate`: `grade` (Grade.code), `school_fee_amount`
- `PriceSettingBulkUpdate`: `price_settings[]`
- `PriceSettingResponse`: `id`, `term_id`, `grade`, `school_fee_amount`
- `TransportZoneCreate`: `zone_name`, `zone_code`
- `TransportZoneUpdate`: `zone_name?`, `zone_code?`, `is_active?`
- `TransportZoneResponse`: `id`, `zone_name`, `zone_code`, `is_active`
- `TransportPricingCreate`: `zone_id`, `transport_fee_amount`
- `TransportPricingBulkUpdate`: `transport_pricings[]`
- `TransportPricingResponse`: `id`, `term_id`, `zone_id`, `zone_name`, `zone_code`, `transport_fee_amount`
- `FixedFeeCreate`: `fee_type`, `display_name`, `amount`
- `FixedFeeUpdate`: `display_name?`, `amount?`, `is_active?`
- `FixedFeeResponse`: `id`, `fee_type`, `display_name`, `amount`, `is_active`
  - Note: Fixed fees are stored as Kits in "Fixed Fees" category. Response fields map: `fee_type`=`sku_code`, `display_name`=`name`, `amount`=`price`

### 6.4. Items & Kits
- `CategoryCreate`: `name`
- `CategoryUpdate`: `name?`, `is_active?`
- `CategoryResponse`: `id`, `name`, `is_active`
- `ItemCreate`: `category_id`, `sku_code`, `name`, `item_type`, `price_type`, `price?`, `requires_full_payment?`
- `ItemUpdate`: `category_id?`, `name?`, `price?`, `requires_full_payment?`, `is_active?`
- `ItemResponse`: `id`, `category_id`, `category_name?`, `sku_code`, `name`, `item_type`, `price_type`, `price?`, `requires_full_payment`, `is_active`
- `ItemPriceHistoryResponse`: `id`, `item_id`, `price`, `effective_from`, `changed_by_id`
- `KitItemCreate`: `item_id`, `quantity`
- `KitItemUpdate`: `item_id`, `quantity`
- `KitCreate`: `category_id`, `sku_code?`, `name`, `item_type`, `price_type`, `price?`, `requires_full_payment?`, `items[]`
- `sku_code` для Kit можно не передавать — генерируется автоматически на бэке
- `KitUpdate`: `category_id?`, `name?`, `price?`, `requires_full_payment?`, `is_active?`, `items?`
- `KitItemResponse`: `id`, `item_id`, `item_name?`, `item_sku?`, `quantity`
- `KitResponse`: `id`, `category_id`, `category_name?`, `sku_code`, `name`, `item_type`, `price_type`, `price?`, `requires_full_payment`, `is_active`, `items[]`
- `KitPriceHistoryResponse`: `id`, `kit_id`, `price`, `effective_from`, `changed_by_id`

### 6.5. Students & Grades
- `GradeCreate`: `code`, `name`, `display_order`
- `GradeUpdate`: `code?`, `name?`, `display_order?`, `is_active?`
- `GradeResponse`: `id`, `code`, `name`, `display_order`, `is_active`
- `StudentCreate`: `first_name`, `last_name`, `date_of_birth?`, `gender`, `grade_id`, `transport_zone_id?`, `guardian_name`, `guardian_phone`, `guardian_email?`, `enrollment_date?`, `notes?`
- `StudentUpdate`: `first_name?`, `last_name?`, `date_of_birth?`, `gender?`, `grade_id?`, `transport_zone_id?`, `guardian_name?`, `guardian_phone?`, `guardian_email?`, `enrollment_date?`, `notes?`
- `StudentResponse`: `id`, `student_number`, `first_name`, `last_name`, `full_name`, `date_of_birth?`, `gender`, `grade_id`, `grade_name?`, `transport_zone_id?`, `transport_zone_name?`, `guardian_name`, `guardian_phone`, `guardian_email?`, `status`, `enrollment_date?`, `notes?`, `created_by_id`

### 6.6. Invoices
- `InvoiceCreate`: `student_id`, `due_date?`, `notes?`, `lines[]`
- `InvoiceLineCreate`: `kit_id`, `quantity`, `unit_price_override?`, `discount_amount?`
- `InvoiceLineDiscountUpdate`: `discount_amount`
- `IssueInvoiceRequest`: `due_date?`
- `TermInvoiceGenerationRequest`: `term_id`
- `TermInvoiceGenerationForStudentRequest`: `term_id`, `student_id`
- `TermInvoiceGenerationResult`: `school_fee_invoices_created`, `transport_invoices_created`, `students_skipped`, `total_students_processed`
- Admission/Interview fee можно выставить только один раз на студента (проверка по `invoice_line`, даже если invoice cancelled/void)
- `InvoiceResponse`: `id`, `invoice_number`, `student_id`, `student_name?`, `student_number?`, `term_id?`, `term_name?`, `invoice_type`, `status`, `issue_date?`, `due_date?`, `subtotal`, `discount_total`, `total`, `paid_total`, `amount_due`, `notes?`, `created_by_id`, `lines[]`
- `InvoiceLineResponse`: `id`, `invoice_id`, `kit_id`, `description`, `quantity`, `unit_price`, `line_total`, `discount_amount`, `net_amount`, `paid_amount`, `remaining_amount`
- `InvoiceSummary`: `id`, `invoice_number`, `student_id`, `student_name?`, `invoice_type`, `status`, `total`, `paid_total`, `amount_due`, `issue_date?`, `due_date?`

### 6.7. Discounts
- `DiscountReasonCreate`: `code`, `name`
- `DiscountReasonUpdate`: `code?`, `name?`, `is_active?`
- `DiscountReasonResponse`: `id`, `code`, `name`, `is_active`
- `DiscountApply`: `invoice_line_id`, `value_type`, `value`, `reason_id?`, `reason_text?`
- `DiscountResponse`: `id`, `invoice_line_id`, `value_type`, `value`, `calculated_amount`, `reason_id?`, `reason_name?`, `reason_text?`, `student_discount_id?`, `applied_by_id`
- `StudentDiscountCreate`: `student_id`, `applies_to`, `value_type`, `value`, `reason_id?`, `reason_text?`
- `StudentDiscountUpdate`: `value_type?`, `value?`, `reason_id?`, `reason_text?`, `is_active?`
- `StudentDiscountResponse`: `id`, `student_id`, `student_name?`, `applies_to`, `value_type`, `value`, `reason_id?`, `reason_name?`, `reason_text?`, `is_active`, `created_by_id`

### 6.8. Payments & Allocations
- `PaymentCreate`: `student_id`, `preferred_invoice_id?`, `amount`, `payment_method`, `payment_date`, `reference?`, `confirmation_attachment_id?`, `notes?` — обязательно **либо** reference, **либо** confirmation_attachment_id.
- `PaymentUpdate`: поддерживает `preferred_invoice_id?`; pending payment можно перепривязать к другому invoice или очистить привязку
- `PaymentResponse`: дополнительно отдаёт `preferred_invoice_id?` и `preferred_invoice_number?`
- При `POST /payments/{payment_id}/complete`, если у payment есть `preferred_invoice_id`, backend сначала создаёт manual allocation на этот invoice в пределах суммы платежа и только потом запускает обычный auto-allocation на остаток
- `PaymentUpdate`: `amount?`, `preferred_invoice_id?`, `payment_method?`, `payment_date?`, `reference?`, `notes?`
- `PaymentResponse`: `id`, `payment_number`, `receipt_number?`, `student_id`, `student_name?`, `student_number?`, `preferred_invoice_id?`, `preferred_invoice_number?`, `amount`, `payment_method`, `payment_date`, `reference?`, `confirmation_attachment_id?`, `status`, `notes?`, `received_by_id`, `created_at`, `updated_at`
- `AttachmentResponse`: `id`, `file_name`, `content_type`, `file_size`, `created_at` (ответ POST /attachments и GET /attachments/{id})
- `AllocationCreate`: `student_id?`, `billing_account_id?`, `invoice_id`, `invoice_line_id?`, `amount`
- `AllocationResponse`: `id`, `student_id`, `billing_account_id`, `invoice_id`, `invoice_line_id?`, `amount`, `allocated_by_id`, `created_at`
- `AutoAllocateRequest`: `student_id?`, `billing_account_id?`, `max_amount?`
- `AutoAllocateResult`: `total_allocated`, `invoices_fully_paid`, `invoices_partially_paid`, `remaining_balance`, `allocations[]`
- `StudentBalance`: `student_id`, `total_payments`, `total_allocated`, `available_balance`, `outstanding_debt`, `balance` (net: available_balance − outstanding_debt, считается на бэкенде)
- `StatementResponse`: `student_id`, `student_name`, `period_from`, `period_to`, `opening_balance`, `total_credits`, `total_debits`, `closing_balance`, `entries[]`
- `StatementEntry`: `date`, `entry_type`, `payment_id?`, `allocation_id?`, `invoice_id?`, `description`, `reference?`, `credit?`, `debit?`, `balance`

### 6.9. Inventory
- `ReceiveStockRequest`: `item_id`, `quantity`, `unit_cost`, `reference_type?`, `reference_id?`, `notes?`
- `AdjustStockRequest`: `item_id`, `quantity`, `reason`, `reference_type?`, `reference_id?`
- `WriteOffRequest`: `items[]` (каждый: `item_id`, `quantity`, `reason_category`, `reason_detail?`)
- `InventoryCountRequest`: `items[]` (каждый: `item_id`, `actual_quantity`)
- `IssueStockRequest`: `item_id`, `quantity`, `reference_type?`, `reference_id?`, `notes?`
- `StockResponse`: `id`, `item_id`, `item_sku?`, `item_name?`, `quantity_on_hand`, `quantity_owed`, `quantity_available`, `average_cost`
- `StockMovementResponse`: `id`, `stock_id`, `item_id`, `item_sku?`, `item_name?`, `movement_type`, `quantity`, `unit_cost?`, `quantity_before`, `quantity_after`, `average_cost_before`, `average_cost_after`, `reference_type?`, `reference_id?`, `notes?`, `created_by_id`, `created_by_name?`, `created_at`
- `WriteOffResponse`: `movements[]`, `total`
- `InventoryCountResponse`: `movements[]`, `adjustments_created`, `total_variance`
- `InternalIssuanceCreate`: `recipient_type` (employee | student | other), `recipient_id?` (обязателен для employee/student, не передавать для other), `recipient_name`, `items[]`, `notes?`
- `IssuanceItemCreate`: `item_id`, `quantity`
- `IssuanceResponse`: `id`, `issuance_number`, `issuance_type`, `recipient_type`, `recipient_id?` (null для other), `recipient_name`, `reservation_id?`, `issued_by_id`, `issued_by_name?`, `issued_at`, `notes?`, `status`, `items[]`

### 6.10. Reservations
- `ReservationIssueRequest`: `items[]` (каждый: `reservation_item_id`, `quantity`), `notes?`
- `ReservationCancelRequest`: `reason?`
- `ReservationResponse`: `id`, `student_id`, `invoice_id`, `invoice_line_id`, `status`, `created_by_id`, `created_at`, `updated_at`, `items[]`
- `ReservationItemResponse`: `id`, `item_id`, `item_sku?`, `item_name?`, `quantity_required`, `quantity_issued`

### 6.11. Procurement
- `PurchaseOrderCreate`: `supplier_name`, `supplier_contact?`, `purpose_id`, `order_date?`, `expected_delivery_date?`, `track_to_warehouse`, `notes?`, `lines[]`
- `PurchaseOrderLineCreate`: `item_id?`, `description`, `quantity_expected`, `unit_price`
- `PurchaseOrderUpdate`: `supplier_name?`, `supplier_contact?`, `purpose_id?`, `order_date?`, `expected_delivery_date?`, `track_to_warehouse?`, `notes?`, `lines?`
- `PurchaseOrderLineUpdate`: `item_id?`, `description?`, `quantity_expected?`, `unit_price?`
- `PurchaseOrderResponse`: `id`, `po_number`, `supplier_name`, `supplier_contact?`, `purpose_id`, `status`, `order_date`, `expected_delivery_date?`, `track_to_warehouse`, `expected_total`, `received_value`, `paid_total`, `debt_amount`, `forecast_debt`, `notes?`, `cancelled_reason?`, `created_by_id`, `created_at`, `updated_at`, `lines[]`
- `PurchaseOrderLineResponse`: `id`, `item_id?`, `description`, `quantity_expected`, `quantity_cancelled`, `quantity_received`, `unit_price`, `line_total`, `line_order`
- `CancelPurchaseOrderRequest`: `reason`
- `GoodsReceivedNoteCreate`: `po_id`, `received_date?`, `notes?`, `lines[]`
- `GoodsReceivedLineCreate`: `po_line_id`, `quantity_received`
- `GoodsReceivedNoteResponse`: `id`, `grn_number`, `po_id`, `status`, `received_date`, `received_by_id`, `approved_by_id?`, `approved_at?`, `notes?`, `created_at`, `updated_at`, `lines[]`
- `GoodsReceivedLineResponse`: `id`, `po_line_id`, `item_id?`, `quantity_received`
- `PaymentPurposeCreate`: `name`
- `PaymentPurposeUpdate`: `name?`, `is_active?`
- `PaymentPurposeResponse`: `id`, `name`, `is_active`, `created_at`, `updated_at`
- `ProcurementPaymentCreate`: `po_id?`, `purpose_id?`, `payee_name?`, `payment_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `company_paid`, `employee_paid_id?`, `budget_id?`, `funding_source` (`personal_funds | budget`)
- `ProcurementPaymentResponse`: `id`, `payment_number`, `po_id?`, `purpose_id`, `purpose_name?`, `payee_name?`, `payment_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `company_paid`, `employee_paid_id?`, `budget_id?`, `budget_number?`, `budget_name?`, `funding_source`, `status`, `cancelled_reason?`, `cancelled_by_id?`, `cancelled_at?`, `created_by_id`, `created_at`, `updated_at`
- `CancelProcurementPaymentRequest`: `reason`

### 6.12. Compensations
- `ExpenseClaimResponse`: `id`, `claim_number`, `payment_id?`, `employee_id`, `employee_name`, `purpose_id`, `amount`, `payee_name?`, `description`, `rejection_reason?`, `edit_comment?`, `expense_date`, `proof_text?`, `proof_attachment_id?`, `status`, `paid_amount`, `remaining_amount`, `auto_created_from_payment`, `related_procurement_payment_id?`, `created_at`, `updated_at`
- `ExpenseClaimCreate`: `employee_id?`, `purpose_id`, `amount`, `payee_name?`, `description`, `expense_date`, `proof_text?`, `proof_attachment_id?`, `submit` (default true; если false — создаёт draft без proof)
- `ExpenseClaimUpdate`: `employee_id?`, `purpose_id?`, `amount?`, `payee_name?`, `description?`, `expense_date?`, `proof_text?`, `proof_attachment_id?`, `submit?` (если true — переводит draft в pending_approval и требует proof)
- `ApproveExpenseClaimRequest`: `approve`, `reason?` (для reject сохраняется в `rejection_reason`, описание не меняется)
- `SendToEditExpenseClaimRequest`: `comment` (обязательное поле)
- `CompensationPayoutCreate`: `employee_id`, `payout_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`
- `CompensationPayoutResponse`: `id`, `payout_number`, `employee_id`, `payout_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `created_at`, `updated_at`, `allocations[]`
- `PayoutAllocationResponse`: `id`, `claim_id`, `allocated_amount`
- `EmployeeBalanceResponse`: `employee_id`, `total_approved`, `total_paid`, `balance`

### 6.12.1. Budgets / Budget Advances Schemas

- `BudgetResponse`: `id`, `budget_number`, `name`, `purpose_id`, `purpose_name?`, `period_from`, `period_to`, `limit_amount`, `notes?`, `status`, `created_by_id`, `approved_by_id?`, `created_at`, `updated_at`, `direct_company_paid_total`, `direct_issue_total`, `transfer_in_total`, `returned_total`, `transfer_out_total`, `reserved_total`, `settled_total`, `committed_total`, `open_on_hands_total`, `available_unreserved_total`, `available_to_issue`, `overdue_advances_count`
- `BudgetAdvanceResponse`: `id`, `advance_number`, `budget_id`, `budget_number`, `budget_name`, `employee_id`, `employee_name`, `issue_date`, `amount_issued`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `notes?`, `source_type` (`cash_issue | transfer_in`), `settlement_due_date`, `status`, `created_by_id`, `created_at`, `updated_at`, `reserved_amount`, `settled_amount`, `returned_amount`, `transferred_out_amount`, `open_balance`, `available_unreserved_amount`
- `BudgetAdvanceReturnResponse`: `id`, `return_number`, `advance_id`, `return_date`, `amount`, `return_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `notes?`, `created_by_id`, `created_at`
- `BudgetAdvanceTransferResponse`: `id`, `transfer_number`, `from_advance_id`, `from_advance_number`, `to_budget_id`, `to_budget_number`, `to_employee_id`, `to_employee_name?`, `transfer_date`, `amount`, `transfer_type` (`rollover | reassignment | reallocation`), `reason`, `created_to_advance_id`, `created_to_advance_number`, `created_by_id`, `created_at`
- `BudgetClaimAllocationResponse`: `id`, `advance_id`, `advance_number`, `claim_id`, `allocated_amount`, `allocation_status` (`reserved | settled | released`), `released_reason?`, `created_at`, `updated_at`

Related schema extensions:

- `ExpenseClaimCreate`: + `funding_source`, `budget_id?`
- `ExpenseClaimUpdate`: + `funding_source?`, `budget_id?`
- `ExpenseClaimResponse`: + `budget_id?`, `budget_funding_status?`, `budget_allocations[]?`
- `ProcurementPaymentCreate` / `ProcurementPaymentResponse`: + `funding_source`, `budget_id?`, `budget_number?`, `budget_name?`

Semantics:

- `funding_source=personal_funds` — reimbursement flow;
- `funding_source=budget` + `company_paid=false` — claim / payment closes against earlier budget advances;
- `funding_source=budget` + `company_paid=true` — direct company-paid budget spend through procurement payments.
