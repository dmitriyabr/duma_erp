# Массовая загрузка стока через CSV

## Обзор

- **Ветка:** `feature/bulk-stock-csv`
- **Место в UI:** страница Inventory count (рядом с ручной инвентаризацией): секция «Bulk upload from CSV» + кнопка «Download template».

## Режимы загрузки

1. **Затереть старый склад (Overwrite)**  
   Сначала обнулить остатки по всем товарам (product), затем применить CSV. В результате ненулевой остаток только у позиций из файла.

2. **Только обновить (Update)**  
   Менять остатки только у позиций, которые есть в CSV. Позиции, которых нет в файле, не трогать. Для каждой строки CSV: установить остаток = значение из CSV (через adjustment).

## CSV

### Формат (предлагаемый)

| Колонка      | Обязательность | Описание |
|-------------|----------------|----------|
| category    | да             | Название категории (если нет — создать, например «Uncategorized» или ошибка) |
| item_name   | да             | Название позиции (если нет в системе — создать в этой категории с автоСКУ) |
| quantity    | да             | Целое ≥ 0, остаток на складе |
| unit_cost   | нет            | Цена за единицу (для новых поступлений; при создании позиции и при receive) |

- Кодировка: UTF-8.
- Разделитель: запятая. Первая строка — заголовки.
- Вариант: опциональная колонка `sku` — если указана и позиция с таким SKU есть, ищем по SKU; иначе ищем/создаём по (category, item_name).

### Создание позиций, которых ещё нет

- По строке CSV: категория по имени (get or create), позиция по (category_id, item_name) или по sku.
- Если позиции нет: создать Item (product), SKU сгенерировать из префикса категории (как в Items: `_build_sku_prefix` + `_next_sku_sequence`). Затем создать Stock и установить остаток (receive с quantity и unit_cost из CSV, или сразу установить quantity через adjustment).
- Логика: один метод в backend «get_or_create_product_item(category_name, item_name, sku?)» → (item, created). Затем «set_stock(item_id, quantity, unit_cost?)» с учётом режима (overwrite/update).

## Backend

- **POST /inventory/bulk-upload**  
  - Тело: `multipart/form-data`: файл `file` (CSV), поле `mode`: `overwrite` | `update`.
  - Права: ADMIN (как inventory count).
  - Логика:
    1. Парсинг CSV, валидация заголовков и строк (category, item_name, quantity; unit_cost опционально).
    2. Если `mode == overwrite`: обнулить quantity_on_hand (и quantity_reserved?) по всем product items (через adjustment или прямой update + движения в аудит).
    3. Для каждой строки: get_or_create_item(category, item_name, sku?) → item; затем установить остаток: при overwrite — просто set quantity (т.к. уже обнулили); при update — adjustment до target quantity. Если указан unit_cost и это новая позиция или «первое поступление», можно записать через receive; иначе — adjustment.
  - Ответ: количество обработанных строк, созданных позиций, ошибки по строкам (если делать пошаговый отчёт).

- **GET /inventory/bulk-upload/template**  
  - Ответ: CSV-файл с одной строкой заголовков: `category,item_name,quantity,unit_cost` (и опционально `sku`).
  - Либо отдача статического файла, либо генерация на лету.

### Сервисы

- **InventoryService** (или отдельный BulkStockService):
  - `bulk_upload_from_csv(file, mode, user_id)`: парсинг, валидация, overwrite/update, создание движений и аудит.
- **ItemService** (расширение):
  - `get_or_create_category_by_name(name)` → Category.
  - `get_or_create_product_item(category_name, item_name, sku=None, created_by_id)` → (Item, created: bool). Если sku передан и найден — вернуть; иначе искать по (category_id, name); если нет — создать с автоСКУ (нужен метод генерации SKU для Item по категории, по аналогии с Kit).

### Важно

- Stock создаётся при первом receive/adjust (уже есть _get_or_create_stock). Для новой позиции: создать Item → вызвать receive или adjustment.
- При overwrite: обнуление только quantity_on_hand; quantity_reserved трогать только если бизнес разрешает (иначе оставить как есть и запретить overwrite при reserved > 0 или обнулить и reserved).

## Frontend

- Страница **Inventory count**:
  - Секция «Bulk upload from CSV»:
    - Кнопка **«Download template»** → GET template, сохранить файл (или открыть в новой вкладке).
    - Поле выбора файла (CSV).
    - Радио: **«Overwrite warehouse»** / **«Update only»**.
    - Кнопка **«Upload»** → POST bulk-upload с file и mode.
  - Показать результат: «Processed N rows, created M items» и при необходимости список ошибок по строкам.

## CDN / хранилище файлов

- **Прод:** Cloudflare S3 (R2 или S3-совместимый API).
- **Дев:** поднять локальное хранилище:
  - **Вариант 1:** MinIO в `docker-compose` (S3-совместимый), один бакет для dev.
  - **Вариант 2:** локальная папка `./uploads` (или `STORAGE_PATH`), без S3 — для загрузок/вложений в dev.

Для самой массовой загрузки стока CDN не обязателен: файл читается в память и парсится, не сохраняется. CDN понадобится для будущих вложений (Фаза 10).

**Dev: MinIO в docker-compose** (профиль `storage`):
```bash
docker-compose --profile storage up -d
```
- API: http://localhost:9000
- Console: http://localhost:9001 (логин minio_admin / minio_password)
- Создать бакет вручную или через приложение. В .env для dev: `S3_ENDPOINT_URL=http://localhost:9000`, `S3_ACCESS_KEY=minio_admin`, `S3_SECRET_KEY=minio_password`, `S3_BUCKET=...`.
