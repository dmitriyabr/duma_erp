# План рефакторинга фронтенда (ERP)

Документ составлен по результатам аудита кодовой базы фронтенда. Цель — зафиксировать слабые места и план их исправления без немедленной реализации в коде.

---

## Прогресс (ветка feature/frontend-refactoring)

- **1.1 Студенты:** сделано — один batch `POST /payments/students/balances-batch` возвращает кредит, долг и чистый баланс (считается на бэкенде); StudentsPage один запрос, без `GET /invoices/outstanding-totals`.
- **1.3 Резервации:** сделано — в `ReservationResponse` добавлено поле `student_name`; ReservationsPage убран запрос `/students?limit=500`.
- **4. Поиск:** сделано — хук `useDebouncedValue(400ms)` на StudentsPage, UsersPage, StockPage.
- **5.1 Типы:** сделано — общие `ApiResponse` и `PaginatedResponse` в `frontend/src/app/types/api.ts`.
- **8.1 Мелкое:** сделано — удалён `ProcurementPaymentsListPage.tsx.bak`.
- **1.2 Payouts:** сделано — batch-эндпоинт для балансов сотрудников; PayoutsPage использует один запрос.
- **1.4 Форма выдачи:** сделано — лимиты студентов/пользователей 500→200 через константу `MAX_DROPDOWN_SIZE`.
- **5.2 InvoicesTab:** сделано — форма «Add line» только для Kit (убрана опция Item, приведено к контракту API).
- **7.1 Загрузка таблиц:** сделано — во всех списковых таблицах при `loading === true` показывается строка «Loading…».
- **8.4 Константы лимитов:** сделано — `frontend/src/app/constants/pagination.ts`: `DEFAULT_PAGE_SIZE`, `MAX_DROPDOWN_SIZE`, `INVOICE_LIST_LIMIT`, `PAYMENTS_LIST_LIMIT`, `SECONDARY_LIST_LIMIT`; использованы в IssueFormPage, InvoicesTab, PaymentsTab, ItemsToIssueTab, StudentDetailPage.

- **5.3 Единый разбор ответа API:** сделано — `unwrapResponse<T>(response)` в `services/api.ts`; использован в InvoicesTab, PaymentsTab, CatalogPage, TermDetailPage, SchoolPage, CreateInvoicePage.
- **7.2 Error Boundary:** сделано — компонент `ErrorBoundary` в `components/ErrorBoundary.tsx`, оборачивает `AppLayout` в роутах; при ошибке показывается сообщение и кнопки «Go back» / «Try again».
- **8.5 Роли и доступ:** сделано — модуль `utils/permissions.ts`: `isSuperAdmin`, `canCancelPayment`, `canApproveClaim`, `canApproveGRN`, `canManageReservations`, `canManageStock`, `canCreateItem`, `canCancelIssuance`, `canInvoiceTerm`; использованы в InvoicesTab, PaymentsTab, ReservationsPage, StockPage, ExpenseClaimsListPage, ExpenseClaimDetailPage, IssuancesPage, GRNDetailPage.

- **2.1 Карточка студента и вкладки:** сделано — список счетов загружается один раз в StudentDetailPage (useApi /invoices), долг считается из него (useMemo); InvoicesTab и PaymentsTab получают initialInvoices и invoicesLoading; при мутациях вызывается onDebtChange → refetch в родителе. InvoicesTab при initialInvoices фильтрует по поиску на клиенте.
- **8.3 useApi:** сделано — в JSDoc зафиксировано: запрос ключится по url + JSON.stringify(options), передавать стабильные options (useMemo).

- **8.2 Синхронизация URL и вкладок:** сделано — вкладка выводится из searchParams (tab = searchParams.get('tab') ?? 'overview'), валидация допустимых значений; при прямом заходе по URL с ?tab=payments открывается нужная вкладка без вспышки.
- **2.2 Справочники Grades и Transport zones:** сделано — контекст ReferencedDataContext (ReferencedDataProvider в роутах вокруг AppLayout); один раз загружаются /students/grades и /terms/transport-zones; используют StudentDetailPage, StudentsPage, TermFormPage, TermDetailPage, GradesPage, TransportZonesPage; после мутаций в GradesPage/TransportZonesPage вызывается refetchGrades/refetchTransportZones.

