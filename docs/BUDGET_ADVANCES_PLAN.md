# План фичи: бюджеты и выдача денег сотрудникам под операционные расходы

## 1. Цель

Нужен механизм для ситуаций, когда компания сначала выдаёт деньги сотруднику, а сотрудник потом тратит их на операционные нужды, например:

- продукты для кухни;
- бытовая химия;
- офисные расходники;
- мелкие локальные закупки без PO/GRN.

Система должна позволять:

- завести бюджет направления, а не "бюджет сотрудника";
- выдать часть бюджета конкретному сотруднику под отчёт;
- видеть, у кого сейчас деньги на руках;
- фиксировать фактические траты через существующий flow `ExpenseClaim`;
- автоматически закрывать такие траты из ранее выданных денег, без `CompensationPayout`;
- видеть остаток по бюджету и по каждой выдаче;
- не смешивать этот процесс с обычным reimbursement, когда сотрудник тратит свои личные деньги.

---

## 2. Что уже есть в системе

### 2.1. Что можно переиспользовать

- `ExpenseClaim` уже умеет:
  - хранить сумму, дату, описание, proof;
  - проходить approval flow;
  - связываться с `ProcurementPayment`.
- `ProcurementPayment` уже является единым журналом расходов:
  - claim создаёт связанный payment;
  - category/purpose уже существует через `PaymentPurpose`.
- `Attachment` уже покрывает подтверждения и файлы.
- `Bank reconciliation` уже умеет матчить исходящие движения банка с внутренними документами.
- `Employees` уже выделяются в отдельный HR-контур, и фича должна быть совместима с будущим переходом compensations на `employees.id`.

### 2.2. Что уже есть, но не подходит как готовое решение

- `CompensationPayout` умеет выплатить сотруднику сумму и распределить её FIFO по claims.
- В `TASKS.md` уже зафиксировано, что payout может быть больше текущего approved balance, то есть технически возможен "аванс".

Но использовать `CompensationPayout` как бюджетный механизм не стоит, потому что:

- payout по смыслу относится к компенсациям сотруднику, а не к операционным авансам;
- текущие отчёты и reconciliation трактуют payout как employee compensation cash outflow;
- это смешает два разных кейса:
  - компания должна сотруднику деньги за личные траты;
  - компания уже выдала деньги сотруднику под будущие траты;
- `EmployeeBalance` перестанет быть понятным, если туда положить и reimbursements, и budget advances.

Итог: `CompensationPayout` должен остаться документом компенсации, а бюджеты и выдачи нужно моделировать отдельно.

---

## 3. Ключевое продуктовое решение

### 3.1. Бюджет не привязывается к сотруднику

Правильная модель:

- **Budget** живёт на уровне направления расходов;
- **BudgetAdvance** фиксирует выдачу конкретной суммы конкретному сотруднику;
- **ExpenseClaim** фиксирует фактическую трату;
- **BudgetClaimAllocation** резервирует и закрывает claim из ранее выданных advances.

То есть не:

- `budget -> employee`

А:

- `budget -> many advances`
- `advance -> employee`
- `claim -> budget`
- `claim allocations -> advances`

Это позволяет:

- менять сотрудника-держателя денег без закрытия бюджета;
- вести один бюджет через несколько сотрудников;
- видеть отдельно:
  - лимит бюджета;
  - сколько уже выдано;
  - сколько потрачено;
  - сколько ещё на руках;
  - сколько возвращено.

### 3.2. Budget и BudgetAdvance решают разные задачи

- **Budget** отвечает на вопрос: "Сколько можно потратить на это направление?"
- **BudgetAdvance** отвечает на вопрос: "Кому и сколько денег уже выдали?"

Это критичное разделение. Если не разделять эти сущности, система быстро станет непонятной для бухгалтерии и для менеджмента.

---

## 4. Рекомендуемый дизайн

### 4.1. Общий принцип

Сделать отдельный модуль `Budgets`, но не изобретать новый журнал фактических расходов.

То есть:

