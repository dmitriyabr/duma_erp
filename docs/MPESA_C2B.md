# M-Pesa C2B (Paybill) → Auto top-up student balance

## Что реализовано

- Публичные webhook-и M-Pesa C2B (Paybill):
  - `POST /api/v1/mpesa/c2b/validation/<MPESA_WEBHOOK_TOKEN>`
  - `POST /api/v1/mpesa/c2b/confirmation/<MPESA_WEBHOOK_TOKEN>`
- `BillRefNumber` (account number), который вводит родитель, сопоставляется со студентом по Admission#:
  - полный формат: `STU-YYYY-NNNNNN`
  - короткий формат (как в UI): `YYNNN...` (например `26123` → `STU-2026-000123`)
- На `confirmation` автоматически создаётся платёж (`Payment`, method=`mpesa`, reference=`TransID`) и проводится (`completed`), после чего запускается существующий auto-allocation на инвойсы.
- Любые входящие события сохраняются в `mpesa_c2b_events` для аудита и идемпотентности.
- Если студент не найден — событие помечается как `unmatched` (платёж не создаётся).

## Настройка окружения

В `.env`:

- `MPESA_WEBHOOK_TOKEN`: секретный токен для URL
- `MPESA_SYSTEM_USER_ID`: user id, под которым будут создаваться платежи/аллокации

Пример см. в `.env.example`.

## Настройка M-Pesa (Daraja)

При регистрации C2B URL (ValidationURL/ConfirmationURL) укажите:

- ValidationURL: `https://<your-domain>/api/v1/mpesa/c2b/validation/<MPESA_WEBHOOK_TOKEN>`
- ConfirmationURL: `https://<your-domain>/api/v1/mpesa/c2b/confirmation/<MPESA_WEBHOOK_TOKEN>`

Где `<your-domain>` — домен вашего backend.

## Операционные сценарии

### 1) Родитель оплатил с корректным Admission#

- M-Pesa вызывает `confirmation`
- ERP создаёт `Payment` (completed) → баланс ученика растёт → auto-allocation закрывает/частично закрывает инвойсы

### 2) Родитель ошибся в Admission#

- ERP сохраняет событие как `unmatched`
- Админ может найти событие и вручную привязать к студенту:
  - `GET /api/v1/mpesa/c2b/events/unmatched`
  - `POST /api/v1/mpesa/c2b/events/{event_id}/link` body: `{ "student_id": <id> }`

## Безопасность

- Webhook-и доступны только по URL с токеном (`MPESA_WEBHOOK_TOKEN`).
- (Опционально) можно настроить `school_settings.mpesa_business_number` и проверять `BusinessShortCode` в callback.