**Константы лимитов (добивка):** добавлена `USERS_LIST_LIMIT = 100`; использованы `DEFAULT_PAGE_SIZE` для начального limit на StudentsPage и UsersPage; `USERS_LIST_LIMIT` — в PayoutsPage, ExpenseClaimsListPage, ProcurementPaymentFormPage; `SECONDARY_LIST_LIMIT` — в OverviewTab (discounts).

---

## Отложено (рекомендации на следующий этап)

### 3. Кэширование запросов (TanStack Query)

**Почему отложено:** Введение TanStack Query затрагивает все вызовы `useApi` и мутаций; справочники уже кэшируются через ReferencedDataContext. При росте приложения имеет смысл поэтапно мигрировать на TanStack Query (useQuery/useMutation) с настройкой staleTime/cacheTime.

**Рекомендация:** Добавить зависимость `@tanstack/react-query`, обернуть приложение в `QueryClientProvider`, по одному экрану переводить useApi → useQuery и мутации → useMutation; затем единообразно настроить инвалидацию.

### 6. Пагинация в UI для «длинных» списков без пагинации

**Почему отложено:** Списки в рамках одного студента (invoices, payments, discounts, reservations) ограничены константами (INVOICE_LIST_LIMIT, SECONDARY_LIST_LIMIT и т.д.). При росте данных можно добавить TablePagination или «Load more» на этих вкладках.

**Рекомендация:** При появлении сценариев «счетов/платежей больше 200» — добавить пагинацию по страницам или кнопку «Загрузить ещё» с увеличением limit/offset.

---

## 1. Критичные проблемы производительности (N+1 и лавина запросов)

### 1.1 Страница студентов (StudentsPage) — запрос на каждого студента

**Проблема:** После загрузки списка студентов для **каждого** студента в текущей странице выполняются два запроса:
- `GET /payments/students/{id}/balance` — баланс
- `GET /invoices?student_id={id}&limit=500` — для расчёта долга (сумма `amount_due` по неоплаченным счетам)

При 25 студентах на странице это **1 + 25 + 25 = 51** запрос. При 100 студентах — более 200 запросов. Страница открывается очень долго.

**Решение:**
- **Backend:** Добавить batch-эндпоинты или расширить ответ списка студентов:
  - Вариант A: `GET /students?…&include_balance=true&include_debt=true` — в каждом элементе списка возвращать `available_balance` и `outstanding_debt` (бэкенд считает одним запросом/подзапросами).
  - Вариант B (реализован): `POST /payments/students/balances-batch` возвращает `outstanding_debt` и `balance` (net) на бэкенде; один запрос вместо двух.
- **Frontend:** Использовать один запрос `balances-batch`, колонка Balance из `balance` в ответе.

### 1.2 Страница выплат (PayoutsPage) — запрос баланса на каждого сотрудника

**Проблема:** Загружается список пользователей `GET /users?limit=100`, затем для **каждого** сотрудника вызывается `GET /compensations/payouts/employees/{id}/balance`. 100 пользователей = 101 запрос при открытии страницы.

**Решение:**
- **Backend:** Эндпоинт `GET /compensations/payouts/employee-balances?limit=…` или `POST .../balances-batch` с массивом `employee_id`, возвращающий список `{ employee_id, total_approved, total_paid, balance }`.
- **Frontend:** Один запрос за всеми балансами, убрать `loadBalances` с циклом по `employees`.

### 1.3 Резервации (ReservationsPage) — загрузка 500 студентов для имён

**Проблема:** Список резерваций приходит с бэка с полем `student_id`, но без `student_name`. Фронт загружает `GET /students?page=1&limit=500` только чтобы по `student_id` подставить имя в таблице. Лишний большой запрос и хрупкая связка.

