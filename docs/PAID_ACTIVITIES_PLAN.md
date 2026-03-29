# План фичи: платные активности и массовое выставление счетов

## 1. Цель

Нужен механизм для платных школьных активностей, например:
- экскурсия;
- `fun day`;
- поездка/соревнование;
- разовый школьный ивент.

Система должна позволять:
- создать активность как отдельную сущность;
- определить, кому она выставляется;
- массово выписать счета выбранным ученикам;
- не дублировать уже выставленные счета;
- видеть прогресс: кому счёт создан, кто оплатил, кто исключён;
- использовать уже существующий billing-поток: invoices, payments, allocations, reports.

---

## 2. Что уже есть в системе

### 2.1. Что можно переиспользовать

- `Invoice` уже умеет:
  - хранить сумму, статус, due date, invoice lines;
  - участвовать в auto-allocation;
  - отображаться в student profile, общем списке invoices и отчётах.
- `Payment` и `CreditAllocation` уже работают корректно:
  - payment попадает в credit balance;
  - allocation списывает credit на invoice;
  - после `payment.complete` система запускает `allocate_auto`.
- Есть массовая генерация term invoices:
  - это хороший шаблон для batch-выставления activity invoices.
- Есть `Kit` как канонический source для invoice lines:
  - line item в счёте создаётся через `kit_id`;
  - для standard-price услуг уже есть готовый паттерн.
- Есть `Fixed Fees`, которые уже реализованы как `Kit` в отдельной категории:
  - это полезный ориентир, но не полноценное решение для activities.

### 2.2. Чего сейчас не хватает

- Нет сущности “Activity”.
- Нет roster/snapshot участников активности.
- Нет защиты от повторного выставления activity invoice одному и тому же ученику.
- Нет отдельной аналитики по activity billing.
- Если activity проводить как обычный `adhoc invoice`, она смешается с любыми другими разовыми продажами.

---

## 3. Почему не стоит делать это только через Fixed Fees

Вариант “создать fixed fee и потом массово генерировать adhoc invoices” выглядит быстрым, но у него есть системные минусы:

- нет отдельной сущности активности;
- нельзя нормально хранить дату события, описание, статус активности;
- нет снимка участников на момент запуска;
- нет статусов уровня activity: `draft`, `published`, `invoicing`, `closed`, `cancelled`;
- нет защиты от дублей в рамках одной активности;
- activity invoices попадут в `adhoc` и смешаются в отчётах с любыми другими “other fees”.

Итог: `Fixed Fees` можно использовать как архитектурный ориентир для ценовой модели (`Kit` + standard price), но не как полноценную бизнес-модель.

---

## 4. Рекомендуемый дизайн

### 4.1. Общий принцип

Сделать отдельный модуль `Activities`, но не изобретать новый billing engine.

То есть:
- **Activity** отвечает за бизнес-смысл события;
- **ActivityParticipant** отвечает за состав участников и статус биллинга;
- **Invoice / Payment / Allocation** остаются существующими сущностями для денег.

Это лучший баланс между:
- скоростью внедрения;
- прозрачностью для пользователей;
- совместимостью с текущими экранами и отчётами;
- минимальным дублированием логики.

### 4.2. Ключевое решение

Для activity billing рекомендую **добавить новый `invoice_type = activity`**, а не использовать `adhoc`.

Почему:
- activities станут отдельной категорией в отчётах;
- cash flow / P&L не будут смешивать их с прочими разовыми счетами;
- в будущем можно строить отчёты “сколько собрано по активностям”.

---

## 5. Предлагаемая модель данных

## 5.1. Activity

Новая таблица `activities`.

Пример полей:

| Поле | Тип | Назначение |
|------|-----|------------|
| id | BIGINT PK | |
| activity_number | VARCHAR(50) UNIQUE | ACT-YYYY-NNNNNN |
| code | VARCHAR(100) UNIQUE NULL | короткий код, если нужен |
| name | VARCHAR(255) | название активности |
| description | TEXT NULL | описание |
| activity_date | DATE NULL | дата события |
| due_date | DATE NULL | срок оплаты |
| term_id | BIGINT NULL | если активность относится к term |
| status | VARCHAR(20) | `draft`, `published`, `billing_in_progress`, `closed`, `cancelled` |
| audience_type | VARCHAR(20) | `all_active`, `grades`, `manual` |
| amount | DECIMAL(15,2) | стандартная цена на одного ученика |
| requires_full_payment | BOOLEAN | нужно ли полное покрытие для “полезности” activity invoice |
| auto_issue_invoices | BOOLEAN | создавать сразу `ISSUED`, без draft |
| notes | TEXT NULL | |
| created_activity_kit_id | BIGINT NULL | связанный `Kit`, если создаётся автоматически |
| created_by_id | BIGINT | |
| created_at / updated_at | timestamptz | |

### 5.2. ActivityAudienceGrade

Нужна только если поддерживаем таргетинг по классам.

| Поле | Тип |
|------|-----|
| id | BIGINT PK |
| activity_id | BIGINT FK |
| grade_id | BIGINT FK |

`UNIQUE(activity_id, grade_id)`

### 5.3. ActivityParticipant

Ключевая таблица, без неё фича будет хрупкой.

| Поле | Тип | Назначение |
|------|-----|------------|
| id | BIGINT PK | |
| activity_id | BIGINT FK | |
| student_id | BIGINT FK | |
| status | VARCHAR(20) | `planned`, `invoiced`, `paid`, `cancelled`, `skipped` |
| selected_amount | DECIMAL(15,2) | snapshot цены на ученика |
| invoice_id | BIGINT NULL | счёт, если создан |
| invoice_line_id | BIGINT NULL | строка activity line |
| excluded_reason | TEXT NULL | если ученик был вручную исключён |
| added_manually | BOOLEAN | был ли добавлен вне auto audience |
| created_at / updated_at | timestamptz | |

Критично:
- `UNIQUE(activity_id, student_id)`

Это даст:
- идемпотентную batch-генерацию;
- защиту от двойного включения ученика;
- понятный roster и billing progress.

---

## 6. Связь с Kit и invoice lines

### 6.1. Как выставлять line item

Так как invoice line в системе уже строится через `kit_id`, activity тоже должна использовать `Kit`.

Рекомендую:
- при создании activity автоматически создавать service `Kit`;
- держать связь `Activity.created_activity_kit_id`;
- для invoice line использовать этот kit.

Параметры такого kit:
- `item_type = service`
- `price_type = standard`
- `price = activity.amount`
- `requires_full_payment = activity.requires_full_payment`
- category: лучше отдельная категория, например `Activities`, а не `Fixed Fees`

### 6.2. Почему отдельный kit лучше, чем один общий

Отдельный kit на activity даёт:
- понятное название в invoice line;
- удобство фильтрации и аудита;
- возможность менять цену/active state без влияния на другие активности;
- меньше “магии” в отчётах и UI.

Важно:
- invoice line всё равно должна сохранять свой `unit_price` snapshot;
- изменение `Activity.amount` или `Kit.price` не должно переписывать старые invoices.

---

## 7. Бизнес-правила

### 7.1. Audience

На старте достаточно трёх режимов:
- `all_active` — все активные ученики;
- `grades` — только выбранные классы;
- `manual` — только вручную выбранные ученики.

### 7.2. Snapshot участников

Audience нужно не вычислять “на лету” каждый раз, а **сохранять как snapshot** в `ActivityParticipant`.

Почему:
- состав учащихся меняется;
- activity может быть создана заранее;
- важно понимать, кому именно activity была назначена на момент публикации.

### 7.3. Invoice generation

Рекомендую такой поток:

