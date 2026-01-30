# Backend API (консолидированная документация)

Актуальная сводка по бэкенду: структуры, правила и все API‑эндпоинты.
Спецификация `erp_spec.md` и статус/решения в `TASKS.md` сведены сюда, чтобы читать было удобно.

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
- **Allocation priority:** Kit с `requires_full_payment` оплачиваются полностью раньше услуг
- **Credit balance:** вычисляется как `SUM(completed payments) - SUM(allocations)`
- **Invoice issue:** при выставлении счёта (POST `.../issue`) автоматически вызывается авто-аллокация баланса ученика — существующий положительный баланс списывается на новый и другие неоплаченные счета.
- **Employee balance:** при запросе баланса сотрудника (`GET .../payouts/employees/{id}/balance`) баланс всегда пересчитывается по одобренным claims и выплатам (approved claims − payouts).
- **Reservation:** создаётся при полной оплате line с Kit (product), выдача частями
- **Catalog:** продажи идут через `Kit` (invoice lines используют только `kit_id`)
- **Stock:** остатки не могут уходить в минус
- **Cancellations:** по причине, данные не удаляются

## 4. Enum‑значения (сокращённо)

- **StudentStatus:** `active`, `inactive`
- **Gender:** `male`, `female`
- **TermStatus:** `Draft`, `Active`, `Closed`
- **InvoiceType:** `school_fee`, `transport`, `adhoc`
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
- **ExpenseClaimStatus:** `draft`, `pending_approval`, `approved`, `rejected`, `partially_paid`, `paid`
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
- `POST /items/kits`
- `GET /items/kits`
- `GET /items/kits/{kit_id}`
- `PATCH /items/kits/{kit_id}`
- `GET /items/kits/{kit_id}/price-history`

### 5.5. Students & Grades
- `POST /students/grades`
- `GET /students/grades`
- `GET /students/grades/{grade_id}`
- `PATCH /students/grades/{grade_id}`
- `POST /students`
- `GET /students` — filters: `status`, `grade_id`, `transport_zone_id`, `search`, `page`, `limit`
- `GET /students/{student_id}`
- `PATCH /students/{student_id}`
- `POST /students/{student_id}/activate`
- `POST /students/{student_id}/deactivate`

### 5.6. Invoices
- `POST /invoices`
- `GET /invoices` — filters: `student_id`, `term_id`, `invoice_type`, `status`, `search`, `page`, `limit`
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
- `POST /attachments` — загрузка файла подтверждения (image/PDF). Тело: `multipart/form-data`, поле `file`. Допустимые типы: image/jpeg, image/png, image/gif, image/webp, application/pdf. Макс. 10 MB. Ответ: `{ id, file_name, content_type, file_size, created_at }`. Роль: Admin, User.
- `GET /attachments/{attachment_id}` — метаданные вложения.
- `GET /attachments/{attachment_id}/download` — скачать файл (для просмотра подтверждения). Роль: любой авторизованный.

### 5.9. Payments & Allocations
- `POST /payments` — обязателен **либо** `reference`, **либо** `confirmation_attachment_id` (подтверждение файлом).
- `GET /payments` — filters: `student_id`, `status`, `payment_method`, `date_from`, `date_to`, `page`, `limit`
- `GET /payments/{payment_id}`
- `PATCH /payments/{payment_id}`
- `POST /payments/{payment_id}/complete`
- `POST /payments/{payment_id}/cancel`
- `GET /payments/students/{student_id}/balance`
- `GET /payments/students/{student_id}/statement` — `date_from`, `date_to`
- `POST /payments/allocations/auto`
- `POST /payments/allocations/manual`
- `DELETE /payments/allocations/{allocation_id}`

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
- `POST /procurement/payment-purposes`
- `GET /procurement/payment-purposes`
- `PUT /procurement/payment-purposes/{purpose_id}`
- `POST /procurement/payments`
- `GET /procurement/payments` — filters: `po_id`, `purpose_id`, `status`, `date_from`, `date_to`, `page`, `limit`
- `GET /procurement/payments/{payment_id}`
- `POST /procurement/payments/{payment_id}/cancel`

