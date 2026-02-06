# Backend Overview (смыслы и процессы)

Краткая и структурированная «картина мира» для UI и аналитики: зачем
нужны сущности, как они связаны, какие ключевые правила действуют.

## 1. Домены

### Students & Billing
- **Student**: основной субъект, на него оформляются счета и платежи.
- **Term**: учебный период. Только один активный.
- **Invoice/InvoiceLine**: начисления. Счёт нельзя редактировать после `issued`.
- **Payment/CreditAllocation**: оплата сначала попадает в кредит, затем аллоцируется.
- **Discount/StudentDiscount**: скидки на строку или постоянные скидки на студента.

### Inventory & Warehouse
- **Item/Kit/Category**: складские позиции (Item) и каталог продаж (Kit).
  - Kits могут быть **обычными** (фиксированный состав) или **editable uniform kits**:
    - продажа всегда идёт по `kit_id` и фиксированной цене кита;
    - для editable kit при продаже можно поменять **только модель/размер** внутри каждого компонента, состав и количество берутся из кита.
- **Stock/StockMovement**: остатки и движения. Остатки не уходят в минус.
- **Issuance**: выдача (внутренняя или по резервации).
- **Reservation**: создаётся сразу после issue инвойса по строкам с Kit (product), до оплаты.

### Procurement & Expenses
- **PurchaseOrder** → **GRN** → **ProcurementPayment** — цепочка закупки.
- **PaymentPurpose**: справочник назначения платежа.

### Bank Statements / Reconciliation
- **BankStatementImport**: загруженная выписка (CSV как Attachment) + вычисленный диапазон `range_from/range_to` по min/max `Value Date`.
- **BankTransaction**: каноническая транзакция (дедуп между перекрывающимися выписками).
- **BankTransactionMatch**: связь bank transaction ↔ `ProcurementPayment(company_paid=true)` или ↔ `CompensationPayout`.

### Employee Compensations
- **ExpenseClaim**: заявка на компенсацию (обычно из employee_paid платежа).
- **CompensationPayout**: выплаты сотруднику с FIFO‑аллокацией по claims.
- **EmployeeBalance**: агрегированный баланс сотрудника.

## 2. Основные жизненные циклы

### Term
`Draft → Active → Closed`
- Активируется вручную, предыдущий активный терм закрывается автоматически.
- В закрытом терме нельзя создавать инвойсы, но платежи принимать можно.

### Invoice
`draft → issued → partially_paid → paid`
- `cancelled` — если оплат нет.
- `void` — если были оплаты (через отмену платежей/аллокаций).
 - Term invoices можно генерировать для всех активных студентов или для одного студента (роль: `SUPER_ADMIN` или `ADMIN`).
 - В bulk‑генерации студент пропускается, если нет price settings для его grade/zone.
 - Если у студента ещё не было admission/interview (по наличию invoice_line, даже если invoice cancelled/void), генерация создаёт отдельный invoice с двумя строками.

### Payment
`pending → completed | cancelled`
- Редактировать нельзя, только отмена (с причиной).

### Reservation
`pending → partial → fulfilled | cancelled`
- Создаётся при полной оплате строки с Kit (product).
- Выдача частями через Issuance.

### Procurement
`PurchaseOrder: draft → ordered → partially_received → received → closed/cancelled`
`GRN: draft → approved | cancelled`
`ProcurementPayment: posted → cancelled`

### Compensation
`ExpenseClaim: pending_approval → approved/rejected → partially_paid → paid`
`CompensationPayout` создаётся и распределяет сумму FIFO по claim.

### Bank reconciliation
`BankStatementImport` создаётся загрузкой CSV (Admin/SuperAdmin) и парсит транзакции в `BankTransaction` (debits/credits).
Для reconciliation используем только **исходящие** транзакции (debits). Матчинг:
- auto‑match по сумме/дате + эвристики по reference (только если однозначный кандидат),
- manual match/unmatch (Admin/SuperAdmin).

## 3. Ключевые бизнес‑правила

### Платежи и аллокации
- Оплата всегда идёт через **credit balance**.
- **Auto‑allocation** (только бэкенд):
  1) счета с `requires_full_payment` — в приоритете, допускается частичная оплата (выдача/резерв — только при полной);
  2) счета с `partial_ok` — остаток распределяется пропорционально по `amount_due`.
- Триггеры: при `payment complete` и при любом переводе счёта в Issued (одиночный issue, массовая генерация, генерация по студенту).
- Излишки остаются в кредите.

### Склад
- Остаток не может быть отрицательным.
- Любое движение фиксируется в `StockMovement`.
- Резервирование снижает доступный остаток.
- Для **editable uniform kits**:
  - InvoiceLine хранит только `kit_id`, но фактический состав строки — в `InvoiceLineComponent`;
  - Reservation всегда резервирует **конкретные Items**: либо по `InvoiceLineComponent`, либо по `Kit.kit_items` (если компонентов нет).

### Скидки
- Скидка может быть фиксированной или процентной.
- Скидки на строку влияют на `net_amount`.
- `StudentDiscount` авто‑применяется при генерации терм‑счетов.

### Нумерация документов
- Формат: `PREFIX-YYYY-NNNNNN`.
- Генерация централизована.

## 4. Формулы и расчёты (кратко)

- `line_total = quantity × unit_price`
- `invoice.total = subtotal - discount_total`
- `amount_due = total - paid_total`
- `credit = sum(completed payments) - sum(allocations)`

## 5. Безопасность и аудит

- Проверка роли на каждом endpoint.
- Финансовые и складские операции логируются.
- Критические отмены требуют причины.

## 6. Что важно для UI

- Все списки возвращаются в `PaginatedResponse`.
- У сущностей есть статусы: UI должен отображать и фильтровать по ним.
- Частые операции вынесены в отдельные экшн‑эндпоинты:
  `issue`, `cancel`, `approve`, `complete`, `allocate`.
