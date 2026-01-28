# Массовая загрузка стока через CSV

## Обзор

- **Ветка:** `feature/bulk-stock-csv`
- **Место в UI:** страница Inventory count: секция «Bulk upload from CSV» + кнопка **«Download current stock»** (выгрузка текущего склада в CSV — по ней удобно редактировать и заливать обратно).

## Режимы загрузки

1. **Затереть старый склад (Overwrite)**  
   Обнулить только **quantity_on_hand** по всем product (reserved не трогаем — это производная от резерваций/выдач). Затем применить CSV. В результате ненулевой остаток только у позиций из файла.

2. **Только обновить (Update)**  
   Менять остатки только у позиций, которые есть в CSV. Позиции, которых нет в файле, не трогать. Для каждой строки CSV: установить quantity_on_hand = значение из CSV (через adjustment).

## CSV

- **Reserved в CSV не участвует:** не выводим, не обновляем. Только сток (quantity_on_hand).

### Формат (загрузка)

| Колонка      | Обязательность | Описание |
|-------------|----------------|----------|
| category    | да             | Название категории (если нет — создать) |
| item_name   | да             | Название позиции (если нет — создать в этой категории с автоСКУ) |
| quantity    | да             | Целое ≥ 0, остаток на складе (quantity_on_hand) |
| unit_cost   | нет            | Цена за единицу (для новых поступлений) |
| sku         | нет            | Если указан и есть в системе — ищем по SKU; иначе по (category, item_name) |

- Кодировка: UTF-8, разделитель: запятая, первая строка — заголовки.

### Создание позиций, которых ещё нет

- По строке CSV: категория по имени (get or create), позиция по (category_id, item_name) или по sku.
- Если позиции нет: создать Item (product), SKU сгенерировать из префикса категории (как в Items: `_build_sku_prefix` + `_next_sku_sequence`). Затем создать Stock и установить остаток (receive с quantity и unit_cost из CSV, или сразу установить quantity через adjustment).
- Логика: один метод в backend «get_or_create_product_item(category_name, item_name, sku?)» → (item, created). Затем «set_stock(item_id, quantity, unit_cost?)» с учётом режима (overwrite/update).

## Backend

- **POST /inventory/bulk-upload**  
  - Тело: `multipart/form-data`: файл `file` (CSV), поле `mode`: `overwrite` | `update`.
  - Права: ADMIN (как inventory count).
  - Логика:
    1. Парсинг CSV, валидация заголовков и строк (category, item_name, quantity; unit_cost, sku опционально).
    2. Если `mode == overwrite`: обнулить **только quantity_on_hand** по всем product (quantity_reserved не трогаем).
    3. Для каждой строки: get_or_create_item(category, item_name, sku?) → item; установить quantity_on_hand через receive или adjustment. Если unit_cost указан и новая позиция — receive; иначе adjustment до target quantity.
  - Ответ: обработано строк, создано позиций, ошибки по строкам (при необходимости).

- **GET /inventory/bulk-upload/export** (вместо «шаблона»)  
  - Ответ: CSV с **текущим складом** — строки по всем product с остатком (category, item_name, sku, quantity, unit_cost/average_cost). Так пользователь скачивает актуальное состояние, правит и заливает обратно, не теряя данные.

### Сервисы

- **InventoryService** (или отдельный BulkStockService):
  - `bulk_upload_from_csv(file, mode, user_id)`: парсинг, валидация, overwrite/update, создание движений и аудит.
- **ItemService** (расширение):
  - `get_or_create_category_by_name(name)` → Category.
  - `get_or_create_product_item(category_name, item_name, sku=None, created_by_id)` → (Item, created: bool). Если sku передан и найден — вернуть; иначе искать по (category_id, name); если нет — создать с автоСКУ (нужен метод генерации SKU для Item по категории, по аналогии с Kit).

### Важно

- Stock создаётся при первом receive/adjust (_get_or_create_stock). Новая позиция: создать Item → receive или adjustment.
- При overwrite: обнуляем **только quantity_on_hand**. quantity_reserved не трогаем (производная от резерваций/выдач).

## Frontend

- Страница **Inventory count**:
  - Секция «Bulk upload from CSV»:
    - Кнопка **«Download current stock»** → GET export, скачать CSV текущего склада (редактируешь и заливаешь — так проще не ошибиться).
    - Поле выбора файла (CSV), радио: **«Overwrite warehouse»** / **«Update only»**, кнопка **«Upload»**.
  - Результат: обработано строк, создано позиций, ошибки по строкам (если есть).

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
