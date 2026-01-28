# Загрузка файлов подтверждения платежей

Функция добавлена в ветке `feature/payment-confirmation-uploads`.

## Суть

Там, где есть текстовое поле для референса платежа (M-Pesa, банк и т.п.), можно вместо текста загрузить файл подтверждения. **Обязательно одно из двух:** либо текст (reference), либо файл.

- **Студенческие платежи (Payments):** `reference` или `confirmation_attachment_id`.
- **Платежи закупок (Procurement):** `proof_text` или `proof_attachment_id`.
- **Выплаты сотрудникам (Payouts):** `proof_text` или `proof_attachment_id`.

## Допустимые файлы

- Изображения: JPEG, PNG, GIF, WebP.
- Документы: PDF.
- Макс. размер: 10 MB.

## Backend

- **Модель:** `Attachment` (file_name, content_type, storage_path, file_size, created_by_id).
- **Хранение:** dev — папка `uploads/` (config `STORAGE_PATH`); prod — S3/R2 (см. `docs/CLOUDFLARE_R2.md`).
- **API:**
  - `POST /api/v1/attachments` — загрузка файла, ответ: `{ id, file_name, content_type, file_size, created_at }`.
  - `GET /api/v1/attachments/{id}` — метаданные.
  - `GET /api/v1/attachments/{id}/download` — скачать файл (для просмотра подтверждения).

## Frontend

- **Студенческие платежи (PaymentsTab):** поле Reference + кнопка «Upload confirmation (image/PDF)»; в детали платежа — кнопка «View confirmation file».
- **Платежи закупок:** поле Reference/proof (текст) + загрузка файла; на странице детали платежа — «View confirmation file».
- **Выплаты:** то же; на странице детали выплаты — «View confirmation file».

Просмотр: по кнопке «View confirmation file» файл запрашивается с авторизацией и открывается в новой вкладке (картинка или PDF).

## Миграция

- `018_attachments_and_payment_confirmation.py`: таблица `attachments`, в `payments` добавлено поле `confirmation_attachment_id` (FK на attachments). В procurement и compensations поля `proof_attachment_id` уже были.

## Багфиксы в той же ветке

- **Employee Balances:** при запросе баланса сотрудника баланс всегда пересчитывается по одобренным claims и выплатам (раньше возвращался кэш без учёта новых одобрений).
- **Invoice issue:** при выставлении счёта (POST `.../invoices/{id}/issue`) автоматически вызывается авто-аллокация баланса ученика — положительный баланс списывается на новый и другие неоплаченные счета.
- **Procurement form:** убрана ранняя проверка «Proof is required (proof text)» — достаточно либо текста, либо загруженного файла.
