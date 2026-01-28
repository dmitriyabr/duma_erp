# Подключение Cloudflare R2 для прода

R2 — S3-совместимое хранилище Cloudflare (для будущих вложений, Фаза 10). Для bulk CSV не используется: файл парсится в память и не сохраняется.

## 1. Включить R2 в Cloudflare

1. Зайди в [Cloudflare Dashboard](https://dash.cloudflare.com) → выбери аккаунт.
2. В левом меню: **R2 Object Storage**.
3. Если R2 ещё не включён — нажми **Purchase R2** (есть бесплатный лимит: 10 GB/мес хранения, 1 млн операций класса A в месяц).

## 2. Создать бакет

1. **R2** → **Overview** → **Create bucket**.
2. Имя бакета, например: `school-erp-uploads` (или `school-erp-prod`).
3. Location: **Automatic** (или выбери регион).
4. **Create bucket**.

## 3. Получить S3-совместимые ключи (API Token)

R2 даёт доступ по S3 API. Нужны Access Key ID и Secret Access Key.

1. В разделе **R2** нажми **Manage R2 API Tokens** (или **Overview** → справа **Manage API Tokens**).
2. **Create API token**.
3. Имя токена, например: `school-erp-prod`.
4. Permissions: **Object Read & Write** (или **Admin Read & Write**, если нужны создание/удаление бакетов).
5. Специфичный бакет: выбери созданный бакет (или «Apply to all buckets» для одного токена на все бакеты).
6. **Create API Token**.
7. **Скопируй и сохрани**:
   - **Access Key ID**
   - **Secret Access Key**  
   (Secret показывается один раз.)

## 4. Узнать Account ID

- В **R2** → **Overview** справа указан **Account ID**.
- Или: **Any website** → выбери домен → в правой колонке **Account ID**.

## 5. Переменные окружения для приложения (прод)

Когда в приложении появится код работы с S3/R2, в Railway (или другом хосте) задай:

```bash
# Cloudflare R2 (S3-совместимый endpoint)
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_ACCESS_KEY=<Access Key ID из шага 3>
S3_SECRET_KEY=<Secret Access Key из шага 3>
S3_BUCKET=school-erp-uploads
S3_REGION=auto
```

- **Account ID** подставь из шага 4.
- Для европейского endpoint: `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`.

В коде бэкенда при использовании boto3/aioboto3 или другого S3-клиента указывай этот endpoint и `region_name=auto` (R2 использует регион `auto`).

## 6. Публичный доступ к файлам (если понадобится)

По умолчанию объекты в R2 приватные. Чтобы раздавать файлы по URL:

1. **R2** → твой бакет → **Settings** → **Public access** → включи **Allow Access**.
2. Либо настрой **Custom Domains** для бакета (привязать домен Cloudflare и раздавать по нему).

Приложение уже поддерживает R2: если заданы переменные окружения `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` (и опционально `S3_REGION=auto`), вложения (подтверждения платежей, proof для procurement/payouts) сохраняются и отдаются из R2; иначе используется локальная папка `STORAGE_PATH`.
