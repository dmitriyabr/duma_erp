# Задачи по разработке ERP

Статусы: `[ ]` — не начато, `[~]` — в работе, `[x]` — готово, `[?]` — требует обсуждения

---

## Фаза 0: Фундамент (Core)

### 0.1 Структура проекта
- [x] Создать структуру папок проекта
- [x] Настроить pyproject.toml / package.json (зависимости)
- [x] Настроить линтер и форматтер (ruff)
- [x] Создать docker-compose для PostgreSQL (dev окружение)

### 0.2 База данных
- [x] Настроить подключение к БД (SQLAlchemy async)
- [x] Создать базовую модель (BaseModel с id, created_at, updated_at)
- [x] Настроить миграции (Alembic async)

### 0.3 Аутентификация
- [x] Реализовать JWT генерацию и валидацию (access 15 мин, refresh 7 дней, без 2FA)
- [x] Middleware проверки токена
- [x] Middleware проверки ролей (SuperAdmin, Admin, User, Accountant)
- [x] Endpoints: login, refresh, me (logout не нужен для stateless JWT)
- [x] Тесты auth

### 0.4 Аудит-лог
- [x] Модель AuditLog
- [x] Сервис create_audit_log(user, action, entity_type, entity_id, old_values, new_values)
- [ ] Тесты аудита

### 0.5 Генератор номеров документов
- [x] Сервис generate_document_number(prefix) → PREFIX-YYYY-NNNNNN
- [x] Хранение последовательностей по prefix+year
- [x] Тесты генератора

### 0.6 Общие утилиты
- [x] Функция округления денег (ROUND_HALF_UP, 2 знака)
- [x] Кастомные исключения (ValidationError, NotFoundError, InsufficientStockError)
- [x] Базовые Pydantic схемы (PaginatedResponse, ErrorResponse)
- [x] Тесты round_money

### 0.7 Рефакторинг API перед UI
- [x] Унифицировать формат ответов: один стандарт (ApiResponse с data) для всех endpoints
- [x] Унифицировать пагинацию: выбрать единый подход (page/limit) и привести все списки к нему
- [x] Привести list responses к единому виду (PaginatedResponse внутри data)
- [x] Добавить глобальные обработчики ошибок для RequestValidationError и HTTPException в ErrorResponse
- [x] Добавить CORS middleware и настройки окружения для UI (allowed origins)

### 0.8 Документация
- [x] Свести актуальную документацию бэка в одном файле (включая все API)
- [x] Добавить обзор смыслов/процессов в отдельном файле

---

## Фаза 1: Справочники

### 1.1 Пользователи (Users)
> Решения: User = сотрудник, password_hash nullable, только SuperAdmin создаёт, деактивация вместо удаления

- [x] Модель User (password_hash nullable, can_login property)
- [x] CRUD сервис (UserService)
- [x] API endpoints (GET list, GET by id, POST, PUT, deactivate/activate, set/remove/change password)
- [x] Хеширование паролей (bcrypt)
- [x] Seed первого SuperAdmin в миграции (admin@school.com / Admin123!)
- [x] Тесты

### 1.2 Триместры (Terms)
> Решения: Только один Active терм, при активации — старый Closed, автокопирование цен

- [x] Модель Term (year, term_number, display_name, status, start_date, end_date)
- [x] CRUD сервис (TermService)
- [x] Логика: только один Active терм, автозакрытие предыдущего
- [x] Копирование цен при создании терма
- [x] API endpoints (CRUD terms, activate, close, price-settings, transport-pricing)
- [x] Тесты

### 1.3 Настройки цен (Pricing)
- [x] Модель PriceSettings (term_id, grade, school_fee_amount)
- [x] Модель TransportZone (zone_name, zone_code, is_active)
- [x] Модель TransportPricing (term_id, zone_id, transport_fee_amount)
- [x] ~~Модель FixedFees~~ → Refactored: now stored as Kits in "Fixed Fees" category
- [x] Копирование цен из предыдущего терма (в TermService.create_term)
- [x] API endpoints (в terms router)
- [x] Seed данные: 3 зоны транспорта, 2 фиксированных сбора
- [x] Тесты

### 1.4 Категории товаров (Categories)
> Решения: Плоский список без иерархии

- [x] Модель Category (name, is_active)
- [x] CRUD сервис (в ItemService)
- [x] API endpoints
- [x] Seed данные в миграции
- [x] Тесты

### 1.5 Товары/SKU (Items)
> Решения: item_type: service|product, price_type: standard|by_grade|by_zone, история цен

- [x] Модель Item (category_id, sku_code, name, item_type, price_type, price, is_active)
- [x] Модель ItemPriceHistory (item_id, price, effective_from, changed_by_id)
- [x] CRUD сервис (ItemService)
- [x] API endpoints
- [x] Seed данные: School Fee, Transport Fee, Admission Fee, Interview Fee
- [x] Тесты

### 1.6 Комплекты (Kits)
> Решения: Kit имеет свою цену, товары в комплекте могут иметь price=null

- [x] Модель Kit (sku_code, name, price, is_active)
- [x] Модель KitItem (kit_id, item_id, quantity)
- [x] Модель KitPriceHistory (kit_id, price, effective_from, changed_by_id)
- [x] CRUD сервис (в ItemService)
- [x] API endpoints
- [x] Тесты

### 1.6.1 Настраиваемые комплекты (Editable Kits)
> Решения: Для комплектов униформы нужна возможность менять конкретные товары (размеры) при продаже, не меняя цену и состав комплекта

- [x] Поле `is_editable_components` в Kit (по умолчанию False)
- [x] Модель InvoiceLineComponent (invoice_line_id, item_id, quantity) для хранения выбранных компонентов
- [x] Модель ItemVariant (name, is_active) — группы взаимозаменяемых товаров
- [x] Модель ItemVariantMembership (variant_id, item_id, is_default) — many-to-many связь (один товар может быть в нескольких вариантах)
- [x] Поля в KitItem: `source_type` ('item' | 'variant'), `variant_id`, `default_item_id` — компонент может быть прямым товаром или вариантом с дефолтным товаром
- [x] Валидация при создании инвойса: заменяемый товар должен принадлежать тому же варианту, что и дефолтный
- [x] При создании инвойса с editable kit: сохранение выбранных компонентов в InvoiceLineComponent
- [x] При создании резервации: использование InvoiceLineComponent вместо дефолтных KitItem
- [x] API endpoints для вариантов: POST/GET/PUT /items/variants, GET /items/variants/{id}/items
- [x] UI: настройка editable kits в CatalogPage (чекбокс, выбор source_type для компонентов)
- [x] UI: выбор компонентов при создании инвойса (CreateInvoicePage) — только для editable kits, можно менять только модель/размер, количество фиксировано
- [x] Миграции: 024_refactor_variants_to_many_to_many, 025_make_kit_items_item_id_nullable
- [x] Тесты: создание editable kits, вариантов, валидация компонентов, резервации с компонентами (302 теста проходят)