- бюджетный модуль отвечает за лимит, выдачи и остатки;
- `ExpenseClaim` остаётся документом фактической траты;
- `ProcurementPayment` остаётся канонической записью самого расхода;
- `CompensationPayout` остаётся только для reimbursement.

### 4.2. Предлагаемые сущности

#### A. Budget

Сущность бюджета направления.

Пример:

- `Kitchen supplies / May 2026 / limit 30,000`

Поля:

- `id`
- `budget_number` (`BGT-YYYY-NNNNNN`)
- `name`
- `purpose_id`
- `period_from`
- `period_to`
- `limit_amount`
- `notes`
- `status`: `draft | active | closing | closed | cancelled`
- `created_by_id`
- `approved_by_id?`
- `created_at`, `updated_at`

Продуктовое правило:

- один budget = один `PaymentPurpose`;
- один budget = один период;
- если нужно несколько направлений расходов, создаются несколько budgets, а не один "универсальный".

#### B. BudgetAdvance

Документ выдачи денег сотруднику под конкретный бюджет.

Пример:

- `5,000 выдано Mary из бюджета Kitchen supplies`

Поля:

- `id`
- `advance_number` (`BADV-YYYY-NNNNNN`)
- `budget_id`
- `employee_id`
- `issue_date`
- `amount_issued`
- `payment_method`: `mpesa | bank | cash | other`
- `reference_number?`
- `proof_text?`
- `proof_attachment_id?`
- `notes?`
- `source_type`: `cash_issue | transfer_in`
- `settlement_due_date`
- `status`: `draft | issued | overdue | settled | closed | cancelled`
- `created_by_id`
- `created_at`, `updated_at`

Смысл:

- это не расход как таковой;
- это передача денег сотруднику под отчёт;
- именно на уровне `BudgetAdvance` видно, у кого деньги на руках.

#### C. BudgetAdvanceReturn

Возврат неиспользованных денег.

Поля:

- `id`
- `return_number` (`BRT-YYYY-NNNNNN`)
- `advance_id`
- `return_date`
- `amount`
- `return_method`: `cash | bank | mpesa | other`
- `reference_number?`
- `proof_text?`
- `proof_attachment_id?`
- `notes?`
- `created_by_id`
- `created_at`

Смысл:

- один advance может закрыться не только claims, но и возвратом остатка;
- без этой сущности нельзя корректно посчитать реальный open balance по advance.

#### D. BudgetAdvanceTransfer

Документ переноса остатка из одного advance в другой.

Он нужен для трёх сценариев:

- rollover остатка в budget следующего месяца;
- передача open balance другому сотруднику;
- перенос между бюджетами одного периода по решению админа.

Поля:

- `id`
- `transfer_number` (`BTR-YYYY-NNNNNN`)
- `from_advance_id`
- `to_budget_id`
- `to_employee_id`
- `transfer_date`
- `amount`
- `transfer_type`: `rollover | reassignment | reallocation`
- `reason`
- `created_to_advance_id`
- `created_by_id`
- `created_at`

Смысл:

- перенос не делается через прямое редактирование старого advance;
- система всегда создаёт явный документ переноса и новый target advance;
- история месяца не переписывается.

#### E. BudgetClaimAllocation

Внутренняя аллокация funding источника к claim.

Поля:

- `id`
- `advance_id`
- `claim_id`
- `allocated_amount`
- `allocation_status`: `reserved | settled | released`
- `released_reason?`
- `created_at`
- `updated_at`

Смысл:

- это не bank movement;
- это внутренняя связь между выданными деньгами и claim;
- один claim может быть закрыт несколькими advances;
- один advance может частично закрывать много claims;
- те же записи используются и для reserve на submit, и для final settlement на approve.

#### F. Расширение ExpenseClaim

`ExpenseClaim` не заменяется. Он расширяется.

Новые поля:

- `budget_id?`
- `funding_source`: `personal_funds | budget`
- `budget_funding_status`: `none | reserved | settled | released`

Ключевое решение:

- claim привязывается не к конкретному advance, а к budget;
- сотрудник выбирает направление расходов;
- backend сам распределяет claim по open advances этого сотрудника внутри budget;
- если одного advance не хватает, claim может быть зарезервирован и закрыт сразу из нескольких advances FIFO.

