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

### Planned Extension: Budget Advances (not implemented yet)
- Целевой дизайн зафиксирован в `docs/BUDGET_ADVANCES_PLAN.md`.
- **Budget**: бюджет направления расходов на период (например, kitchen supplies / месяц).
- **BudgetAdvance**: выдача денег конкретному сотруднику под этот budget.
- **BudgetAdvanceReturn**: возврат неиспользованных денег.
- **BudgetAdvanceTransfer**: rollover / reassignment / reallocation остатка между периодами и/или сотрудниками.
- **BudgetClaimAllocation**: reserve и final settlement claim из ранее выданных advances.
- Важно: budget-funded claims не должны идти через `CompensationPayout`; payout остаётся только reimbursement-механизмом.

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

- **Update PO (Admin/SuperAdmin):**
  - `Admin` может редактировать только `draft` и `ordered`.
  - `partially_received` и `received` может редактировать только `SuperAdmin`.
  - `closed` и `cancelled` редактировать нельзя.
  - Линии обновляются **по существующему `line.id`**, а не через delete/recreate всего заказа.
  - Нельзя уменьшить `quantity_expected` ниже уже принятого `quantity_received`.
  - Нельзя уменьшить итоговый `expected_total` ниже уже внесённого `paid_total`.
  - Нельзя удалить строку или сменить её `item_id`, если по ней уже есть GRN history / received quantity.
- **Rollback receiving (SUPER_ADMIN):** если GRN уже был approved, но позже обнаружили ошибку, можно сделать откат через `POST /procurement/grns/{grn_id}/rollback`.
  - Операция отменяет этот GRN, откатывает `quantity_received` по линиям PO и (если `track_to_warehouse=true`) создаёт компенсационные `StockMovement(receipt)` с отрицательным количеством, чтобы вернуть склад и average cost.
  - Ограничения безопасности: по затронутым items не должно быть более поздних `receipt` movements. Если по PO уже есть оплаты (`paid_total > 0`), откат всё равно возможен — после rollback `debt_amount` может стать отрицательным (аванс поставщику: “paid, not received”).

### Compensation
`ExpenseClaim: pending_approval → needs_edit → pending_approval → approved/rejected → partially_paid → paid`
`CompensationPayout` создаётся и распределяет сумму FIFO по claim.
- `send-to-edit` доступен только `SuperAdmin`, требует комментарий и применяется только к ручным out-of-pocket claims (`auto_created_from_payment=false`).

### Planned: Budget Advances (not implemented yet)
`Budget: draft → active → closing → closed/cancelled`
`BudgetAdvance: draft → issued → overdue → settled/closed/cancelled`

- Budget живёт на уровне направления расходов, а не сотрудника.
- Claim выбирает `budget`, а backend сам резервирует и затем аллоцирует его по open advances сотрудника FIFO.
- Budget-funded claim после approve считается сразу `paid`: компания уже не должна сотруднику деньги, funding был выдан раньше.
- Конец месяца не закрывает open advances автоматически: остаток должен быть либо возвращён, либо перенесён через `BudgetAdvanceTransfer`, либо закрыт claims.
- Rollover между месяцами допустим только через отдельный transfer-документ; старый advance не переписывается и не меняет `budget_id`.

### Bank reconciliation
`BankStatementImport` создаётся загрузкой CSV (Admin/SuperAdmin) и парсит транзакции в `BankTransaction` (debits/credits).
Для reconciliation используем только **исходящие** транзакции (debits). Матчинг:
- auto‑match по сумме/дате + эвристики по reference (только если однозначный кандидат),
- manual match/unmatch (Admin/SuperAdmin).

Planned extension:
- outgoing transactions смогут матчиться не только на `ProcurementPayment(company_paid=true)` и `CompensationPayout`, но и на `BudgetAdvance`;
- incoming transactions для returns смогут матчиться на `BudgetAdvanceReturn`.

## 3. Ключевые бизнес‑правила

### Платежи и аллокации
- Оплата всегда идёт через **credit balance**.
- **Auto‑allocation** (только бэкенд):
  1) счета с `requires_full_payment` — в приоритете, допускается частичная оплата (выдача/резерв — только при полной);
  2) счета с `partial_ok` — остаток распределяется пропорционально по `amount_due`.
- Аллокация может быть привязана ко всему invoice или к конкретной строке; если она invoice-level, `line.paid_amount` синхронизируется пропорционально по оставшимся `net_amount` строк.
- Триггеры: при `payment complete`, при любом переводе счёта в Issued (одиночный issue, массовая генерация, генерация по студенту) и после скидки, если она освободила часть уже направленных аллокаций.
- Если скидка уменьшила `net_amount`/`invoice.total` ниже уже allocated суммы, лишние allocations сначала снимаются с этого invoice, после чего сразу запускается обычный auto-allocation на другие открытые invoices ученика; только нераспределённый остаток остаётся в кредите.

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
- Header-поля invoice (`discount_total`, `total`, `amount_due`) являются агрегатами, производными от строк и allocations.
- Для partially paid / paid-over-allocated кейса скидка сначала освобождает лишние allocations, затем система немедленно прогоняет standard auto-allocation по другим открытым счетам ученика.
- На `paid` invoice скидку может применить только `SuperAdmin`; обычный `Admin` на таких счетах заблокирован.
- `StudentDiscount` авто‑применяется при генерации терм‑счетов.

### Нумерация документов
- Формат: `PREFIX-YYYY-NNNNNN`.
- Генерация централизована.

## 4. Формулы и расчёты (кратко)

- `line_total = quantity × unit_price`
- `net_amount = line_total - discount_amount`
- `remaining_amount = net_amount - paid_amount`
- `invoice.total = subtotal - discount_total`
- `amount_due = total - paid_total`
- `credit = sum(completed payments) - sum(allocations)`
- Для summary/open debt безопасный source of truth: суммы по `invoice_lines.net_amount` и `invoice_lines.remaining_amount`; header aggregates могут быть исторически stale.

## 5. Безопасность и аудит

- Проверка роли на каждом endpoint.
- Финансовые и складские операции логируются.
- Критические отмены требуют причины.

## 6. Что важно для UI

- Все списки возвращаются в `PaginatedResponse`.
- У сущностей есть статусы: UI должен отображать и фильтровать по ним.
- Частые операции вынесены в отдельные экшн‑эндпоинты:
  `issue`, `cancel`, `approve`, `complete`, `allocate`.