### 1.9 Рефакторинг Каталога
> Решения:
> - Разделить понятия: Inventory Items (складские позиции) vs Catalog Items (товары для продажи)
> - Все товары для продажи = Kits (services тоже, но без компонентов)
> - Items (type=product) = только складские позиции, не добавляются в счёт напрямую
> - Items (type=service) — оставить как есть ИЛИ тоже через Kit (обсудить)
> - SKU автогенерация при создании
> - InvoiceLine ссылается только на kit_id (item_id deprecated или удалить)

**Бэкенд:**
- [x] Добавить поле item_type в Kit (product/service)
- [x] Для Kit с item_type=service компоненты не обязательны
- [x] Изменить InvoiceLine: убрать прямую ссылку на item_id, только kit_id
- [x] Миграция данных: существующие Items с продажами → создать Kit-обёртки
- [x] Автогенерация SKU для Kit (категория + номер)
- [x] API: создание Kit с компонентами из Inventory
- [x] Обновить ReservationService для работы только с Kit
- [x] Тесты

**Inventory:**
- [x] Переименовать UI секцию "Inventory" → понятнее что это склад (сделано: "Warehouse")
- [ ] Добавить UI для создания складских позиций (Items type=product)
- [ ] SKU автогенерация для складских позиций

### 1.7 Инвентарь — Часть 1: Остатки и выдача
> Решения: Один склад, средневзвешенная себестоимость, единая сущность Issuance

- [x] Модель Stock (item_id, quantity_on_hand, average_cost)
- [x] Модель StockMovement (item_id, movement_type, quantity, unit_cost, reference_type, reference_id, notes)
- [x] Модель Issuance (issuance_number, issuance_type, recipient_type, recipient_id, recipient_name, reservation_id)
- [x] Модель IssuanceItem (issuance_id, item_id, quantity, unit_cost, reservation_item_id)
- [x] Сервис InventoryService (receive/adjust/issue)
- [x] API endpoints (stock, movements, issuances)
- [x] Миграция (004_inventory.py)
- [x] Тесты

### 1.8 Инвентарь — Часть 2: Резервирование при оплате
> Решения: Резерв при fully paid line, Kit разворачивается в ReservationItem, выдача частями

- [x] Модель Reservation (student_id, invoice_id, invoice_line_id, status)
- [x] Модель ReservationItem (reservation_id, item_id, quantity_required, quantity_issued)
- [x] Сервис ReservationService (create_from_line, issue_items, cancel_reservation)
- [x] Интеграция с PaymentService (trigger при allocation)
- [x] API endpoints (list/get/issue/cancel)
- [x] Тесты

### 1.8.1 Изменения в логике резервирования
> Решения: Резервации создаются сразу после issue инвойса (до оплаты), выдавать можно сразу после issue

- [x] Изменена логика: резервации создаются при issue инвойса (не при полной оплате)
- [x] Резервации можно выдавать сразу после создания (не требуется полная оплата)
- [x] Автоотмена резерваций при отмене инвойса (sync_for_invoice при cancel)
- [x] Поддержка частичной выдачи: можно указать quantity=0 для некоторых items (пропускаются при выдаче)
- [x] Для editable kits: резервация использует InvoiceLineComponent вместо дефолтных KitItem
- [x] Обновлён ReservationService.sync_for_invoice: создание резерваций при issue, отмена при cancel/void
- [x] Обновлён InvoiceService.issue_invoice: вызов sync_for_invoice для создания резерваций
- [x] Обновлён InvoiceService.cancel_invoice: вызов sync_for_invoice для отмены резерваций
- [x] Тесты: резервации при issue до оплаты, автоотмена при cancel, частичная выдача с нулевыми количествами

---

## Фаза 2: Студенты и Счета

### 2.0 Справочник классов (Grades)
- [x] Модель Grade (code, name, display_order, is_active)
- [x] CRUD сервис
- [x] API endpoints
- [x] Seed данные: Play Group, PP1, PP2, Grade 1-6
- [x] Тесты

### 2.1 Студенты (Students)
> Решения: Grades отдельный справочник, один guardian, телефон +254, статус active|inactive

- [x] Модель Student (student_number, first_name, last_name, date_of_birth, gender, grade_id, transport_zone_id, guardian_name, guardian_phone, guardian_email, status, enrollment_date, notes)
- [x] Генерация student_number (STU-YYYY-NNNNNN)
- [x] CRUD сервис (StudentService)
- [x] Валидация телефона (+254...), grade_id
- [x] Смена статуса (active ↔ inactive)
- [x] API endpoints (list с фильтрами, get, create, update, activate, deactivate)
- [x] Тесты

### 2.2 Счета (Invoices)
> Решения: Генерация сразу issued, отдельные счета school_fee + transport, Cancelled/Void

- [x] Модель Invoice (invoice_number, student_id, term_id, invoice_type, status, subtotal, discount_total, total, paid_total, amount_due)
- [x] Модель InvoiceLine (invoice_id, item_id/kit_id, description, quantity, unit_price, line_total, discount_amount, net_amount, paid_amount, remaining_amount)
- [x] Генерация invoice_number (INV-YYYY-NNNNNN)
- [x] Сервис расчёта totals (recalculate_invoice)
- [x] Сервис генерации Term invoices для всех активных студентов
- [x] Добавление строки с Item/Kit к adhoc счёту
- [x] Кастомные скидки на строку (update_line_discount)
- [x] API endpoints (CRUD, issue, cancel, generate-term-invoices)
- [x] Endpoint: generate-term-invoices for single student
- [x] Тесты

### 2.3 Скидки (Discounts)
> Решения: Причины (sibling, staff, etc), процент и фикс, скидка на строку + StudentDiscount

- [x] Модель DiscountReason (справочник причин)
- [x] Модель Discount (invoice_line_id, value_type, value, calculated_amount, reason_id, reason_text)
- [x] Модель StudentDiscount (student_id, applies_to, value_type, value, is_active)
- [x] Сервис DiscountService (apply, remove, create_student_discount)
- [x] Авто-применение StudentDiscount при генерации Term invoices
- [x] API endpoints (reasons CRUD, apply/remove discount, student discounts CRUD)
- [x] Тесты

---

## Фаза 3: Платежи

### 3.1 Платежи (Payments)
> Решения: M-Pesa и Bank Transfer, Payment → Credit Balance → Allocation, статусы pending→completed|cancelled

- [x] Модель Payment (payment_number, receipt_number, student_id, amount, payment_method, payment_date, reference, status, notes)
- [x] Модель CreditAllocation (student_id, invoice_id, invoice_line_id, amount, allocated_by_id)
- [x] Credit Balance = SUM(completed payments) - SUM(allocations) (вычисляемый)
- [x] Сервис PaymentService (create, complete, cancel, get_student_balance)
- [x] API endpoints (CRUD payments, complete, cancel, balance)
- [x] Миграция 008_payments.py
- [x] Тесты