Это лучше, чем `claim -> one advance`, потому что:

- у сотрудника может быть несколько выдач по одному budget;
- остаток может быть частично перенесён через rollover;
- модель не заставляет пользователя вручную выбирать, из какого именно "кармашка" списывать деньги.

#### G. Расширение ProcurementPayment

Текущая идея "любой claim создаёт linked `ProcurementPayment`" должна сохраниться.

Для budget-funded claim:

- payment всё ещё создаётся как запись фактического расхода;
- но он должен быть помечен как расход, оплаченный сотрудником из budget-funded денег, а не из личных.

Новые поля:

- `budget_id?`
- `funding_source`: `personal_funds | budget`

Тогда система сможет различать:

- `employee_paid_id != null` и `funding_source=personal_funds`:
  обычный out-of-pocket claim;
- `employee_paid_id != null` и `funding_source=budget`:
  расход из ранее выданного advance.

---

## 5. Жизненный цикл

### 5.1. Budget

`draft -> active -> closing -> closed | cancelled`

Правила:

- в `draft` можно редактировать лимит и период;
- только `active` budget позволяет создавать advances;
- когда период бюджета закончился, бюджет должен перейти в `closing`;
- в `closing` новые advances создавать нельзя, но можно доводить до конца уже выданные advances, claims и returns;
- `closed` означает, что новых advances и новых claims по нему создавать нельзя;
- `cancelled` допустим только если по бюджету нет issued advances.

### 5.2. BudgetAdvance

`draft -> issued -> overdue -> settled | closed | cancelled`

Дополнительно:

- `cancelled` возможен только до фактической выдачи;
- `overdue` означает, что по advance есть open balance после даты отчётности;
- `settled` означает, что вся сумма funding уже разнесена между claims, returns и transfers out;
- `closed` означает, что документ финально закрыт и больше не участвует в операционной работе.

Практический смысл статусов:

- `issued`: деньги выданы, advance активен;
- `overdue`: сотрудник не закрыл остаток в срок;
- `settled`: open balance = `0`, но документ ещё не архивирован;
- `closed`: документ финально закрыт, редактирование запрещено.

### 5.3. Budget-funded ExpenseClaim

Рекомендуемый flow:

1. сотрудник выбирает активный `Budget`;
2. создаёт claim как обычно: дата, описание, сумма, proof;
3. backend проверяет, что у сотрудника внутри этого budget есть достаточный доступный остаток по open advances;
4. при submit система создаёт `BudgetClaimAllocation` со статусом `reserved` и при необходимости распределяет сумму по нескольким advances FIFO;
5. claim уходит на `pending_approval`;
6. при approve система:
   - переводит `BudgetClaimAllocation` из `reserved` в `settled`;
   - уменьшает доступный остаток использованных advances;
   - переводит claim сразу в `paid`;
   - выставляет `paid_amount = amount`, `remaining_amount = 0`.

Почему claim сразу становится `paid`:

- компания уже не должна сотруднику деньги;
- funding был выдан раньше;
- payout для такого claim не нужен.

Если claim:

- отправлен на доработку: все `reserved` allocations переводятся в `released`;
- rejected: все `reserved` allocations переводятся в `released`, расход не считается подтверждённым;
- edited после submit: старые reservations снимаются и считаются заново;
- approved: claim считается закрытым из advances, а не ожидающим payout.

### 5.4. Что происходит, когда месяц закончился

Для месячного бюджета конец месяца не означает автоматическое списание или ручную правку старых документов.

Полная политика периода:

1. когда наступила дата после `period_to`, budget переходит в `closing`;
2. новые cash issues по нему больше создавать нельзя;
3. claims с `expense_date` позже `period_to` к этому budget привязать нельзя;
4. claims с датой расхода внутри периода ещё можно дозавести и доапрувить, пока budget не закрыт;
5. каждый open advance должен быть доведён до одного из финальных исходов:
   - `settled` через claims;
   - частично или полностью `returned`;
   - частично или полностью `transferred` в другой budget или сотруднику;
