# Issue stock — форма выдачи комплектом

## Обзор

- **Ветка:** `feature/bulk-issue-stock`
- **Место в UI:** страница **Stock** — кнопка **«Issue»** сверху (не у каждого айтема). Открывается отдельная страница формы выдачи, по аналогии с закупкой (Purchase Order form).

## Поведение

1. На странице **Stock** сверху кнопка **«Issue»** (рядом с «New item»). Кнопки **Issue** у строк таблицы убраны.
2. По клику переход на **/inventory/issue** — страница формы выдачи.
3. На форме:
   - **Получатель:** Student / Employee / Other (как раньше в диалоге). Для Student/Employee — выбор из списка, для Other — ввод имени.
   - **Заметки** (опционально).
   - **Таблица строк:** Item (выбор из product items), Quantity. Кнопки «Add line» и удаление строки.
4. Отправка формы → **POST /inventory/issuances** с телом `{ recipient_type, recipient_id?, recipient_name, items: [{ item_id, quantity }], notes? }`. Один issuance на весь комплект.
5. После успешного создания — редирект на **/inventory/issuances** (список выдач).

## Backend

Используется существующий API:

- **POST /inventory/issuances** — создание internal issuance (recipient_type, recipient_id?, recipient_name, items[], notes). Уже поддерживает несколько строк (items). Роль: Admin.

Дополнительных эндпоинтов не требуется.

## Frontend

- **StockPage:** кнопка «Issue» сверху (`navigate('/inventory/issue')`), убраны кнопка «Issue» в строке таблицы и диалог Issue.
- **IssueFormPage** (`/inventory/issue`): форма получателя (Student/Employee/Other) + таблица линий (item, quantity), Add line, Submit → POST /inventory/issuances, затем redirect на /inventory/issuances.
- **routes.tsx:** добавлен маршрут `inventory/issue` → `IssueFormPage`.