**Решение:**
- **Backend:** В `ReservationResponse` (или в сервисе при формировании списка) добавить поле `student_name` (или `student_full_name`): джойн с Student при выборке или подстановка из кэша. Тогда фронту не нужен список всех студентов.
- **Frontend:** Убрать `useApi<PaginatedResponse<StudentOption>>('/students?page=1&limit=500')` и использование `students` для маппинга; отображать `reservation.student_name` из ответа API.

### 1.4 Форма выдачи (IssueFormPage) — тяжёлые справочники при открытии

**Проблема:** При открытии страницы `/inventory/issue` сразу выполняются три запроса: `/items` (products), `/students?limit=500`, `/users?limit=500`. Два из них — большие списки только для двух выпадающих списков (получатель: студент или сотрудник).

**Решение:**
- Оставить один общий запрос за «получателями» (студенты + пользователи) с бэка, если такой эндпоинт появится (опционально).
- Или: загружать списки студентов и пользователей только при выборе типа получателя Student/Employee (lazy load), с пагинацией или поиском (autocomplete) вместо выгрузки 500 записей.
- Унифицировать лимиты (например, 100 или 200) и по возможности кэшировать справочники (см. раздел 3).

---

## 2. Дублирование запросов и данных

### 2.1 Карточка студента (StudentDetailPage) и вкладки Invoices / Payments

**Проблема:**
- Долг студента считается в `StudentDetailPage`: `GET /invoices?student_id=…&limit=200` и суммирование `amount_due` вручную.
- Вкладка **Invoices** запрашивает тот же список счетов: `GET /invoices?student_id=…&limit=200`.
- Вкладка **Payments** тоже запрашивает счета: `GET /invoices?student_id=…&limit=200` (для модалки ручной аллокации).

Один и тот же список счетов запрашивается до трёх раз (при переключении вкладок и при открытии карточки). Плюс баланс: `StudentDetailPage` запрашивает balance, при смене вкладок refetch не всегда согласован.

**Решение:**
- Поднять состояние «список счетов студента» и «баланс» на уровень `StudentDetailPage` (или контекста студента): один раз загружать и передавать во вкладки через props или контекст. Вкладки Invoices и Payments используют эти данные, при мутациях (новый платёж, новая строка счёта и т.д.) вызывать общий refetch.
- Либо ввести минимальный «студент-контекст» с данными student, balance, debt, invoices и обновлять его после действий.

### 2.2 Справочники Grades и Transport zones

**Проблема:** `StudentDetailPage`, `StudentsPage`, `TermFormPage`, `TermDetailPage` и др. запрашивают одни и те же справочники: `/students/grades`, `/terms/transport-zones`. Каждый компонент держит свой `useApi`, при переходах между страницами запросы повторяются.

**Решение:**
- Вынести загрузку справочников в общий слой: React Context, либо глобальный кэш (например, React Query / TanStack Query), с единой точкой обновления. Страницы и формы подписаны на кэш, а не на отдельные useApi для grades/transport-zones.

---

## 3. Отсутствие кэширования и дедупликации запросов

**Проблема:**
- Каждый переход на страницу приводит к полному refetch. Нет единого кэша по URL или ключу запроса.
- Один и тот же URL в двух компонентах даёт два одинаковых запроса (например, grades в хедере студента и в форме).
- При возврате со страницы студента на список студентов список и все N+1 запросы выполняются заново.

**Решение:**
- Ввести клиентский кэш запросов: TanStack Query (React Query) или аналог. Настроить staleTime / cacheTime для списков и справочников, чтобы повторные переходы не дергали API без необходимости.
- Либо расширить текущий `useApi`: добавить опциональный кэш по ключу (url + params), инвалидация при мутациях (refetch после create/update/delete).

---

## 4. Поиск без debounce

