# Массовая загрузка линий Purchase Order из CSV

## Обзор

- **Место в UI:** страница **создания** PO (New purchase order). Поставщик, цель платежа, даты и т.д. заполняются в форме; CSV используется только для **линий заказа** (айтемы, количество, цена).
- Пользователь скачивает шаблон, заполняет количество и цену по нужным айтемам, загружает CSV — распознанные линии подставляются в форму, их можно отредактировать и сохранить PO.

## Формат CSV (только линии)

- Кодировка: UTF-8, разделитель: запятая, первая строка — заголовки.

### Колонки

| Колонка           | Обязательность | Описание |
|-------------------|----------------|----------|
| sku               | нет*           | SKU позиции в системе; если указан и найден — линия привязывается к item_id |
| item_name         | да*             | Название/описание строки (если sku указан — можно пусто, подставится имя айтема) |
| quantity_expected | да             | Целое > 0, ожидаемое количество |
| unit_price        | да             | Цена за единицу (≥ 0) |

\* Минимум один из sku или item_name нужен; при указанном sku item_name может быть пустым.

## Шаблон (GET template)

- **GET /procurement/purchase-orders/bulk-upload/template** возвращает CSV:
  1. Строка заголовков: `sku`, `item_name`, `quantity_expected`, `unit_price`.
  2. **Одна строка-пример** с заполненными полями (например EXAMPLE-001, Example product, 1, 0.00).
  3. **По одной строке на каждый продукт** из каталога (product items): заполнены только `sku` и `item_name`; `quantity_expected` и `unit_price` — пустые. Пользователь заполняет их сам, чтобы не ошибиться по названию (в шаблоне уже точные SKU и названия из системы).

## Backend

- **GET /procurement/purchase-orders/bulk-upload/template**
  - Ответ: CSV с заголовками, одной строкой-примером и строками по всем активным product items (sku + name заполнены, quantity и unit_price пустые). Роль: Admin.

- **POST /procurement/purchase-orders/bulk-upload/parse-lines**
  - Тело: `multipart/form-data`, файл `file` (CSV).
  - Права: ADMIN.
  - Логика: парсинг CSV (колонки sku, item_name, quantity_expected, unit_price), resolve item по sku при наличии; **PO не создаётся**.
  - Ответ: `{ lines: [{ item_id?, description, quantity_expected, unit_price }], errors: [{ row, message }] }`. Для использования на странице создания PO: подставить lines в форму, отобразить errors по строкам.

### Сервисы

- **PurchaseOrderService.parse_po_lines_from_csv(content)** → dict с `lines` и `errors`. Resolve item по sku через ItemService.get_item_by_sku.

## Frontend

- Страница **New purchase order** (форма создания PO):
  - Блок «Order lines»: кнопки **«Download template»** и **«Upload CSV»** (только при создании, не при редактировании).
  - «Download template» → GET template, скачивается `po_lines_template.csv`.
  - «Upload CSV» → выбор файла, POST parse-lines → результат (lines) подставляется в таблицу линий формы; ошибки по строкам показываются над таблицей. Пользователь может отредактировать линии и нажать «Save order».