6. budget можно закрыть только когда у всех его advances `open balance = 0` и не осталось unresolved claims;
7. невыданная часть месячного лимита не переносится автоматически;
8. уже выданные, но не закрытые деньги можно перенести в следующий budget только через `BudgetAdvanceTransfer`.

То есть важно разделять:

- **конец периода бюджета**;
- **финальное закрытие всех advances по этому бюджету**.

Практически это значит:

- 31 мая бюджет мог быть на `30,000`;
- выдали advances на `18,000`;
- потратили и подтвердили `14,000`;
- `4,000` ещё остаются на руках;
- невыданные `12,000` просто не используются для июня;
- а выданные, но не закрытые `4,000` должны быть либо возвращены, либо перенесены через rollover document, либо закрыты claims.

### 5.5. Rollover в следующий месяц

Rollover является штатной частью фичи.

Правильный flow:

1. у майского advance считается `available_unreserved_amount`;
2. админ запускает `Roll over`;
3. система создаёт `BudgetAdvanceTransfer(transfer_type=rollover)`;
4. система создаёт новый advance в июньском budget:
   - `source_type=transfer_in`;
   - `amount_issued = transfer amount`;
   - `employee_id` может остаться тем же или быть изменён;
5. у старого advance фиксируется `transferred_out_amount`;
6. июньские claims должны идти уже в июньский budget, а не в майский.

Это важно, потому что:

- май остаётся маем в отчётах;
- июнь получает прозрачный carried-forward остаток;
- история не искажается прямым изменением `budget_id` у старых записей.

### 5.6. Overdue control

У каждого advance должна быть дата отчётности:

- `settlement_due_date`

Правила:

- если после этой даты у advance есть `open balance > 0`, он получает статус `overdue`;
- overdue advance всё ещё может быть закрыт claims, returns или transfer;
- overdue — это не финансовый финал, а управленческий сигнал;
- в UI и отчётах overdue advances должны выделяться отдельно.

---

## 6. Ключевые бизнес-правила

### 6.1. Правила бюджета

- Бюджет задаёт общий лимит направления.
- Один budget имеет один `purpose_id`.
- Нельзя issue advance сверх доступного лимита бюджета.
- После перехода бюджета в `closing` новые advances запрещены.
- После перехода бюджета в `closing` claim с `expense_date` позже `period_to` нельзя привязывать к этому бюджету.
- Бюджет нельзя закрыть, пока по нему есть advances с `open balance > 0` или unresolved claims.
- Невыданный остаток бюджета не переносится автоматически в следующий период.

### 6.2. Правила выдачи

- Один advance принадлежит одному сотруднику.
- У сотрудника может быть несколько open advances внутри одного budget.
- Один claim может быть закрыт несколькими advances.
- Issue advance требует proof или reference так же, как payout/procurement payment.
- Transfer создаёт новый target advance и никогда не переписывает старый.

### 6.3. Правила claims

- Сотрудник может выбирать только budgets, внутри которых у него есть доступный funding.
- Claim, привязанный к budget, не должен попадать в обычный reimbursement payout flow.
- Claim сверх суммарного доступного остатка open advances внутри budget отправить нельзя.
- При `send-to-edit` или `reject` reserved amount должен освобождаться.
- При `approve` claim должен быть закрыт из advances автоматически.

### 6.4. Правила возврата

- Возврат можно записать только для `issued` или `overdue` advance.
- Нельзя вернуть больше, чем нераспределённый остаток.
- После полного распределения суммы между claims, returns и transfers out advance должен перейти в `settled`, а затем в `closed`.
- Если месяц закончился, но по advance остался остаток, advance не закрывается автоматически: он остаётся open или overdue до возврата, transfer или подтверждённых claims.

### 6.5. Правила transfer / rollover

- Transfer возможен только на `available_unreserved_amount`.
- Partial transfer допустим.
- Transfer может идти:
  - в budget следующего периода;
  - другому сотруднику в рамках того же budget;
  - в другой budget того же периода.