### 3.2 Аллокация средств
> Решения: Товары requires_full_payment, услуги можно частично, smallest first

- [x] Поле `requires_full_payment` в Item (default: True для product, False для service)
- [x] Поле `requires_full_payment` в Kit (default: True)
- [x] Property `Invoice.requires_full_payment`
- [x] Миграция 009_requires_full_payment.py
- [x] Сервис allocate_auto (приоритет: requires_full — можно частично; partial_ok — пропорционально по amount_due; триггеры: payment complete, любой Issued)
- [x] Сервис allocate_manual (ручная аллокация на конкретный invoice)
- [x] Сервис delete_allocation (удаление аллокации с возвратом в баланс)
- [x] API endpoints (POST /allocations/auto, POST /allocations/manual, DELETE /allocations/{id})
- [x] Тесты

### 3.3 Выписка по счёту (Statement)
- [x] Сервис get_statement (student_id, date_from, date_to)
- [x] Схема StatementResponse (entries, total_credits, total_debits, opening_balance, closing_balance)
- [x] API endpoint GET /payments/students/{id}/statement
- [x] Тесты

### 3.4 Отмена платежа
- [x] Сервис cancel_payment (только pending платежи без аллокаций)
- [x] Обязательная причина отмены
- [x] API endpoint POST /payments/{id}/cancel
- [x] Тесты

---

## Фаза 4: Склад (дополнительные функции)

> Базовые функции (Stock, StockMovement, Issuance, receive/adjust/issue/reserve) реализованы в Фазе 1.7

### 4.1 Заявки на выдачу (Issue Requests) — опционально
- [ ] **[ОБСУДИТЬ]** Нужны ли заявки с approval flow или достаточно прямой выдачи?
- [ ] Модель IssueRequest
- [ ] Flow: Draft → PendingApproval → Approved → Issued
- [ ] API endpoints
- [ ] Тесты

### 4.2 Списание с причинами (Write-off)
> Решения: Категории damage/expired/lost/other, без approval

- [x] Endpoint списания (write-off)
- [x] Расширить adjust_stock для указания причины списания
- [x] Тесты

### 4.3 Инвентаризация
> Решения: Ввод actual_quantity → автоматические adjustments

- [x] Сервис bulk_inventory_adjustment (список item_id → actual_quantity)
- [x] Автоматический расчёт delta и создание movements
- [x] Тесты

---

## Фаза 5: Закупки

### 5.1 Заказы (Purchase Orders)
> Решения: Аванс допускается, статус closed при полной поставке/оплате

- [x] Модель PurchaseOrder (po_number, supplier_name, supplier_contact, status, order_date, expected_delivery_date, track_to_warehouse, expected_total, received_value, paid_total, debt_amount)
- [x] Модель PurchaseOrderLine (po_id, item_id, description, quantity_expected, quantity_cancelled, unit_price, line_total, quantity_received)
- [x] CRUD сервис
- [x] Расчёт expected_total
- [x] API endpoints
- [x] Тесты

### 5.2 Приёмка (GRN)
> Решения: Принять больше заказанного нельзя, Admin не апрувит свои GRN

- [x] Модель GoodsReceivedNote (grn_number, po_id, status, received_date, received_by, approved_by)
- [x] Модель GoodsReceivedLine (grn_id, po_line_id, item_id, quantity_received)
- [x] Сервис approve_grn (создание stock movements, обновление PO)
- [x] Запрет approve своего GRN
- [x] API endpoints
- [x] Тесты

### 5.3 Платежи поставщикам
> Решения: Платеж может быть без PO, справочник PaymentPurpose, статусы posted/cancelled

- [x] Справочник PaymentPurpose (name, is_active)
- [x] `PaymentPurpose.purpose_type`: `expense` | `fee` (для выделения транзакционных комиссий)
- [x] Модель ProcurementPayment (payment_number, po_id?, payee_name, purpose_id, payment_date, amount, payment_method, reference_number, company_paid, employee_paid_id, status)
- [x] Сервис создания платежа с пересчётом debt (если есть PO)
- [x] Автосоздание ExpenseClaim если employee_paid (реализовано в Фазе 6)
- [x] API endpoints
- [x] Тесты

---

## Фаза 6: Компенсации сотрудникам

### 6.1 Расходы (Expense Claims)
> Решения: Payment автоматически создаёт ExpenseClaim, approval только SuperAdmin

- [x] Модель ExpenseClaim (claim_number, payment_id, employee_id, purpose_id, amount, description, expense_date, status, paid_amount, remaining_amount, auto_created_from_payment)
- [x] Обязательная валидация proof в Payment (attachment ИЛИ text)
- [x] Автосоздание Claim при payment (employee_paid_id)
- [x] Approve/reject (только SuperAdmin)
- [x] API endpoints
- [x] Тесты

### 6.1.1 Канонизация расходов через ProcurementPayment (ExpenseClaim → Payment)
> Решение: `ProcurementPayment` — единый журнал расходов. Любой `ExpenseClaim` всегда создаёт `ProcurementPayment` (без PO) и становится workflow-обёрткой вокруг него. UX claim-страниц не меняем.

- [x] Backend: при создании ExpenseClaim создавать связанный ProcurementPayment (company_paid=false, employee_paid_id=employee_id)
- [x] Backend: поддержать `fee_amount` в ExpenseClaim (отдельный proof) → создаётся второй linked ProcurementPayment (purpose_type=`fee`) и fee включается в total claim amount
- [x] Backend: для employee-paid платежей `payment_method=employee` (канонизация, не “способ оплаты компании”)
- [x] Backend: убрать рекурсию/дубли (payment.employee_paid_id не должен автосоздавать второй claim, если payment создан из claim)
- [x] Backend: в API ExpenseClaim возвращать поля расхода из ProcurementPayment (amount/date/purpose/payee/proof)
- [x] Backend: при reject claim отменять связанный ProcurementPayment (status=cancelled + reason)
- [x] Backend: если есть edit неаппрувнутого claim — синхронизировать изменения в ProcurementPayment
- [x] Тесты: создание claim создаёт payment; reject claim отменяет payment
- [x] Документация: обновить BACKEND_API.md (ExpenseClaims ↔ ProcurementPayments связь и поведение reject)

### 6.2 Выплаты (Payouts)
> Решения: Можно выплатить больше баланса (аванс), FIFO аллокация, proof обязателен

- [x] Модель CompensationPayout (payout_number, employee_id, payout_date, amount, payment_method, reference_number, proof_text?, proof_attachment_id?)
- [x] Модель PayoutAllocation (payout_id, claim_id, allocated_amount)
- [x] Модель EmployeeBalance (employee_id, total_approved, total_paid, balance)
- [x] Сервис создания payout с FIFO-аллокацией
- [x] Пересчёт EmployeeBalance
- [x] API endpoints
- [x] Тесты

