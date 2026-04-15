# План фичи: Billing Accounts / общий платежный аккаунт

## 1. Цель

Нужен механизм, который позволит:
- объединять одного или нескольких учеников в один billing account;
- принимать оплату на один общий billing account;
- автоматически распределять деньги по invoice всех детей в account;
- при этом не терять прозрачность: invoice все еще должен быть привязан к конкретному ученику.

Типовой сценарий:
- в семье 2-3 ребенка;
- родитель платит одной суммой;
- школа хочет видеть один общий баланс семьи;
- деньги должны закрывать долги всех детей семьи по понятным правилам.

---

## 2. Почему это нельзя делать поверх текущей модели без отдельной сущности

Сейчас финансовая модель жестко student-centric:
- `Student.cached_credit_balance` хранится на ученике;
- `Payment.student_id` указывает на одного ученика;
- `CreditAllocation.student_id` тоже указывает на одного ученика;
- `allocate_auto` и statement работают в рамках одного `student_id`;
- `Invoice` принадлежит конкретному ученику.

Из этого следуют ограничения:
- нельзя иметь один общий кошелек на несколько детей;
- нельзя корректно показать общий family balance;
- нельзя безопасно принимать payment "на семью", а не на конкретного ребенка;
- нельзя строить общий statement семьи без новой финансовой сущности.

Вывод: для shared billing нужна отдельная сущность-владелец денег.

---

## 3. Рекомендуемая бизнес-модель

### 3.1. Naming

Для архитектуры и текущего UI используем сущность `BillingAccount`.

Рекомендация:
- в базе и backend: `BillingAccount`;
- в интерфейсе: `Billing Accounts`;
- создание: единый flow `New admission` на `/students/new`;
- contact block: `Billing contact`.

Причина:
- сегодня это семья;
- завтра может появиться нестандартный плательщик: опекун, sponsor, employer, church fund и т.п.;
- `BillingAccount` более универсален.

### 3.2. Ключевой принцип

Деньги принадлежат `BillingAccount`, а не студенту.

При этом:
- `Invoice` остается на конкретного ученика;
- у каждого `Invoice` есть snapshot поля `billing_account_id`;
- `Payment` зачисляется на `BillingAccount`;
- `CreditAllocation` списывает баланс `BillingAccount` на конкретный `Invoice`.

Именно это дает:
- общий баланс account;
- общий statement account;
- сохранение student-level детализации по долгам и invoice.

---

## 4. Рекомендуемая модель данных

## 4.1. BillingAccount

Новая таблица `billing_accounts`.

Пример полей:

| Поле | Тип | Назначение |
|------|-----|------------|
| id | BIGINT PK | внутренний id |
| account_number | VARCHAR(50) UNIQUE | внешний человекочитаемый номер, например `FAM-000123` |
| display_name | VARCHAR(255) | например `Family of John and Mary Doe` |
| account_type | VARCHAR(20) | `family` / `sponsor` / `other` |
| primary_contact_name | VARCHAR(200) NULL | основной плательщик |
| primary_contact_phone | VARCHAR(20) NULL | |
| primary_contact_email | VARCHAR(255) NULL | |
| status | VARCHAR(20) | `active`, `inactive`, `archived` |
| cached_credit_balance | DECIMAL(15,2) | общий credit balance аккаунта |
| notes | TEXT NULL | |
| created_by_id | BIGINT | |
| created_at / updated_at | timestamptz | |

Важно:
- не использовать raw `id` как внешний payment reference;
- использовать именно `account_number`.

## 4.2. BillingAccountMember

Связь аккаунта и учеников.

| Поле | Тип | Назначение |
|------|-----|------------|
| id | BIGINT PK | |
| billing_account_id | BIGINT FK | |
| student_id | BIGINT FK | |
| role | VARCHAR(20) | `primary_student`, `member` |
| joined_at | DATE NULL | дата включения в семью |
| left_at | DATE NULL | дата исключения |
| is_active | BOOLEAN | активное членство |
| notes | TEXT NULL | |

Ограничения:
- один ученик может состоять только в одном активном billing account одновременно;
- исторические membership rows можно сохранять через `left_at` + `is_active = false`.

## 4.3. Student

В `students` нужно добавить:

| Поле | Тип |
|------|-----|
| billing_account_id | BIGINT FK NOT NULL |

Почему поле нужно и в `students`, и отдельная membership table:
- `students.billing_account_id` удобно для быстрых join и runtime-логики;
- membership table нужна для истории, audit и безопасных переводов между семьями.

## 4.4. Invoice

В `invoices` добавить:

| Поле | Тип |
|------|-----|
| billing_account_id | BIGINT FK NOT NULL |

Это snapshot поля на момент создания invoice.

Почему это критично:
- если ребенка позже переведут в другой billing account, старый invoice не должен автоматически "переехать";
- иначе сломается история долга и statement.

