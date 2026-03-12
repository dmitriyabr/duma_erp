# Скрипты обслуживания ERP

## seed_demo_data.py

Наполнение базы **реалистичными демо-данными** школьной жизни (Kenya):

- **Пользователи, классы, термы** — сборы по классам/зонам, 25 учеников с именами и опекунами.
- **Счета и платежи** — частично оплаченные/оплаченные/выставленные, аллокации.
- **Склад** — 5 категорий (Uniforms, Stationery, Cleaning, Sports, Catering), **150+ товаров** (форма по размерам, канцтовары, уборка, спорт, питание).
- **Закупки** — **48 заказов** (draft / ordered / received / partially received), **24 GRN** с приходом на склад, **38 платежей** по закупкам.
- **Компенсации** — 5 expense claims (сотрудник платил из своего кармана), 5 payouts и employee balance.

Данные не случайные — эмуляция жизни школы: сотни айтемов, десятки транзакций.

**Требования:** миграции применены (`uv run alembic upgrade head`), БД доступна.

```bash
# Просмотр без записи
uv run python scripts/seed_demo_data.py --dry-run

# Записать в БД
uv run python scripts/seed_demo_data.py --confirm

# Полное наполнение: сначала очистить все данные сида (в т.ч. созданные вручную при тестах), затем наполнить заново
uv run python scripts/seed_demo_data.py --clear --confirm
```

Скрипт идемпотентен: если данные уже есть (например, пользователь `admin@school.demo` или классы), соответствующий блок пропускается. Для полного наполнения с нуля используйте пустую БД после миграций.

**Логины после сида:** `admin@school.demo` / `manager@school.demo` / `teacher@school.demo` / `accountant@school.demo` — пароль `demo123`.

---

## audit_financial_integrity.py

Read-only аудит финансовой целостности по студентам.

Проверяет:

- `Student.cached_credit_balance` против `SUM(completed payments) - SUM(allocations)`
- долг по `invoice.amount_due` против суммы `invoice_lines.remaining_amount`
- header поля invoice (`subtotal`, `discount_total`, `total`, `paid_total`, `amount_due`) против строк и allocations
- формулы строк (`net_amount`, `remaining_amount`)
- битые allocations: не тот student, не тот invoice, не та invoice line

### Локальный запуск

```bash
python3 scripts/audit_financial_integrity.py

# Только один ученик
python3 scripts/audit_financial_integrity.py --student-number STU-2026-000001

# JSON-отчет + ненулевой exit code, если найдены проблемы
python3 scripts/audit_financial_integrity.py --json --fail-on-errors
```

### Запуск на Railway

```bash
# Сводка по всем студентам
railway run python3 scripts/audit_financial_integrity.py

# Только один ученик
railway run python3 scripts/audit_financial_integrity.py --student-number STU-2026-000001

# Для сохранения JSON-лога в CI / shell
railway run python3 scripts/audit_financial_integrity.py --json --fail-on-errors
```

Скрипт **ничего не меняет в базе**. Он только читает данные и печатает найденные расхождения.

---

## repair_financial_integrity.py

Безопасный пересчет битых финансовых агрегатов у выбранных студентов.

По умолчанию работает в `dry-run` режиме и только показывает, что будет исправлено:

- `InvoiceLine.net_amount`, `paid_amount`, `remaining_amount`
- `Invoice.subtotal`, `discount_total`, `total`, `paid_total`, `amount_due`, `status`
- `Student.cached_credit_balance`

Скрипт **не трогает allocations и payments**. Он пересчитывает invoice/line/student aggregates из уже существующих discounts и allocations.

### Локальный запуск

```bash
# Dry-run по конкретному ученику
python3 scripts/repair_financial_integrity.py --student-number STU-2026-000014

# Реальное применение
python3 scripts/repair_financial_integrity.py --student-id 14 --student-id 15 --apply
```

### Запуск на Railway

```bash
# Сначала preview
railway run python3 scripts/repair_financial_integrity.py --student-number STU-2026-000014
railway run python3 scripts/repair_financial_integrity.py --student-number STU-2026-000015

# Потом реальное применение
railway run python3 scripts/repair_financial_integrity.py --student-number STU-2026-000014 --student-number STU-2026-000015 --apply

# Повторный аудит после фикса
railway run python3 scripts/audit_financial_integrity.py --student-number STU-2026-000014 --student-number STU-2026-000015
```

Если у инвойса есть небезопасные расхождения, скрипт пометит его как `SKIPPED` и не будет применять автоматический фикс.

---

## reset_invoices.py

Скрипт для одноразового удаления всех счетов (invoices) из базы данных с сохранением платежей (payments).

### 🚀 TL;DR - Быстрый старт

**Самый простой способ (с автоматическими проверками):**
```bash
# Запусти wrapper скрипт - он все сделает за тебя
./scripts/reset_invoices_railway.sh
```

**Или вручную:**
```bash
# 1. Создай backup в Railway Dashboard (Database → Backups → Create Backup)

# 2. Подключись к проекту
railway link

# 3. Сначала dry-run
railway run python3 scripts/reset_invoices.py --dry-run

# 4. Если все ок - выполни
railway run python3 scripts/reset_invoices.py --confirm
# Введи "DELETE ALL INVOICES" когда попросит

# 5. Готово! Все счета удалены, платежи на балансе студентов
```