### 6.3 Totals для сотрудника (Pending + Owed)
> Решение: `EmployeeBalance` остаётся «company view» (учитывает только approved/paid). Для удобства сотрудника добавляем totals, которые включают `pending_approval` и показываем на странице claims.

- [x] Backend: `GET /compensations/claims/employees/{employee_id}/totals` (total claimed, pending, approved, paid, owed)
- [x] Frontend: карточка **My Totals** на странице Expense Claims
- [x] Тесты totals endpoint

---

## Фаза 7: Интеграции

### 7.1 Выдача формы (Uniform Fulfillment)
> Решение: Отдельный модуль НЕ нужен. Выдача формы = выдача Reservation по Kit.

- [x] Реализовано через Reservation + Issuance (Фаза 1.7-1.8)

### 7.2 Шина событий (позже)
- [ ] Реализация event bus
- [ ] События: procurement_payment_created и др.
- [ ] Подписчики для автоматических действий
- [ ] Тесты

---

## Фаза 8: Отчёты

### 8.1 Отчёты по дебиторке
- [ ] **[ОБСУДИТЬ]** Какие группировки? Экспорт в Excel? Рассылка?
- [ ] Accounts Receivable Report (задолженности студентов)
- [ ] Collections Report (сборы по периодам/типам)
- [ ] Credit Balances Report (переплаты)
- [ ] API endpoints с фильтрами
- [ ] Экспорт CSV

### 8.2 Отчёты по закупкам
- [ ] Procurement Debts Report (долги поставщикам)
- [ ] API endpoint
- [ ] Экспорт CSV

### 8.3 Отчёты по компенсациям
- [ ] Compensation Balances Report (балансы сотрудников)
- [ ] API endpoint
- [ ] Экспорт CSV

### 8.4 Отчёты по складу
- [ ] Inventory Valuation Report (стоимость остатков)
- [ ] Stock Movements Report (история движений)
- [ ] API endpoints
- [ ] Экспорт CSV

---

## Фаза 9: UI

### 9.0 Рефакторинг фронтенда (архитектура и производительность)
> План исправлений: см. **FRONTEND_REFACTORING_PLAN.md** (отдельный документ). Ниже — краткий список направлений.

- [x] **Производительность (частично):** N+1 на странице студентов устранён (batch). Расчёт чистого баланса (credit − debt) перенесён на бэкенд: StudentBalance с полями outstanding_debt и balance; StudentsPage и StudentDetailPage используют один запрос balances-batch / balance без outstanding-totals.
- [x] ReservationsPage — student_name из API. PayoutsPage — batch-эндпоинт для балансов сотрудников. IssueFormPage — лимиты 500→200 (MAX_DROPDOWN_SIZE).
- [x] **Дублирование запросов (частично):** список счетов студента загружается один раз в StudentDetailPage, передаётся в InvoicesTab и PaymentsTab. Справочники grades и transport-zones — контекст ReferencedDataContext (один запрос на приложение); используют StudentDetailPage, StudentsPage, TermFormPage, TermDetailPage, GradesPage, TransportZonesPage.
- [ ] **Кэш запросов (отложено):** TanStack Query или кэш в useApi — см. FRONTEND_REFACTORING_PLAN.md, раздел «Отложено».
- [x] **Поиск:** debounce для полей поиска (Students, Users, Stock; Items/Movements/Catalog — фильтр клиентский).
- [x] **Типы:** общие ApiResponse/PaginatedResponse в app/types/api.ts. InvoicesTab: форма «Add line» только Kit (контракт API). Хелпер unwrapResponse в services/api.ts для единого разбора ответов.
- [x] **UX (частично):** индикаторы загрузки «Loading…» во всех списковых таблицах; Error Boundary добавлен (оборачивает AppLayout). Пагинация на вкладках студента — отложено (см. план).
- [x] **Мелкое:** удалён ProcurementPaymentsListPage.tsx.bak. Константы лимитов в app/constants/pagination.ts (DEFAULT_PAGE_SIZE, USERS_LIST_LIMIT и др. — использованы в StudentsPage, UsersPage, PayoutsPage, ExpenseClaimsListPage, ProcurementPaymentFormPage, OverviewTab). Хелперы прав в app/utils/permissions.ts. В useApi зафиксировано в JSDoc: стабильные options (useMemo).

### 9.1 Общее
> Решения: React + Vite + TypeScript + Tailwind CSS (кастомные UI-компоненты, без MUI), формат DD/MM/YYYY, валюта KES

- [x] Настройка проекта (React + Vite + TypeScript)
- [x] UI kit (Tailwind CSS + кастомные компоненты)
- [x] Layout с навигацией по ролям
- [x] Страница логина
- [x] Обработка ошибок API
- [x] Кастомный UI-kit на Tailwind (цвета Indigo/Slate, Inter, скругления, тени)
- [x] Фикс наложения label и placeholder: реализовано в кастомных Input/Select (floating label), без MUI темы
- [x] Современный Sidebar (тёмный gradient, логотип)
- [x] TopBar с аватаром и dropdown меню
- [x] Dashboard Quick Actions (скрыты для Accountant): Admit New Student → /students/new (страница формы), Sell Items To Student (/billing/invoices/new), Receive Student Payment (/payments/new), Track Order Items, Receive Order Items, Track Payment, Issue Item From Stock, Issue Reserved Item. Унификация: из карточки студента «Record payment» → /payments/new с state.studentId; CreateInvoicePage блокирует студента при state.studentId или :studentId.
- [x] New Student — отдельная страница /students/new (CreateStudentPage); после создания редирект на карточку студента /students/:id.
- [x] Кнопка «Back»: на **карточках (detail)** — в список (семантический родитель), на **формах** — по истории (navigate(-1)). Пример: StudentDetailPage → Back → /students; формы (CreateStudent, CreateInvoice, ReceivePayment, TermForm, PO, ProcurementPayment, IssueForm) → Back/Cancel = navigate(-1).

### 9.1.1 Mobile MVP (Dashboard + Expense Claims)
> Цель: приложение в целом пока desktop-first, но **с телефона должны работать**: вход → навигация → dashboard (quick actions) → полный flow expense claims (list → new claim → detail).

- [x] Навигация на мобильных:
  - [x] Sidebar: скрывать на small, открывать по hamburger (TopBar) как overlay drawer
  - [x] Контент: убрать фиксированный `margin-left: drawerWidth` на small; уменьшить padding контента на mobile
- [ ] Dashboard (мобильный UX):
  - [x] Quick Actions: кнопки не ломают иконки/текст, корректная сетка и переносы
  - [ ] Summary блоки (Admin/SuperAdmin): читаемость на small (stack вместо 2/4 колонок)