## 4.5. Payment

В `payments` изменить владельца денег:

| Поле | Тип |
|------|-----|
| billing_account_id | BIGINT FK NOT NULL |
| student_id | BIGINT NULL или deprecated path |
| preferred_invoice_id | BIGINT NULL |

Рекомендация:
- на переходный период можно временно оставить `student_id`, чтобы не ломать старые интеграции;
- новой канонической связью сделать `billing_account_id`;
- позже `student_id` в payment оставить как optional "student context", а не owner.

## 4.6. CreditAllocation

В `credit_allocations` тоже нужен владелец:

| Поле | Тип |
|------|-----|
| billing_account_id | BIGINT FK NOT NULL |
| invoice_id | BIGINT FK NOT NULL |
| invoice_line_id | BIGINT FK NULL |
| amount | DECIMAL(15,2) |

Здесь уже недостаточно `student_id`, потому что кредит принадлежит семье.

## 4.7. Optional: BillingAccountReferenceAlias

Если нужна поддержка оплаты по разным идентификаторам:
- `billing_account_number`;
- `student_number`;
- legacy admission refs;

можно добавить alias table:

| Поле | Тип |
|------|-----|
| id | BIGINT PK |
| billing_account_id | BIGINT FK |
| alias_type | VARCHAR(20) |
| alias_value | VARCHAR(100) UNIQUE |
| is_active | BOOLEAN |

Но для MVP это не обязательно.

---

## 5. Основные бизнес-правила

### 5.1. Один общий кошелек на семью

Если несколько детей состоят в одном `BillingAccount`, то:
- все completed payments попадают в общий balance аккаунта;
- auto-allocation видит invoice всех active students этого account;
- остаток денег остается как общий account credit.

### 5.2. Invoice остается student-owned

Даже после внедрения billing accounts:
- invoice создается на конкретного ученика;
- в отчетах видно, какой именно ребенок должен;
- billing account view агрегирует invoice всех членов account.

### 5.3. Оплата должна приниматься по account number, а не по raw DB id

Правильная внешняя модель:
- плательщик платит по `account_number`, например `FAM-000123`;
- система резолвит его в `billing_account_id`.

Для переходного периода стоит поддержать и student number:
- если пришел `student_number`, система находит студента и его `billing_account_id`;
- если студент состоит в семье, платеж идет на family account;
- если у студента нет общей семьи, это его персональный account.

### 5.4. Один активный billing account на студента

Иначе будет неочевидно:
- куда зачислять payment;
- какой account должен получать новый invoice;
- какой account видеть в statement и balance.

### 5.5. Перевод ученика между семьями

Это отдельный controlled flow.

Нужно явно определить:
- остаются ли старые invoice на старом account;
- переводятся ли будущие invoice на новый;
- нужно ли переносить неиспользованный family credit.

Рекомендация:
- старые invoice и старые allocations остаются на старом account;
- будущие invoice создаются на новом account;
- перенос кредита делать отдельным explicit действием.

### 5.6. Preferred invoice

Текущий `preferred_invoice_id` нужно сохранить и в family mode.

Логика:
- payment сначала идет в выбранный invoice;
- остаток идет в общий auto-allocation по family account.

Это особенно важно для activities, trip fees и других целевых сборов.

---

## 6. Auto-allocation в family mode

## 6.1. Базовый принцип

Не придумывать новый allocation engine.

Нужно расширить текущий `allocate_auto`, чтобы он работал по `billing_account_id` вместо `student_id`.

## 6.2. Какие invoice участвуют

В auto-allocation должны попадать:
- все `issued`;
- все `partially_paid`;
- все invoice с `amount_due > 0`;
- только те, у которых `billing_account_id = X`.

## 6.3. Какой порядок

Для MVP лучше сохранить текущую семантику:
- invoices с `requires_full_payment` в приоритете;
- потом остальные;
- внутри групп использовать текущие правила.

Но важно добавить deterministic ordering внутри family:
- сначала по due date;
- потом по issue date;
- потом по invoice id.

Иначе пользователю будет сложно предсказывать, почему платеж закрыл именно эти долги.

Рекомендация:
- текущий алгоритм распределения сохранить;
- сортировку сделать более business-friendly, а не только по `amount_due`.

## 6.4. Family-level manual allocation

Нужен ручной flow:
- выбрать payment account;
- выбрать invoice любого ребенка в семье;
- аллоцировать сумму.

---

## 7. Statement и balances

## 7.1. Family Statement

Нужен новый statement на уровне billing account.

Он должен показывать:
- opening balance account;
- payments;
- allocations;
- closing balance;
- к какому invoice и какому студенту относится каждая allocation.

Пример строки:
- `Payment to INV-2026-001234 (Student: Alice Doe)`