### Что делает скрипт

**Удаляет:**
- ❌ Все Invoices и InvoiceLines
- ❌ Все Reservations и ReservationItems
- ❌ Все CreditAllocations

**НЕ удаляет:**
- ✅ Payments (остаются как баланс студентов)
- ✅ Students, Users, Terms и другие данные
- ✅ AuditLogs (история операций)

### Использование на Railway

#### Вариант 1: Запуск через Railway CLI (рекомендуется)

```bash
# 1. Подключись к проекту (если еще не подключен)
railway link

# 2. Сначала dry-run для просмотра
railway run python3 scripts/reset_invoices.py --dry-run

# 3. Если все ОК - реальное выполнение
railway run python3 scripts/reset_invoices.py --confirm
```

#### Вариант 2: Запуск локально с подключением к проду

```bash
# 1. Получи DATABASE_URL из Railway
railway variables

# 2. Экспортируй DATABASE_URL в текущую сессию
export DATABASE_URL="postgresql+asyncpg://..."

# 3. Запусти скрипт локально
python3 scripts/reset_invoices.py --dry-run
python3 scripts/reset_invoices.py --confirm
```

#### Вариант 3: Через Railway Shell (интерактивно)

```bash
# Открой shell на Railway
railway shell

# Внутри shell запусти скрипт
python3 scripts/reset_invoices.py --dry-run
python3 scripts/reset_invoices.py --confirm
```

### ⚠️ ВАЖНО

1. **Сделайте backup базы данных ПЕРЕД запуском!**

   **Через Railway Dashboard (рекомендуется):**
   - Зайди в Railway Dashboard → твой проект → Database (Postgres)
   - Перейди на вкладку **Backups**
   - Нажми **Create Backup** - Railway создаст snapshot
   - Можно скачать backup через **Download** если нужно

   **Через Railway CLI (альтернатива):**
   ```bash
   # Подключись к Railway проекту
   railway link

   # Создай backup через Railway
   railway run pg_dump $DATABASE_URL -F c -f backup_before_reset_$(date +%Y%m%d_%H%M%S).dump
   ```

2. **Убедитесь, что файл .env настроен правильно** - скрипт использует `DATABASE_URL` из .env

3. **Это необратимая операция** - после удаления счета нельзя восстановить

### Пример вывода

```
======================================================================
СКРИПТ УДАЛЕНИЯ СЧЕТОВ (RESET INVOICES)
======================================================================

🌍 Окружение: production
🗄️  База данных: localhost:5432/school_erp
🔧 Режим: РЕАЛЬНОЕ ВЫПОЛНЕНИЕ

📊 Текущее состояние базы данных:
  - invoices: 45 записей
  - invoice_lines: 123 записей
  - credit_allocations: 89 записей
  - reservations: 12 записей
  - reservation_items: 34 записей

⚠️  ВНИМАНИЕ: Начинается удаление данных...

1️⃣  Удаление Reservations...
   ✓ Удалено: 12 reservations

2️⃣  Удаление CreditAllocations...
   ✓ Удалено: 89 credit allocations

3️⃣  Удаление Invoices...
   ✓ Удалено: 45 invoices

======================================================================
✅ УСПЕШНО УДАЛЕНО
======================================================================

🎉 Все счета успешно удалены!
💰 Все payments сохранены и теперь являются балансом студентов
```

### Восстановление из backup (если что-то пошло не так)

#### Через Railway Dashboard
1. Зайди в Railway Dashboard → Database → Backups
2. Найди нужный backup (созданный до запуска скрипта)
3. Нажми **Restore** - Railway автоматически восстановит БД

#### Через Railway CLI (если скачал dump локально)
```bash
# Восстановление из локального dump файла
railway run pg_restore -d $DATABASE_URL -c -v backup_before_reset.dump

# Или можно через psql
railway run psql $DATABASE_URL < backup_before_reset.sql
```

#### Важно
- Railway автоматически создает daily backups
- Backups хранятся 7-30 дней в зависимости от плана
- Manual backups можно создавать в любое время

---

## backfill_reservation_issued_from_issuances.py

Исправляет ситуацию, когда **issuance был отменён (cancelled)**, склад вернулся, но
в `reservation_items.quantity_issued` цифры **не откатились** (старый баг).

Скрипт **идемпотентный и безопасный**: он не “вычитает”, а **пересчитывает**
`quantity_issued` по реально **COMPLETED** выдачам (cancelled не учитывает),
и пересчитывает `Reservation.status` (кроме `cancelled`).

### Использование

```bash
# Сначала dry-run (рекомендуется)
python3 scripts/backfill_reservation_issued_from_issuances.py --dry-run --issuance-id 123

# Применить (попросит подтверждение фразой)
python3 scripts/backfill_reservation_issued_from_issuances.py --confirm --issuance-id 123

# Можно ограничить по reservation_id
python3 scripts/backfill_reservation_issued_from_issuances.py --dry-run --reservation-id 456
```

### Запуск на Railway (wrapper)

```bash
./scripts/backfill_reservation_issued_from_issuances_railway.sh --issuance-id 123
```