- [ ] Expense Claims (мобильный UX):
  - [x] Claims list: вместо wide table — карточки на small (таблица остаётся на md+)
  - [ ] New claim: форма без горизонтального скролла, file upload доступен с телефона
  - [ ] Claim detail: ключевые поля и rejection reason читаемы на small

**Рефакторинг обработки 401 (token refresh):**
> Проблема: При истечении токена страницы показывали ошибку, даже если interceptor успешно обновлял токен
> Решение: Создали хуки useApi и useApiMutation, которые игнорируют 401 (обработку делает interceptor)

- [x] Создан `frontend/src/app/hooks/useApi.ts` с двумя хуками:
  - `useApi<T>` для GET-запросов (авто-загрузка при монтировании)
  - `useApiMutation<T>` для POST/PUT/DELETE (ручной вызов через execute)
- [x] Рефакторинг страниц для использования хуков (38 из 38 завершено):
  - [x] Compensations: ExpenseClaimDetailPage, ExpenseClaimsListPage, PayoutDetailPage, PayoutsPage
  - [x] Inventory: InventoryCountPage, IssuancesPage, IssueFormPage, ItemsPage, MovementsPage, ReservationsPage, StockPage
  - [x] Procurement: GRNDetailPage, GRNListPage, ProcurementPaymentDetailPage, ProcurementPaymentFormPage, ProcurementPaymentsListPage, PurchaseOrderDetailPage, PurchaseOrderFormPage, PurchaseOrdersListPage
  - [x] Settings: GradesPage, PaymentPurposesPage, UsersPage, **CatalogPage**, **SchoolPage**
  - [x] Students: StudentDetailPage, StudentsPage, ItemsToIssueTab, OverviewTab, StatementTab, StudentHeader, **InvoicesTab**, **PaymentsTab**, **CreateInvoicePage**
  - [x] Terms: FixedFeesPage, TermsListPage, TransportZonesPage, **TermDetailPage**, **TermFormPage**

### 9.2 Справочники UI
> Решения: Settings содержит Users и Grades, Users только SuperAdmin

- [x] Управление пользователями
- [x] Управление классами (Grades)

### 9.3 Студенты и биллинг UI
> Решения: Student profile с вкладками, URL синхронизация, auto-allocate после payment

- [x] Список студентов с фильтрами и поиском
- [x] Карточка студента (вкладки: Overview, Invoices, Payments, Items to Issue, Statement)
- [x] Назначение student discount при создании студента
- [x] Управление student discount в карточке студента
- [x] Просмотр/создание счетов
- [x] Форма приёма платежа (аллокация по complete на бэке, без вызова allocations/auto с фронта)
- [x] Ручная аллокация кредита (модалка в карточке студента)
- [x] Список платежей + детальная страница
- [x] Отмена платежа (только SuperAdmin)
- [x] Statement по студенту
- [x] Применение скидки
- [x] Просмотр квитанции (без PDF)
- [x] Рефакторинг StudentDetailPage на компоненты (StudentHeader, OverviewTab, InvoicesTab, PaymentsTab, ItemsToIssueTab, StatementTab)

### 9.4 Склад UI
> Решения: Категории = разделы склада, low stock ≤ 5, только для products

- [x] Просмотр остатков
- [x] Быстрая выдача
- [x] Списание (из списка)
- [x] Форма инвентаризации
- [x] Просмотр движений склада
- [x] Issuances: список/деталь/отмена
- [x] Reservations: список/выдача/отмена (показывает имя студента, фильтр Active)

**Выдача (Issue): трекинг «кому» (инициатор уже есть — issued_by):**
- [x] **Backend:** Расширить тип получателя: ученик / сотрудник / другое.
  - В `RecipientType` добавлен `OTHER`; для «другое» хранится только `recipient_name`, `recipient_id` nullable в Issuance.
  - В `create_internal_issuance` разрешён `recipient_type=student`; для `other` не требуется `recipient_id`, требуется `recipient_name`; для employee/student имя подставляется с бэка по id.
  - Миграция 017: `issuances.recipient_id` → nullable.
- [x] **Frontend (StockPage, диалог Issue):** В форме выдачи добавлен блок «Кому»: тип Student/Employee/Other, при Student — select студентов, при Employee — select пользователей, при Other — текстовое поле. Выдача идёт через `POST /inventory/issuances` с одним item.
- [x] В списке issuances отображается «Кому» (recipient_name уже в IssuanceResponse).

**Issue stock — форма выдачи комплектом (ветка `feature/bulk-issue-stock`, план в `docs/ISSUE_FORM.md`):**
- [x] **Frontend (Stock):** Кнопка «Issue» сверху страницы (не у каждого айтема). Убраны кнопка Issue в строке таблицы и диалог Issue.
- [x] **Frontend (IssueFormPage):** Новая страница `/inventory/issue` — форма получателя (Student/Employee/Other) + таблица строк (Item, Quantity), Add line, Submit → POST /inventory/issuances (несколько items в одном issuance), redirect на /inventory/issuances.
- [x] **Backend:** Используется существующий POST /inventory/issuances (уже поддерживает items[]).

**Массовая загрузка стока (CSV) — ветка `feature/bulk-stock-csv`, план в `docs/BULK_STOCK_CSV.md`:**
- [x] **Backend:** POST `/inventory/bulk-upload` (file CSV + mode: overwrite | update).
  - Парсинг CSV: category, item_name, quantity, unit_cost? (и опционально sku). Reserved в CSV не участвует.
  - Get-or-create категории по имени; get-or-create Item (product) по (category, item_name) или sku, автоСКУ при создании.
  - Режим overwrite: обнулить **только quantity_on_hand** по всем product (но запрещать overwrite при outstanding reservations).
  - Режим update: только для позиций из CSV установить quantity_on_hand (adjustment до target quantity).
  - Аудит и движения StockMovement.
- [x] **Backend:** GET `/inventory/bulk-upload/export` — выгрузка **текущего склада** в CSV (не пустой шаблон), чтобы редактировать и заливать обратно.
- [x] **Frontend (страница Inventory count):** секция «Bulk upload from CSV»: кнопка «Download current stock», выбор файла, режим (Overwrite warehouse / Update only), Upload; результат (обработано строк, создано позиций, ошибки).
- [ ] **CDN / хранилище:** прод = Cloudflare S3; дев = MinIO в docker-compose. Для bulk CSV CDN не нужен.

**После рефакторинга 1.9:**
- [x] Управление складскими позициями (Items type=product)
- [x] Создание новой позиции: Name, Category, SKU (авто)
- [x] Редактирование позиции
- [x] Деактивация позиции

### 9.5 Каталог UI
> Решения:
> - Каталог = товары для продажи (отдельно от складских позиций)
> - Все товары для продажи = Kits (даже если один компонент)
> - При создании товара выбираем компоненты из Inventory (для Products)
> - Service = товар без компонентов (не связан со складом)
> - SKU автогенерируется (категория + номер), не показываем в UI
> - История цен только для аудита в БД, не в UI
> - requires_full_payment автоматически для products, убираем из UI