1. Activity создаётся в `draft`.
2. Админ формирует audience.
3. Система создаёт/обновляет `ActivityParticipant`.
4. Админ нажимает `Generate invoices`.
5. По каждому участнику:
   - если `invoice_id` уже есть, пропускаем;
   - если участник `cancelled/skipped`, пропускаем;
   - создаём отдельный invoice типа `activity`;
   - создаём одну line с activity kit;
   - ставим invoice в `ISSUED`;
   - сохраняем `invoice_id` и `invoice_line_id` в participant.
6. После batch-generation запускаем `allocate_auto` по затронутым студентам.

### 7.4. Идемпотентность

Повторный запуск генерации должен:
- не дублировать счета для уже invoiced участников;
- создавать только missing invoices;
- быть безопасным после partial failures.

### 7.5. Оплата

Отдельной логики оплаты для activity не нужно.

После выставления activity invoice:
- он участвует в общей задолженности ученика;
- закрывается обычными allocations;
- попадает в student statement и общий payments flow.

### 7.6. Exclusions / late changes

Нужны базовые операции:
- исключить ученика до генерации invoice;
- добавить ученика в activity после публикации;
- сгенерировать invoice только для нового участника.

### 7.7. Что делать с уже оплаченным activity invoice при отмене участия

Это отдельный сложный кейс.

На MVP я рекомендую:
- **не поддерживать автоматический reversal/void оплаченного activity invoice**;
- разрешить отмену участника только пока invoice не оплачен;
- если уже оплачено, обрабатывать вручную как финансовое исключение.

Причина:
- в системе пока нет полноценного публичного flow для reversal оплаченных invoices.

---

## 8. Изменения в backend

### 8.1. Миграции

Понадобятся:
- новая таблица `activities`;
- новая таблица `activity_audience_grades` (если делаем таргетинг по классам);
- новая таблица `activity_participants`;
- расширение `InvoiceType` значением `activity`.

### 8.2. Новый модуль

Предлагаемый модуль:
- `src/modules/activities/models.py`
- `src/modules/activities/schemas.py`
- `src/modules/activities/service.py`
- `src/modules/activities/router.py`

### 8.3. ActivityService

Ключевые методы:
- `create_activity`
- `update_activity`
- `publish_activity`
- `build_participants_snapshot`
- `add_participant`
- `exclude_participant`
- `generate_invoices`
- `generate_missing_invoices`
- `get_activity_progress`

### 8.4. Интеграция с InvoiceService

Нужно не ломать текущий `InvoiceService`, а переиспользовать его паттерны:
- создавать invoice через существующую модель;
- line добавлять через существующую логику kit pricing;
- после issue вызывать `allocate_auto`.

Вариант реализации:
- либо переиспользовать внутренние helper methods `InvoiceService`;
- либо добавить новый специализированный helper для server-side batch invoice creation.

### 8.5. Идемпотентность и транзакции

Для batch generation лучше делать:
- один participant = одна атомарная операция создания invoice;
- весь batch не должен падать из-за одной проблемной записи;
- итогом возвращать summary:
  - `participants_total`
  - `invoices_created`
  - `participants_skipped`
  - `errors[]`

---

## 9. API

Минимальный набор endpoints:

### 9.1. Activity CRUD

- `POST /activities`
- `GET /activities`
- `GET /activities/{activity_id}`
- `PATCH /activities/{activity_id}`

### 9.2. Audience / participants

- `POST /activities/{activity_id}/participants/snapshot`
- `GET /activities/{activity_id}/participants`
- `POST /activities/{activity_id}/participants`
- `POST /activities/{activity_id}/participants/{participant_id}/exclude`

### 9.3. Billing

- `POST /activities/{activity_id}/generate-invoices`
- `POST /activities/{activity_id}/generate-missing-invoices`
- `GET /activities/{activity_id}/billing-summary`

### 9.4. Permissions

Роли:
- просмотр списка/деталей: `SuperAdmin`, `Admin`, `Accountant`
- создание/редактирование/generate: `SuperAdmin`, `Admin`