## 7.2. Student Statement

Есть два варианта:

### Вариант A: оставить как есть

Student statement показывает только:
- invoice этого ребенка;
- allocations на его invoice;
- возможно без прямой привязки к family payments.

Плюс:
- проще.

Минус:
- родителю будет неочевидно, откуда деньги.

### Вариант B: student statement с family context

Показывать:
- allocations на invoice этого ребенка;
- но в payment source указывать, что деньги пришли из family account.

Рекомендация:
- MVP: оставить student statement как child-specific;
- основной ledger сделать family statement.

## 7.3. Balance API

Нужны:
- `GET /billing-accounts/{id}/balance`
- `GET /billing-accounts/{id}/statement`

А существующий student balance API должен:
- по желанию возвращать family context;
- либо показывать student net debt + family credit отдельно.

Иначе возникнет путаница:
- у студента может быть debt;
- у семьи может быть положительный общий balance.

---

## 8. Миграция существующих данных

Это самая важная часть.

## 8.1. Безопасная стратегия MVP

На первом шаге создать персональный billing account для каждого существующего студента:
- 1 student = 1 billing account;
- backfill `students.billing_account_id`;
- backfill `invoices.billing_account_id`;
- backfill `payments.billing_account_id`;
- backfill `credit_allocations.billing_account_id`.

Это даст:
- нулевое изменение поведения после миграции;
- возможность позже вручную объединять студентов в семьи.

## 8.2. Почему не стоит сразу auto-merge по guardian phone

Потому что:
- телефоны могут совпадать случайно;
- один guardian может вести не всех детей;
- данные могут быть грязными;
- merge финансовых аккаунтов — высокорисковая операция.

Правильный путь:
- после backfill все аккаунты индивидуальные;
- админ вручную объединяет нужных студентов.

## 8.3. Merge flow

Нужен controlled service:
- выбрать целевой billing account;
- выбрать студентов, которых туда переносим;
- решить судьбу существующего credit balance и unpaid invoices.

Для MVP рекомендую:
- unpaid invoices выбранных студентов переводить на новый account только если они еще не имеют allocations;
- если уже есть allocations/история, не переносить автоматически;
- старые долги оставлять как есть и предупреждать пользователя.

Более безопасный вариант:
- merge разрешать только для будущих invoice;
- исторические invoice не перепривязывать.

---

## 9. API

## 9.1. Billing Account CRUD

- `POST /billing-accounts`
- `GET /billing-accounts`
- `GET /billing-accounts/{account_id}`
- `PATCH /billing-accounts/{account_id}`

## 9.2. Membership management

- `POST /billing-accounts/{account_id}/members`
- `DELETE /billing-accounts/{account_id}/members/{student_id}`
- `POST /billing-accounts/{account_id}/transfer-student`

## 9.3. Financial endpoints

- `GET /billing-accounts/{account_id}/balance`
- `GET /billing-accounts/{account_id}/statement`
- `GET /billing-accounts/{account_id}/invoices`
- `GET /billing-accounts/{account_id}/payments`
- `POST /billing-accounts/{account_id}/payments`
- `POST /billing-accounts/{account_id}/allocations/auto`
- `POST /billing-accounts/{account_id}/allocations/manual`

## 9.4. Resolve endpoints

Полезно добавить:
- `GET /billing-accounts/resolve?reference=FAM-000123`
- `GET /billing-accounts/resolve?student_number=STU-...`

Это пригодится:
- в UI;
- в M-Pesa matching;
- в будущем для parent portal.

---

## 10. UI

## 10.1. Новая страница Family / Billing Account

Нужна detail page с блоками:
- account summary;
- общий balance;
- общий outstanding;
- список детей;
- список open invoices по всем детям;
- payments history;
- family statement.

## 10.2. Student page

В карточке ученика добавить:
- linked family/billing account;
- переход на family page;
- пометку, что payment идет в общий family wallet.

## 10.3. Receive Payment

Форма оплаты должна позволять:
- выбрать billing account;
- либо открыть форму из student page, где account подставится автоматически;
- optionally выбрать preferred invoice любого ребенка в семье.

## 10.4. Students list

Полезно показывать:
- family account number;
- family display name;
- сколько детей в семье.

## 10.5. Merge / create family UX

Нужны отдельные actions:
- `Create family account from student`
- `Add student to existing family`
- `Move student to another family`

Это лучше делать отдельным dialog/flow, а не прятать в student edit form.

---

## 11. Reports и exports