**Проблема:** На страницах со поиском (Students, Users, Items, Stock, Movements, Catalog) значение поля поиска попадает в параметры запроса и в зависимость `useApi`. Каждое изменение инпута (каждый символ) вызывает новый запрос к API. При быстром наборе «Иванов» уходит до 6+ запросов.

**Где:** `StudentsPage`, `UsersPage`, `ItemsPage`, `StockPage`, `MovementsPage`, `CatalogPage`.

**Решение:**
- Ввести debounce (300–500 ms) для значения поиска перед тем, как передавать его в параметры API. Использовать локальный state для инпута и «отложенное» значение для запроса (другой state или useDeferredValue после debounce).
- Либо единый хук `useDebouncedValue(value, delay)` и передавать в `requestParams` уже отложенное значение.

---

## 5. Типы и контракты API

### 5.1 Дублирование типов между файлами

**Проблема:** Интерфейсы `PaginatedResponse<T>`, `ApiResponse<T>` объявлены во многих файлах: `StudentsPage`, `ReservationsPage`, `UsersPage`, `PurchaseOrderDetailPage`, `ProcurementPaymentsListPage`, `GRNListPage`, `ItemsPage`, `StockPage`, `MovementsPage`, `IssueFormPage`, `PayoutsPage`, `ExpenseClaimsListPage`, `PurchaseOrderFormPage`, `ProcurementPaymentFormPage`, `PayoutDetailPage`, `InventoryCountPage` и т.д. Локальные копии ведут к расхождениям (например, в одном месте есть поле `pages`, в другом нет).

**Решение:**
- Вынести общие типы в один модуль, например `frontend/src/app/types/api.ts` или `services/api.types.ts`: `ApiResponse<T>`, `PaginatedResponse<T>`, общие типы фильтров. Импортировать их во всех страницах и убрать локальные объявления.

### 5.2 Несоответствие UI и API (InvoicesTab — добавление строки счёта)

**Проблема:** В форме «Add invoice line» в `InvoicesTab` есть выбор «Line type»: Item или Kit, и в payload уходит либо `item_id`, либо `kit_id`. Согласно BACKEND_API и коду бэка, строка счёта (InvoiceLine) поддерживает только `kit_id`; `item_id` в API нет. То есть выбор «Item» и отправка `item_id` — устаревшее или ошибочное поведение, бэк может не принимать item_id.

**Решение:**
- Привести форму к контракту API: только добавление строки по `kit_id`. Убрать опцию «Item» из выбора типа строки либо явно маппить выбранный Item к одному Kit на бэке (если такая логика предусмотрена). Иначе — оставить в UI только выбор Kit для строки счёта.

### 5.3 Единый формат ответа API на фронте

**Проблема:** В разных местах ответ оборачивают по-разному: `(r.data as { data: T }).data`, `(r.data as { data?: unknown })?.data ?? true`, что усложняет чтение и даёт риск ошибок.

**Решение:**
- Ввести одну функцию-хелпер разбора ответа API (например, `unwrapResponse<T>(response): T`) и использовать её в useApi и при ручных вызовах api.get/post. Типы ответов описать в общих api.types.

---

## 6. Загрузка списков без пагинации на UI

**Проблема:** Некоторые списки запрашиваются с большим `limit` (200, 500) без пагинации в интерфейсе:
- InvoicesTab: invoices `limit: 200`, termInvoices `limit: 200`;
- PaymentsTab: payments `limit: 100`, invoices `limit: 200`;
- OverviewTab: discounts `limit: 200`;
- ItemsToIssueTab: reservations `limit: 200`;
- StudentsPage: при расчёте долга запрос invoices с `limit: 500`.

При росте данных страница может тормозить и потреблять лишнюю память.

**Решение:**
- Где возможно, добавить пагинацию на UI (таблица + page/limit) и запрашивать по страницам.
- Где пагинация не нужна (например, счета одного студента), оставить разумный лимит (например, 100) и при необходимости добавить «Load more» или предупреждение, если счетов больше лимита.