- Transfer в closed или cancelled budget запрещён.
- Claim следующего периода нельзя "задним числом" закрыть старым budget: сначала нужен transfer, потом claim идёт уже в новый budget.

### 6.6. Правила аудита

- Нельзя удалять issued advances, returns и settled allocations.
- Любые отмены и ручные корректировки требуют reason.
- Все статусы и суммы должны проходить через audit log.

---

## 7. Расчёты

### 7.1. Budget totals

- `direct_issue_total = sum(BudgetAdvance.amount_issued where source_type = cash_issue)`
- `transfer_in_total = sum(BudgetAdvance.amount_issued where source_type = transfer_in)`
- `returned_total = sum(BudgetAdvanceReturn.amount)`
- `transfer_out_total = sum(BudgetAdvanceTransfer.amount from advances in this budget)`
- `reserved_total = sum(BudgetClaimAllocation.allocated_amount where allocation_status = reserved and claim.budget_id = budget.id)`
- `settled_total = sum(BudgetClaimAllocation.allocated_amount where allocation_status = settled and claim.budget_id = budget.id)`
- `committed_total = direct_issue_total + transfer_in_total - returned_total - transfer_out_total`
- `open_on_hands_total = committed_total - settled_total`
- `available_unreserved_total = committed_total - settled_total - reserved_total`
- `available_to_issue = limit_amount - committed_total`

Комментарий:

- `committed_total` отражает всё funding, которое уже относится к этому budget: либо ещё на руках, либо уже подтверждено расходами;
- transfer in увеличивает нагрузку на budget следующего периода;
- transfer out и returns освобождают headroom этого budget.

### 7.2. Advance totals

- `reserved_amount = sum(BudgetClaimAllocation.allocated_amount where advance_id = X and allocation_status = reserved)`
- `settled_amount = sum(BudgetClaimAllocation.allocated_amount where advance_id = X and allocation_status = settled)`
- `returned_amount = sum(BudgetAdvanceReturn.amount where advance_id = X)`
- `transferred_out_amount = sum(BudgetAdvanceTransfer.amount where from_advance_id = X)`
- `open_balance = amount_issued - settled_amount - returned_amount - transferred_out_amount`
- `available_unreserved_amount = amount_issued - reserved_amount - settled_amount - returned_amount - transferred_out_amount`

### 7.3. Overdue and aging

- `days_overdue = current_date - settlement_due_date`, если `open_balance > 0`
- aging buckets:
  - `current`
  - `1-7 days`
  - `8-30 days`
  - `31+ days`

---

## 8. API-предложение

### 8.1. Budgets

- `POST /budgets`
- `GET /budgets`
- `GET /budgets/{budget_id}`
- `PATCH /budgets/{budget_id}`
- `POST /budgets/{budget_id}/activate`
- `GET /budgets/{budget_id}/closure` — статус закрытия периода: open advances, overdue, unresolved claims, transfer candidates
- `POST /budgets/{budget_id}/close`
- `POST /budgets/{budget_id}/cancel`

### 8.2. Budget advances

- `POST /budgets/advances`
- `GET /budgets/advances`
- `GET /budgets/advances/{advance_id}`
- `POST /budgets/advances/{advance_id}/issue`
- `POST /budgets/advances/{advance_id}/transfer`
- `POST /budgets/advances/{advance_id}/close`
- `POST /budgets/advances/{advance_id}/cancel`

### 8.3. Advance returns

- `POST /budgets/advances/{advance_id}/returns`
- `GET /budgets/advances/{advance_id}/returns`

### 8.4. Transfers

- `GET /budgets/transfers`
- `GET /budgets/transfers/{transfer_id}`

### 8.5. Claims integration

Расширить существующий API claims:

- `POST /compensations/claims`
- `PATCH /compensations/claims/{claim_id}`
- `GET /compensations/claims`
- `GET /compensations/claims/{claim_id}`

Новое поведение:

- в create/update можно передавать:
  - `funding_source`
  - `budget_id?`