Статус реализации:
- `Aged Receivables` остается student-level по invoice debt, но debt считается snapshot-ом через allocations up to `as_at_date`, а `last_payment_date` берется с linked billing account. Поэтому payment, принятый на family account, виден у каждого debtor-child этого account, и invoice, закрытый после `as_at_date`, не пропадает из исторического отчета.
- `Cash Flow` считает cash received по `Payment.billing_account_id` и сопоставляет same-day allocations тоже по `CreditAllocation.billing_account_id`, чтобы family payment корректно раскладывался по invoice types siblings.
- `Balance Sheet` считает `Billing Account Credit Balances` на уровне billing accounts: positive `completed payments - allocations`, без промежуточных отрицательных/положительных остатков на reference-student и без netting отрицательных account positions против настоящих credit balances.
- `Revenue Trend` считает denominator как количество students в billing accounts, где были payments за год, а не только `Payment.student_id` reference.
- Accountant `student-payments` CSV включает billing account columns и полный roster linked students.
- Accountant `student-balance-changes` CSV остается student-level ledger: invoices = debit, allocations = credit. Raw unallocated family payments не дублируются по детям и должны смотреться через account statement/account-level export.

Остается отдельным follow-up:
- family/account-level statement CSV/PDF;
- outstanding by billing account;
- family payment history export.

---

## 12. M-Pesa и внешние reference

## 12.1. Что должно стать каноническим reference

Канонический payment reference:
- `billing_account_number`

Пример:
- `FAM-000123`

## 12.2. Переходный режим

Чтобы не ломать существующую операционку, поддержать:
- `billing_account_number`
- `student_number`

Resolution logic:
- если пришел family account number -> платим прямо туда;
- если пришел student number -> находим ученика и его billing account;
- если account не найден -> unmatched queue.

## 12.3. MPesa unmatched

Экран unmatched должен уметь:
- показывать candidate family account;
- показывать candidate students;
- вручную матчить платеж на family account.

---

## 13. Порядок внедрения

## Phase 1. Foundations

1. Добавить `billing_accounts`.
2. Добавить `billing_account_members`.
3. Добавить `students.billing_account_id`.
4. Добавить `billing_account_id` в `invoices`, `payments`, `credit_allocations`.
5. Backfill: один account на каждого существующего студента.
6. Перенести balance cache с уровня student на уровень billing account.

## Phase 2. Engine changes

1. Переписать `get_balance`, `allocate_auto`, `allocate_manual`, statement на account-level owner.
2. Сохранить student-level invoice ownership.
3. Сохранить `preferred_invoice_id`.
4. Обновить payment completion flow.

## Phase 3. Admin operations

1. CRUD billing accounts.
2. Add/remove member.
3. Merge/move student flows.
4. Validation rules и audit logging.

## Phase 4. UI

1. Family list/detail pages.
2. Student page integration.
3. Receive payment by billing account.
4. Update payments/invoices pages.

## Phase 5. Integrations and reports

1. M-Pesa reference resolution.
2. Family statement/export.
3. Family-level receivables reports.

---

## 14. Риски

### 14.1. Исторические данные

Главный риск:
- при merge/transfer можно случайно "перекинуть" исторические долги не туда.

Решение:
- snapshot `billing_account_id` на invoice;
- отдельный explicit transfer flow;
- ограничить авто-перенос исторических invoice.

### 14.2. Смешение student debt и family credit

Пользователь может увидеть:
- student A debt 10,000
- family credit 8,000

Без хорошего UI это будет путать.

Решение:
- на student page показывать family context;
- на family page показывать aggregate balances;
- не пытаться скрывать distinction между child debt и family wallet.

### 14.3. Performance

Family auto-allocation будет трогать больше invoice и больше join.

Нужны индексы:
- `students.billing_account_id`
- `invoices.billing_account_id`
- `payments.billing_account_id`
- `credit_allocations.billing_account_id`
- `billing_account_members.billing_account_id`

### 14.4. Concurrency

Если одновременно приходят несколько family payments:
- нужен нормальный transactional update balance cache;
- желательно избегать race conditions при auto-allocation.

---

## 15. MVP scope

Если делать прагматично, MVP должен включать:
- `billing_accounts`
- membership студентов
- account-level balance
- account-level payments
- account-level auto-allocation
- family detail page
- receive payment on family account
- support `preferred_invoice_id`

Что можно отложить:
- сложный merge historical debt
- family-level report pack
- advanced alias table
- parent portal

---

## 16. Рекомендация по внедрению

Я рекомендую внедрять фичу именно как `BillingAccount`, а не как "семейный флажок у Student".

Правильная архитектура:
- student = owner of invoice
- billing account = owner of money
- allocation = bridge between family money and student invoice

Это даст:
- общий семейный кошелек;
- прозрачную финансовую историю;
- нормальную поддержку targeted payments;
- устойчивую основу для M-Pesa, statement и будущего parent portal.

Если делать это следующим шагом, safest path такой:
1. Ввести account-level owner без изменения поведения через one-student-per-account backfill.
2. Потом открыть ручное объединение студентов в семьи.
3. Только после этого менять payment references и M-Pesa matching.