### 5.13. Compensations
- `GET /compensations/claims` — filters: `employee_id`, `status`, `date_from`, `date_to`, `page`, `limit`
- `GET /compensations/claims/{claim_id}`
- `POST /compensations/claims/{claim_id}/approve`
- `POST /compensations/payouts`
- `GET /compensations/payouts` — filters: `employee_id`, `date_from`, `date_to`, `page`, `limit`
- `GET /compensations/payouts/{payout_id}`
- `GET /compensations/payouts/employees/{employee_id}/balance`

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
- `PaymentCreate`: `student_id`, `amount`, `payment_method`, `payment_date`, `reference?`, `confirmation_attachment_id?`, `notes?` — обязательно **либо** reference, **либо** confirmation_attachment_id.
- `PaymentUpdate`: `amount?`, `payment_method?`, `payment_date?`, `reference?`, `notes?`
- `PaymentResponse`: `id`, `payment_number`, `receipt_number?`, `student_id`, `amount`, `payment_method`, `payment_date`, `reference?`, `confirmation_attachment_id?`, `status`, `notes?`, `received_by_id`, `created_at`, `updated_at`
- `AttachmentResponse`: `id`, `file_name`, `content_type`, `file_size`, `created_at` (ответ POST /attachments и GET /attachments/{id})
- `AllocationCreate`: `student_id`, `invoice_id`, `invoice_line_id?`, `amount`
- `AllocationResponse`: `id`, `student_id`, `invoice_id`, `invoice_line_id?`, `amount`, `allocated_by_id`, `created_at`
- `AutoAllocateRequest`: `student_id`, `max_amount?`
- `AutoAllocateResult`: `total_allocated`, `invoices_fully_paid`, `invoices_partially_paid`, `remaining_balance`, `allocations[]`
- `StudentBalance`: `student_id`, `total_payments`, `total_allocated`, `available_balance`
- `StatementResponse`: `student_id`, `student_name`, `period_from`, `period_to`, `opening_balance`, `total_credits`, `total_debits`, `closing_balance`, `entries[]`
- `StatementEntry`: `date`, `description`, `reference?`, `credit?`, `debit?`, `balance`

### 6.9. Inventory
- `ReceiveStockRequest`: `item_id`, `quantity`, `unit_cost`, `reference_type?`, `reference_id?`, `notes?`
- `AdjustStockRequest`: `item_id`, `quantity`, `reason`, `reference_type?`, `reference_id?`
- `WriteOffRequest`: `items[]` (каждый: `item_id`, `quantity`, `reason_category`, `reason_detail?`)
- `InventoryCountRequest`: `items[]` (каждый: `item_id`, `actual_quantity`)
- `IssueStockRequest`: `item_id`, `quantity`, `reference_type?`, `reference_id?`, `notes?`
- `StockResponse`: `id`, `item_id`, `item_sku?`, `item_name?`, `quantity_on_hand`, `quantity_reserved`, `quantity_available`, `average_cost`
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
- `ReservationItemResponse`: `id`, `item_id`, `item_sku?`, `item_name?`, `quantity_required`, `quantity_reserved`, `quantity_issued`

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
- `ProcurementPaymentCreate`: `po_id?`, `purpose_id?`, `payee_name?`, `payment_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `company_paid`, `employee_paid_id?`
- `ProcurementPaymentResponse`: `id`, `payment_number`, `po_id?`, `purpose_id`, `payee_name?`, `payment_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `company_paid`, `employee_paid_id?`, `status`, `cancelled_reason?`, `cancelled_by_id?`, `cancelled_at?`, `created_by_id`, `created_at`, `updated_at`
- `CancelProcurementPaymentRequest`: `reason`

### 6.12. Compensations
- `ExpenseClaimResponse`: `id`, `claim_number`, `payment_id`, `employee_id`, `purpose_id`, `amount`, `description`, `expense_date`, `status`, `paid_amount`, `remaining_amount`, `auto_created_from_payment`, `related_procurement_payment_id?`, `created_at`, `updated_at`
- `ApproveExpenseClaimRequest`: `approve`, `reason?`
- `CompensationPayoutCreate`: `employee_id`, `payout_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`
- `CompensationPayoutResponse`: `id`, `payout_number`, `employee_id`, `payout_date`, `amount`, `payment_method`, `reference_number?`, `proof_text?`, `proof_attachment_id?`, `created_at`, `updated_at`, `allocations[]`
- `PayoutAllocationResponse`: `id`, `claim_id`, `allocated_amount`
- `EmployeeBalanceResponse`: `employee_id`, `total_approved`, `total_paid`, `balance`