---

## 7. Состояние загрузки и ошибок

### 7.1 Таблица отображается до прихода данных

**Проблема:** На нескольких страницах таблица рендерится сразу; строка «No … found» показывается по условию `!rows.length && !loading`. Пока `loading === true`, пользователь видит пустую таблицу без индикатора загрузки (спиннер/скелетон), что создаёт впечатление «ничего нет».

**Решение:**
- Пока `loading === true`, показывать индикатор загрузки (например, `<TableRow><TableCell colSpan={…}>Loading…</TableCell></TableRow>` или скелетон таблицы). Сообщение «No … found» выводить только когда `!loading && !rows.length`.

### 7.2 Ошибки только в Alert, без границ ошибок

**Проблема:** Ошибки API показываются через локальный state и Alert. Нет единой границы ошибки (Error Boundary) для падения компонента при необработанном исключении; при сбое одного виджета может «падать» вся страница без понятного сообщения.

**Решение:**
- Добавить Error Boundary на уровне маршрута или layout и показывать запасной UI с текстом ошибки и кнопкой «Обновить» / «Назад».
- По желанию логировать ошибки в один сервис для отладки.

---

## 8. Мелкие и средние улучшения

### 8.1 Удалить мёртвый код и бэкапы

- **Файл:** `ProcurementPaymentsListPage.tsx.bak` — бэкап не должен храниться в репозитории. Удалить и при необходимости полагаться на историю git.

### 8.2 Синхронизация URL и вкладок студента

- Уже реализовано: вкладка в `searchParams` (`?tab=invoices`). Стоит проверить обратную синхронизацию (при прямом заходе по URL с `?tab=payments` вкладка открывается корректно). Если есть баги — внести в план правки.

### 8.3 useApi: зависимости и стабильность

- В `useApi` зависимости запроса завязаны на `url` и `JSON.stringify(options)`. При передаче объекта `options` с новой ссылкой каждый рендер даёт ту же строку, так что лишних запросов нет. Стоит зафиксировать в коде или в правилах: параметры в `options` передавать стабильно (например, через useMemo), чтобы не полагаться на случайное совпадение JSON.

### 8.4 Константы лимитов и дефолтов

- Сейчас лимиты (25, 50, 100, 200, 500) и значения пагинации разбросаны по компонентам. Имеет смысл вынести в константы (например, `DEFAULT_PAGE_SIZE = 25`, `MAX_DROPDOWN_SIZE = 200`) и использовать в одном месте, чтобы легче менять и согласовывать с бэком.

### 8.5 Роли и доступ к кнопкам

- Проверки вроде `user?.role === 'SuperAdmin'` повторяются в разных компонентах. Можно вынести хелперы `canCancelPayment(user)`, `canApproveClaim(user)` и т.п. в один модуль прав и использовать их в UI, чтобы не дублировать строки и не забыть обновить при смене правил.

---

## 9. Рекомендуемый порядок работ

1. **Критично по производительности:** п. 1.1 (студенты), 1.2 (payouts), 1.3 (резервации). Затем при необходимости 1.4 (форма выдачи).
2. **Снижение дублирования запросов:** п. 2.1 (данные студента и вкладки), 2.2 (справочники) + п. 3 (кэш).
3. **Поиск:** п. 4 (debounce) — быстро даёт выигрыш по количеству запросов.
4. **Типы и контракты:** п. 5.1, 5.2, 5.3.
5. **Пагинация и UX:** п. 6, 7.
6. **Уборка и константы:** п. 8.

---

## Итог рефакторинга (ветка feature/frontend-refactoring)

Выполнено: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 4, 5.1, 5.2, 5.3, 7.1, 7.2, 8.1–8.5, константы лимитов (в т.ч. DEFAULT_PAGE_SIZE, USERS_LIST_LIMIT в оставшихся местах).  
Отложено: п. 3 (TanStack Query), п. 6 (пагинация на вкладках студента) — см. раздел «Отложено» выше.