---

## 10. Изменения во frontend

### 10.1. Новые страницы

Рекомендую:
- `ActivitiesListPage`
- `ActivityDetailPage`
- `ActivityFormPage`

### 10.2. Что должно быть в списке

В таблице activities:
- название;
- дата;
- amount;
- audience type;
- participants total;
- invoices created;
- paid count / unpaid count;
- status.

### 10.3. Что должно быть в detail page

Блоки:
- общая информация об activity;
- список участников;
- billing summary;
- действия:
  - publish;
  - regenerate missing invoices;
  - add participant;
  - exclude participant.

### 10.4. Где это размещать в навигации

Рекомендация:
- раздел `Billing`
- отдельный пункт `Activities`

Причина:
- это ближе к student billing, чем к events/calendar.

---

## 11. Отчёты и аналитика

Если вводим `invoice_type = activity`, нужно обновить:
- revenue grouping в P&L;
- cash flow labels;
- invoice list filters;
- возможно dashboard cards позже.

Пример labels:
- `activity` -> `Activities`

Дополнительно можно позже сделать отдельный отчёт:
- `Activity collection report`
- activity -> billed / paid / unpaid / collection rate

---

## 12. MVP vs этап 2

## MVP

Достаточно сделать:
- `Activity`
- `ActivityParticipant`
- audience snapshot
- batch invoice generation
- отдельный `invoice_type = activity`
- базовый UI: list + detail + create

Без:
- публичной регистрации на activity;
- reversal уже оплаченного activity invoice;
- сложных ценовых правил;
- partial audience sync rules;
- отдельного advanced reporting.

## Этап 2

Можно добавить:
- разные цены по классам;
- optional capacity / max participants;
- self-registration / consent;
- waiver files / activity documents;
- отдельные activity reports;
- refund / reversal flow.

---

## 13. Порядок реализации

### Этап 1. Backend foundation

1. Добавить `InvoiceType.ACTIVITY`.
2. Добавить таблицы `activities` и `activity_participants`.
3. Сделать CRUD для activity.
4. Сделать participant snapshot builder.

### Этап 2. Batch billing

1. Реализовать `generate_invoices`.
2. Сохранять `invoice_id` и `invoice_line_id` в participant.
3. После генерации запускать `allocate_auto`.
4. Вернуть summary по batch operation.

### Этап 3. Frontend

1. Activities list.
2. Activity create/edit.
3. Activity detail + participants table.
4. Кнопка `Generate invoices`.

### Этап 4. Reporting

1. Добавить `activity` в labels отчётов.
2. Обновить invoice filters и invoice list UI.
3. При необходимости сделать отдельный activity report.

---

## 14. Открытые вопросы

Перед реализацией нужно подтвердить:

1. Activity invoice должен быть отдельным invoice на каждого ученика или line в уже существующем `adhoc` invoice?
   - Рекомендация: отдельный invoice.

2. Нужен ли `invoice_type = activity`?
   - Рекомендация: да.

3. Activity всегда одна цена для всех или могут быть разные цены по классам?
   - На MVP лучше одна цена.

4. Можно ли исключать ученика после оплаты?
   - На MVP лучше нет, только вручную через отдельный финансовый процесс.

5. Нужно ли activity привязывать к academic term?
   - Лучше сделать `term_id` опциональным.

---

## 15. Рекомендация к реализации

Итоговая рекомендация:

- делать **отдельный модуль `Activities`**;
- использовать текущие `Invoice`, `Payment`, `Allocation` как финансовый движок;
- для line item использовать отдельный service `Kit` на activity;
- добавить `invoice_type = activity`;
- хранить roster через `ActivityParticipant`;
- запускать массовую генерацию invoices как идемпотентную batch-операцию.

Это даст чистую архитектуру, не сломает текущий billing flow и оставит нормальную базу для дальнейшего роста фичи.