**Требуется рефакторинг бэкенда (см. 1.9)**

- [x] Страница `/billing/catalog` с вкладками (перенесено из Settings для консистентности - все за что берём деньги в одном месте)
- [x] Вкладка "Items": таблица товаров (Name, Category, Price, Type, Active)
- [x] Фильтры: поиск по названию, категория, тип (product/service)
- [x] Создание товара: Name, Category (dropdown с +Add), Price, Type (product/service)
- [x] Для products: выбор компонентов из Inventory (item + qty)
- [x] Для services: без компонентов
- [x] Редактирование товара
- [x] Деактивация товара

**Настраиваемые комплекты (Editable Kits):**
- [x] Вкладка "Variants": управление вариантами товаров (группы взаимозаменяемых товаров, например размеры)
- [x] Создание/редактирование варианта: название, выбор товаров из Inventory (many-to-many)
- [x] При создании/редактировании Kit: чекбокс "Editable components" для комплектов униформы
- [x] Для компонентов Kit: выбор source_type (Inventory Item или Variant)
- [x] Если выбран Variant: выбор варианта и дефолтного товара из варианта
- [x] При создании инвойса (CreateInvoicePage): для editable kits показывается секция "Components" с возможностью выбора конкретных товаров (только модель/размер, количество фиксировано)

### 9.6 Terms & Pricing UI
> Решения:
> - Раздел меню "Billing" содержит Terms и Fixed Fees
> - Transport Zones остаётся в Settings
> - Создание/редактирование терма — одна страница со всеми ценами
> - Цены копируются из предыдущего терма при создании
> - Генерация счетов — отдельная кнопка, результат в модалке

**Структура меню:**
- Billing → Terms, Fixed Fees, Catalog (все за что берём деньги в одном месте)
- Settings → Users, Grades, Transport Zones

**Terms `/billing/terms`:**
- [x] Список термов (Name, Status, Dates, Actions)
- [x] Кнопка "+ New Term"

**Создание/редактирование терма `/billing/terms/new`, `/billing/terms/:id/edit`:**
- [x] Одна страница: Year, Term Number, Start/End Date
- [x] Таблица School Fees by Grade (inline редактирование)
- [x] Таблица Transport Fees by Zone (inline редактирование)
- [x] При создании — цены копируются из предыдущего терма

**Детальная страница терма `/billing/terms/:id`:**
- [x] Статус (Draft/Active/Closed) с бейджем
- [x] Кнопки: Activate, Close
- [x] Dropdown "Generate Invoices" → All students / Single student
- [x] Модалка результата генерации (school fee invoices, transport invoices, skipped, total)
- [x] Таблицы цен (read-only, кнопка Edit → переход на edit страницу)

**Fixed Fees `/billing/fixed-fees`:** *(now using Kits from "Fixed Fees" category)*
- [x] Список (Name, Amount, Active)
- [x] Редактирование в модалке
- [x] Добавление нового fee

**Settings:**
- [x] Transport Zones (справочник)

### 9.7 Закупки UI
> Решения:
> - Раздел меню "Procurement" содержит Purchase Orders, Goods Received, Payments
> - Payment Purposes — в Settings
> - track_to_warehouse вычисляется автоматически на фронте:
>   - Если есть строки с item_id → true
>   - Если все строки без item_id (только description) → false
> - При создании PO можно добавлять новые товары на лету (создаёт Inventory Item)
> - Создание GRN — из детальной страницы PO
> - Dashboard с pending GRN и долгами поставщикам

**Структура меню:**
- Procurement → Purchase Orders, Goods Received, Payments
- Settings → Payment Purposes

**Purchase Orders `/procurement/orders`:**
- [x] Список с фильтрами (status, supplier, date)
- [x] Dashboard/сводка: pending GRN, долги поставщикам (в детальной странице PO)

**Создание/редактирование PO `/procurement/orders/new`, `/:id/edit`:**
- [x] Supplier name, contact, purpose, dates
- [x] Таблица строк с возможностью:
  - [x] Добавить из Inventory (выбор существующего товара)
  - [x] "+ New item" (создаёт складскую позицию на лету)
  - [x] "Add custom line" (только description, для мебели и т.д.)
- [x] track_to_warehouse вычисляется автоматически

**Детальная страница PO `/procurement/orders/:id`:**
- [x] Информация о заказе, статус
- [x] Таблица строк (expected/received/remaining)
- [x] Actions: Submit, Close, Cancel
- [x] Кнопка "Receive" → создание GRN
- [x] История GRN и платежей

**Goods Received `/procurement/grn`:**
- [x] Список GRN с фильтрами (status, PO, date)
- [x] Детальная страница GRN
- [x] Actions: Approve (если не свой), Cancel

**Payments `/procurement/payments`:**
- [x] Список платежей с фильтрами
- [x] Создание платежа (с PO или без)
- [x] Детальная страница
- [x] Cancel платежа

**Settings:**
- [x] Payment Purposes (справочник)

### 9.8 Компенсации UI
> Решения:
> - Раздел меню "Compensations" содержит Expense Claims и Payouts
> - Expense Claims — один список, фильтруется по роли:
>   - Сотрудник видит только свои + свой баланс вверху
>   - SuperAdmin видит все + фильтр по сотруднику
> - Балансы всех сотрудников — на странице Payouts (таблица сверху)
> - Кнопка [Pay] у сотрудника → модалка создания payout

**Структура меню:**
- Compensations → Expense Claims, Payouts

**Expense Claims `/compensations/claims`:**
- [x] Список claims с фильтрами (status, employee, date)
- [x] Для сотрудника: только свои claims, баланс вверху (если доступен endpoint)
- [x] Для SuperAdmin: все claims, фильтр по сотруднику
- [x] Детальная страница claim
- [x] Actions: Approve, Reject (только SuperAdmin)

**Out-of-pocket (быстрые покупки сотрудника) → Expense Claim:**
> Цель: отдельный простой флоу для мелких покупок (fuel, groceries, small repairs), без PO/GRN.
> Сущность: `ExpenseClaim` создаётся напрямую сотрудником (или админом), затем утверждается и оплачивается `CompensationPayout`.
- [x] Backend: `ExpenseClaim` создаётся напрямую, но под капотом всегда создаётся `ProcurementPayment` без PO (канонический журнал расходов)
- [x] Backend: proof/payee живут в `ProcurementPayment` (claim-level `payee_name/proof_*` больше не нужны)
- [x] Backend: добавить API для создания claim (User создаёт для себя; Admin/SuperAdmin — для любого сотрудника)
- [x] Backend: разрешить User читать `GET /procurement/payment-purposes` (для выбора категории расходов)
- [x] Frontend: страница создания claim `/compensations/claims/new` + кнопка "New claim" в списке
- [x] Tests: покрыть создание claim (User), видимость "только своё", валидацию proof