- если `funding_source=budget`:
  - claim создаётся как budget-funded;
  - UI и backend не должны трактовать его как reimbursement candidate;
  - при submit создаются `BudgetClaimAllocation(reserved)`;
  - при approve claim автоматически закрывается из advances.

### 8.6. Employee-side shortcuts

Полезные endpoints:

- `GET /my/budgets`
- `GET /my/budget-advances`
- `GET /budgets/{budget_id}/my-available-balance`
- `GET /budgets/advances/{advance_id}/claims`

---

## 9. UI-предложение

### 9.1. Budget list

Колонки:

- budget number
- name
- period
- purpose
- limit
- committed
- available to issue
- settled
- returned
- open on hands
- overdue advances count
- status

### 9.2. Budget detail

Блоки:

- summary карточки;
- список advances;
- totals по budget;
- period closing widget:
  - open advances;
  - overdue advances;
  - roll over candidates;
  - unresolved claims;
- recent claims, закрытые этим budget;
- action buttons:
  - `Issue advance`
  - `Run rollover`
  - `Close budget`
  - `Cancel budget`

### 9.3. Budget advance detail

Блоки:

- сотрудник;
- source type: `cash_issue` или `transfer_in`;
- дата и способ выдачи;
- settlement due date;
- выданная сумма;
- reserved / settled / returned / transferred / available;
- overdue badge при необходимости;
- связанные claims;
- returns history;
- transfers in/out history.

### 9.4. Claim form

В форме claim добавить selector:

- `Funding source`
  - `My personal money`
  - `Budget`

Если выбран `Budget`:

- показывать dropdown budgets, по которым у сотрудника есть доступный balance;
- показывать текущий available balance;
- автоматически подставлять purpose из budget или ограничивать purpose только допустимым значением;
- менять текст UI:
  - не "request reimbursement";
  - а "report spending from issued budget funds".

На detail claim полезно показывать:

- budget;
- funding status;
- allocations by advance.

### 9.5. Payouts page

Ничего не менять по смыслу.

Важно:

- бюджетные claims не должны появляться как задолженность к выплате;
- `CompensationPayout` остаётся только экраном reimbursements.

---

## 10. Отчёты и reconciliation

### 10.1. Что нужно добавить

- Budget utilization report:
  - budget;
  - limit;
  - committed;
  - settled;
  - returned;
  - open on hands;
  - available to issue;
  - overdue advances count.
- Advances outstanding report:
  - employee;
  - advance;
  - issue / transfer source;
  - settled;
  - returned;
  - transferred;
  - available;
  - due date;
  - days overdue.
- Budget transfer register:
  - transfer number;
  - from budget / to budget;
  - from employee / to employee;
  - amount;
  - transfer type.
- Expense by category:
  - полезно видеть split:
    - out-of-pocket claims;
    - budget-funded claims.

### 10.2. Bank reconciliation

Для полной фичи reconciliation должен поддерживать:

- `BudgetAdvance` как outgoing cash-out документ;
- `BudgetAdvanceReturn` как incoming return документ.

Рекомендация по модели:

- расширить `BankTransactionMatch` связями на:
  - `budget_advance_id?`
  - `budget_advance_return_id?`
- авто-матчинг:
  - outgoing по сумме/дате/reference для advances;
  - incoming по сумме/дате/reference для returns.

### 10.3. Возвраты

Возвраты в банк или M-Pesa - это входящие движения.

Для полной фичи:

- возврат должен фиксироваться и как внутренний документ, и как кандидат для incoming reconciliation;
- unmatched incoming returns должны быть видны отдельно.

### 10.4. Влияние на финансовые отчёты

Это важный момент.

Сейчас `CompensationPayout` участвует в cash-based reporting как employee compensation outflow. Если budget advances пойдут через payout, отчёты будут искажены.

Поэтому:

- `BudgetAdvance` нельзя считать `Employee Compensations`;
- budget-funded claims нельзя вести через обычный payout flow.

Правильная логика:

- в accrual analytics расход признаётся по claim/payment, как и сейчас;
- в cash analytics `Budget Advances` показываются отдельной строкой cash outflow;
- `BudgetAdvanceReturn` уменьшает этот cash outflow или показывается отдельной отрицательной строкой;
- `CompensationPayout` остаётся отдельной строкой employee reimbursements.

---

## 11. Права доступа

### SuperAdmin

- create/update/activate/close/cancel budgets;
- create/issue/close/cancel advances;
- create transfers;
- approve/reject/send-to-edit claims;
- create returns.

### Admin

- create/update budgets и advances;
- create transfers and returns;
- view all budgets/advances/claims;
- без финального approve claims, если текущая политика approval остаётся только за SuperAdmin.

### Accountant

- read-only доступ к budgets, advances, claims, returns, transfers, reports, exports;
- без права создавать advances и без права approve claims.

### User

- видит только свои advances и budgets, где у него есть funding;
- создаёт claims только против своих funded budgets;
- не видит чужие budgets/advances.

---

## 12. Полная целевая версия

Полноценная фича в этом плане включает:

- monthly budgets с period closing;
- несколько advances на сотрудника в одном budget;
- reserve и settle claims через `BudgetClaimAllocation`;
- split одного claim по нескольким advances;
- returns;
- rollover / reassignment / reallocation через `BudgetAdvanceTransfer`;
- overdue control и aging;
- outgoing и incoming reconciliation;
- отдельное отражение в cash reporting и management reporting.

Если нужна закупка, которая должна пройти через склад:

- использовать существующий procurement flow;
- budget advances использовать только для мелких операционных трат.

---

## 13. Пример процесса

Пример:

- создаём budget:
  - `Kitchen supplies / May 2026 / limit 30,000`
- выдаём advances:
  - `5,000` сотруднику Mary
  - `2,000` сотруднику Mary позже в том же месяце
- Mary покупает:
  - milk and tea `1,200`
  - cleaning supplies `800`
- создаёт 2 claims с `funding_source=budget` и `budget_id=Kitchen supplies / May 2026`
- claims проходят approve
- система автоматически закрывает их FIFO из двух advances
- к концу мая остаётся `5,000` open balance
- админ делает rollover `3,000` в июньский budget и принимает return `2,000`
- по майскому budget получаем:
  - direct issues = `7,000`
  - settled = `2,000`
  - returned = `2,000`
  - transferred out = `3,000`
  - open on hands = `0`
- в июньском budget появляется новый advance `3,000` с `source_type=transfer_in`

---

## 14. Порядок внедрения

### Этап 1. Backend models + migrations

- `budgets`
- `budget_advances`
- `budget_advance_returns`
- `budget_advance_transfers`
- `budget_claim_allocations`
- `budget_id` в `expense_claims`
- `budget_id` и `funding_source` в `procurement_payments`

### Этап 2. Claims integration

- добавить выбор funding source;
- валидации по budget и доступному funding;
- reserve/release logic на submit/edit/reject;
- auto-settle claim from advances on approve.

### Этап 3. UI

- budgets list/detail;
- advance detail;
- period closing / rollover actions;
- claims form updates;
- employee-side "My advances".

### Этап 4. Reporting and reconciliation

- budget utilization report;
- outstanding advances report;
- transfer register;
- bank reconciliation support for `BudgetAdvance` and `BudgetAdvanceReturn`.

---

## 15. Рекомендация для проекта

Для этого проекта рекомендованный вариант такой:

- **Budget** - сущность направления расходов;
- **BudgetAdvance** - выдача денег сотруднику;
- **BudgetAdvanceTransfer** - штатный перенос остатка между периодами и/или сотрудниками;
- **ExpenseClaim** - подтверждение фактической траты с привязкой к budget;
- **BudgetClaimAllocation** - reserve и final settlement claims из ранее выданных денег;
- **CompensationPayout** - оставить только для reimbursements.

Это самый чистый и расширяемый вариант:

- не ломает текущий модуль compensations;
- не искажает отчёты и reconciliation;
- даёт прозрачный контроль "у кого деньги на руках";
- поддерживает перенос остатка между месяцами без искажения истории;
- хорошо ложится на будущий переход compensations с `users.id` на `employees.id`.