**Payouts `/compensations/payouts`:**
- [x] Таблица Employee Balances (Name, Approved, Paid, Balance, [Pay])
- [x] Кнопка [Pay] → модалка создания payout
- [x] Список recent payouts
- [x] Детальная страница payout (allocations)

### 9.9 Отчёты UI
- [ ] Отчёты в UI после появления эндпоинтов в API

### 9.10 Аудит UI
- [ ] **[ОБСУДИТЬ]** Уточнить требования к интерфейсу
- [ ] Просмотр аудит-лога с фильтрами

### 9.11 Интерфейс для бухгалтера (Accountant)
> ТЗ: **ACCOUNTANT_REPORTS.md**. Роль Accountant — read-only: первичные документы, экспорт данных, audit trail. Без создания/редактирования.

**Прогресс 9.11 (как отслеживать):**
- Ищи в этом блоке строки с `[ ]` — это оставшиеся задачи.
- Backend: экспорт student-payments и procurement-payments готовы; по желанию: transactions, vat, wht.
- Frontend: меню, страницы Receipts/Export/Audit, скрытие кнопок создания — готово; Settings для Accountant не показываем (минимальное меню без Settings).

**Навигация для роли Accountant (минимальная):**
- Documents: Incoming Payments, Students Invoices, Purchase Orders, GRN, Procurement Payments, Employee Expenses Claims, Employee Payouts
- Data Export: Student Payments, Procurement Payments, Student Balance Changes (CSV); отдельные периоды по каждому экспорту, предзаполнение дат (текущий месяц)
- Audit Trail
- Settings → My Profile (только профиль)

**Backend (API для бухгалтера):**
- [x] Роутер `/api/v1/accountant/` с проверкой роли Accountant (Admin/SuperAdmin тоже допущены)
- [x] Документы: все GET для просмотра допускают Accountant (students list/get, grades, transport-zones, payments list/get/receipt/pdf, invoices list/get/pdf, procurement: purchase-orders list/get, grns list/get, payments list/get, payment-purposes, dashboard; compensations: claims list/get, payouts list/get, employee-balances). Запись (POST/PUT/PATCH/DELETE) для Accountant запрещена: create/update/complete payment, allocate, cancel payment, create/update PO/GRN/payout и т.д.
- [x] GET export/student-payments (CSV; ссылки на фронт: Receipt PDF → /payment/{id}/receipt, Attachment → /attachment/{id}/download; FRONTEND_URL в .env)
- [x] GET export/procurement-payments (CSV; ссылка на фронт: Attachment → /attachment/{id}/download)
- [x] GET export/student-balance-changes (CSV: платежи и аллокации по периоду)
- [x] GET audit-trail с фильтрами (date_from, date_to, user_id, entity_type, action, page, limit)
- [x] Тесты API (tests/modules/accountant/test_accountant.py — audit-trail и оба export, роль User — 403)
- [ ] GET export: transactions, vat, wht

**Frontend (интерфейс для бухгалтера):**
- [x] Для роли Accountant: отдельное меню (accountantNavItems: Dashboard, Documents, Data Export, Audit Trail)
- [x] Documents: Incoming Payments (/payments), Students Invoices (/billing/invoices), PO, GRN, Procurement Payments, Employee Expenses Claims — ссылки на существующие страницы
- [x] Страница Data Export (/accountant/export): Student Payments, Procurement Payments, Student Balance Changes CSV; у каждого экспорта свой период дат; предзаполнение текущим месяцем; ссылки в CSV ведут на фронт (FRONTEND_URL) — /attachment/:id/download и /payment/:id/receipt (JWT при открытии в приложении)
- [x] Страницы скачивания по ссылке из CSV: /attachment/:id/download, /payment/:id/receipt (проверка JWT, редирект на логин при необходимости)
- [x] Проактивное обновление JWT (api.ts): за 2 мин до истечения access token — refresh в request interceptor; общая refreshAccessToken() для 401 и проактивного обновления
- [x] Список счетов (Invoices): по умолчанию «все кроме отменённых»; заголовок «Students Invoices»
- [x] Страница Audit Trail (/audit): таблица с фильтрами (дата, entity_type, action), пагинация
- [x] Скрыть кнопки создания для Accountant (PaymentReceiptsPage, ProcurementPaymentsListPage); isAccountant в permissions
- [x] Settings для Accountant: в минимальном меню Settings не показываем (решение принято)

**Осталось по 9.11:**
- [ ] GET export/transactions (общий экспорт транзакций)
- [ ] GET export/vat, GET export/wht (для налоговых отчётов)

### 9.12 Dashboard и отчёты для руководства (SuperAdmin/Admin)
> ТЗ: **MANAGER_REPORTS.md**. Роли Manager нет; доступ к сводкам и отчётам — SuperAdmin, Admin. **Quick Actions над дашбордом** — видимы для **User** тоже (остальное только Admin/SuperAdmin).

**Доступ:**
- Quick Actions на главной: User, Admin, SuperAdmin (не скрывать для User).
- Карточки, графики, алерты, лента активности на Dashboard + весь раздел Reports: только Admin, SuperAdmin.

**Backend:**
- [x] GET /api/v1/dashboard — сводка для главной (карточки, ключевые метрики). Доступ: Admin, SuperAdmin. Модуль dashboard: router, service, schemas; тесты (Admin/SuperAdmin 200, User/Accountant 403).
- [x] Роутер /api/v1/reports/ с проверкой роли Admin/SuperAdmin.
- [x] Отчёт Students: aged-receivables (as_at_date, строки по студентам, bucket'ы current/31-60/61-90/90+, summary). Тесты: Admin/SuperAdmin 200, User/Accountant 403.
- [x] Отчёт Students: student-fees (term_id, grade_id опционально; по классам: students_count, total_invoiced, total_paid, balance, rate). Тесты: 200/404/403.
- [x] Отчёты Financial: profit-loss, cash-flow, balance-sheet (параметры; экспорт в Excel реализован).
- [x] Отчёты Students: collection-rate, discount-analysis, top-debtors.
- [x] Отчёты Procurement & Inventory: procurement-summary, inventory-valuation, low-stock-alert, stock-movement.
- [x] Отчёты Compensations: compensation-summary, expense-claims-by-category.
- [ ] Analytics: revenue-trend, payment-method-distribution, term-comparison, kpis.
- [ ] Тесты API (dashboard, reports; User/Accountant — 403 на dashboard сводке и reports).

**Frontend:**
- [x] Quick Actions: оставить видимыми для User (не скрывать); добавлена кнопка «View Outstanding Debts» → /reports/aged-receivables.
- [x] Dashboard для Admin/SuperAdmin: под Quick Actions — запрос GET /dashboard, карточки (Revenue This Year, This Term Revenue, Collection Rate, Expenses, Student Debts, Supplier Debt, Credit Balances, Pending Claims, Pending GRN). Для User под Quick Actions — текст «Summary and reports are available to Admin and SuperAdmin».
- [x] Меню Reports (один пункт с подменю): Aged Receivables, Student Fees by Term. Показывать только Admin, SuperAdmin (roles: adminRoles).
- [x] Страница отчёта Aged Receivables (/reports/aged-receivables): таблица по студентам (Total, Current 0-30, 31-60, 61-90, 90+, Last Payment), summary; при 403 — сообщение о доступе.
- [x] Страница отчёта Student Fees by Term (/reports/student-fees): выбор терма и опционально класса, таблица по классам (Class, Students, Total Invoiced, Total Paid, Balance, Rate), summary; при 403 — сообщение о доступе.
- [x] Страницы финансовых отчётов: Profit & Loss (/reports/profit-loss), Cash Flow (/reports/cash-flow), Balance Sheet (/reports/balance-sheet) — параметры (даты), таблицы, 403; тесты API (profit-loss, cash-flow, balance-sheet).
- [x] Отчёты с выбором дат: шорткаты (This year, This month, 30 days, 365 days), по умолчанию This year.
- [x] Меню Reports: группировка в 5 разделов (Financial, Students, Procurement & Inventory, Compensations, Analytics) с вкладками внутри раздела.
- [x] Финансовые отчёты помесячно: PnL, Cash Flow, Balance Sheet — при диапазоне > 1 месяца колонки по месяцам (backend breakdown=monthly, frontend таблицы с месяцами).
- [x] Отчёты Students: Collection Rate Trend (/reports/collection-rate), Discount Analysis (/reports/discount-analysis), Top Debtors (/reports/top-debtors) — backend + тесты + страницы и навигация.
- [x] Страницы отчётов Procurement & Inventory: Procurement Summary, Inventory Valuation, Low Stock Alert, Stock Movement Report (меню, роуты, страницы).
- [x] Страницы отчётов Compensations: Compensation Summary, Expense Claims by Category (меню, роуты, страницы).
- [x] Страницы отчётов Analytics: Revenue per Student Trend, Payment Method Distribution, Term Comparison, KPIs & Metrics (меню, роуты, страницы).
- [x] Скрипт наполнения БД демо-данными: `scripts/seed_demo_data.py` (реалистичные школьные данные: пользователи, классы, термы, ученики, счета, платежи, закупки, компенсации, склад).
- [x] Экспорт в Excel для всех отчётов (параметр `format=xlsx`, кнопка «Export to Excel» на каждой странице отчёта; PDF не требуется).

**Порядок реализации (рекомендуемый):** сначала backend dashboard + один отчёт (например aged-receivables или student-fees), тесты; затем фронт дашборда и один отчёт; потом остальные отчёты.

---

## Фаза 10: Вложения и PDF

### 10.1 Загрузка файлов
- [x] **[ОБСУДИТЬ]** Где хранить файлы (локально/S3)? Лимиты размера? Типы файлов?
- [x] Модель Attachment (для подтверждений платежей: image/PDF, до 10 MB)
- [x] Сервис upload/download (локально `STORAGE_PATH`; прод — см. CLOUDFLARE_R2.md)
- [x] API endpoints: POST/GET /attachments, GET /attachments/{id}/download
- [x] Тесты (tests/core/test_attachments.py)
- [x] Подтверждения к платежам: студенческие платежи (reference или confirmation_attachment_id), procurement (proof_text или proof_attachment_id), payouts — то же. Просмотр: «View confirmation file».

### 10.2 Генерация PDF
> Решения: Реквизиты школы, логотип и штамп — в одном месте: Settings → School (таблица school_settings). В UI: галочки «Use M-Pesa» / «Use bank transfer» — показывать в PDF счёта только выбранные способы оплаты. В разделе M-Pesa поле номера называем Paybill (не Business number).

- [x] Настройки школы в UI (реквизиты, логотип, штамп) — одна страница Settings → School, хранение в school_settings
- [x] Тесты school-settings (API GET/PUT, сервис get/update, роли Admin/SuperAdmin vs User/Accountant)
- [x] **[ОБСУДИТЬ]** Шаблоны документов (остальное по DOCUMENT_GENERATION.md)
- [x] PDF счёта (WeasyPrint + Jinja2, GET /invoices/{id}/pdf, данные из school_settings)
- [x] PDF квитанции (GET /payments/{id}/receipt/pdf, только completed)
- [x] Тесты генерации (tests/core/test_pdf.py — эндпоинты с моком WeasyPrint)

---

## Фаза 11: CRM / Маркетинг (Leads)

### 11.1 Семьи и лиды (Families)
- [ ] **[ОБСУДИТЬ]** Воронка лидов, источники, интеграции
- [ ] Модель Family (guardian_name, phone, email, source, status, notes)
- [ ] Модель FamilyChild (family_id, child_name, date_of_birth, gender, intended_grade)
- [ ] Статусы: inquiry → interview_scheduled → interview_done → admission_paid → enrolled
- [ ] CRUD сервис
- [ ] Конвертация FamilyChild → Student при зачислении
- [ ] API endpoints
- [ ] Тесты

### 11.2 Источники лидов
- [ ] Справочник LeadSource (name, is_active)
- [ ] Отчёт по эффективности источников
- [ ] API endpoints

### 11.3 Маркетинговые отчёты
- [ ] Воронка конверсии
- [ ] Лиды по источникам
- [ ] Экспорт CSV

---

## Фаза 12: Bank reconciliation (выписки банка)

> Решения: Выписку храним как файл (Attachment в storage/S3) + парсим транзакции в БД «как в CSV»; транзакции могут пересекаться между выгрузками → дедуп по fingerprint + связь import↔transaction. Date range для reconciliation считается по min/max `Value Date` из транзакций (не доверяем Range From/To в header CSV).

- [x] Модели и миграции: imports, transactions, matches
- [x] API импорта Stanbic CSV (upload + parse + сохранение)
- [x] Auto-match: транзакции ↔ ProcurementPayment(company_paid) / CompensationPayout (amount/date + reference)
- [x] Reconciliation view: unmatched transactions + unmatched payments/payouts
- [x] UI: Admin/SuperAdmin — Bank reconciliation (import + auto-match + manual match); Accountant — Bank transfers (общая таблица + фильтры)
- [x] Тесты парсинга и матчинг‑эвристик
- [x] Документация: BACKEND_API.md (+ accountant exports bank transfers + statement files)

## Примечания

- Задачи с `[ОБСУДИТЬ]` требуют уточнения требований перед началом работы
- Блоки `> Решения:` содержат принятые решения для справки
- Тесты: 308 passed (все бэкенд-тесты проходят, включая тесты для editable kits, вариантов и резерваций)
