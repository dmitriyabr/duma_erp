# План HR-фичи: справочник сотрудников и выгрузки для бухгалтерии

## 1. Цели фичи

- **Хранить данные сотрудников** (персональные, контактные, банк, налоги, документы) в одном месте.
- **Связь с User (опционально):** сотрудник может иметь учётную запись в системе (для компенсаций, заявок и т.д.) или не иметь — только как HR-запись.
- **Заводить новых сотрудников:** через форму (внутри ERP или через внешнюю Google Form с последующим импортом).
- **Выгрузки для бухгалтерии:** экспорт нужных полей (банк, KRA PIN, NSSF, NHIF, оклад/роль и т.д.) в CSV/Excel для передачи в учётную систему или расчёт зарплаты.

---

## 2. Текущий процесс (как есть)

Новые сотрудники заполняют **Google Form**. Результат — таблица в Google Sheets, экспортируемая в CSV. Пример структуры (по файлу `EmployersForms - Form Responses 1.csv`):

| Группа полей | Поля в форме |
|--------------|--------------|
| **Время** | Timestamp |
| **ФИО** | Surname / Last Name, First Name, Second Name |
| **Персональные** | Gender, Marital Status, Nationality, Date of Birth |
| **Контакт** | Mobile Phone Number, Email Address |
| **Адрес** | Physical Address, Town, Postal Address, Postal Code |
| **Работа** | Job Title / Role, Employee Start Date |
| **Документы** | National ID Number, KRA PIN Number, NSSF Number, NHIF / SHA Number |
| **Банк** | Bank Name, Bank Branch Name, Bank Code, Branch Code, Account Number, Account Holder Name |
| **Ближайший родственник** | Next of Kin – Full Name, Relationship to Employee, Next of Kin – Mobile Phone Number, Next of Kin – Physical Address |
| **Льготы** | Do you have Mortgage Relief?, Upload Mortgage Relief Certificate, Do you have Insurance Reliefs?, Upload Insurance Relief Certificates |
| **Вложения** | Upload National ID, Upload KRA PIN Certificate, Upload NSSF Confirmation, Upload NHIF / SHA Confirmation, Upload Bank Confirmation / Cheque / Statement |
| **Подтверждение** | I confirm that the information provided above is true and accurate |

Особенности текущих данных:
- Часть полей — текст (адрес, город, банк в свободной форме).
- Вложения — ссылки на Google Drive.
- Есть дубли (один человек может отправить форму дважды — например, Chitsava/Elius в CSV дважды).
- Нет единого идентификатора сотрудника в системе; компенсации сейчас привязаны к **User** (users.id).

---

## 3. Связь User ↔ Сотрудник

В системе сейчас:
- **User** — учётная запись (логин, роль, full_name, phone). Используется для входа и для компенсаций: `ExpenseClaim.employee_id`, `CompensationPayout.employee_id`, `EmployeeBalance.employee_id` ссылаются на `users.id`.
- Отдельной сущности «Сотрудник» с полными HR-данными нет.

Требование: **User может быть привязан к сотруднику, а может и не быть** (например, охранник без доступа в систему — только HR-запись и выплаты).

Отсюда два варианта архитектуры.

### Вариант A: Employee как расширенный профиль User (минимальные изменения)

- Вводится таблица **Employee** с полным набором HR-полей и полем **user_id** (FK на users, unique, nullable).
- **Compensations остаются как есть:** `employee_id` = user_id (в заявках/выплатах по-прежнему user_id).
- Смысл: «Сотрудник» в контексте компенсаций = User; расширенные данные для бухгалтерии и отчётности хранятся в Employee и подтягиваются по user_id.
- Ограничение: выплаты/заявки только тем, у кого есть User. Если нужно вести выплаты сотруднику без учётки — такой сценарий не покрывается без доработок (например, «виртуальный» User без логина или смена FK на Employee).

### Вариант B: Employee как основная сущность, User опционален (рекомендуется)

- Таблица **Employee** — основная сущность для «сотрудника» (все HR-данные, нумерация EMP-YYYY-NNNNNN и т.д.).
- Поле **user_id** в Employee (FK на users, unique, nullable): при наличии — этот сотрудник может входить в систему.
- **ExpenseClaim, CompensationPayout, EmployeeBalance** переводим на ссылку на **employees.id** (а не users.id). Тогда:
  - сотрудник с заявками/выплатами может быть без User (только запись в Employee);
  - сотрудник с User — просто у Employee заполнен user_id.
- Миграция: для каждого существующего User, у которого есть claims/payouts/balance, создаётся запись Employee (user_id = user.id, копируем full_name, email, phone из User), затем все FK в compensations переключаются на employees.id.

**Рекомендация:** вариант B — одна сущность «сотрудник» (Employee), единая точка правды для HR и выплат; учётка (User) — опциональная привязка.

---

## 4. Варианты процесса приёма данных (форма vs ERP)

### Вариант 1: Оставить Google Form + импорт CSV в ERP

**Плюсы:**
- Сотрудники уже привыкли к форме; не нужно учить новому интерфейсу.
- Можно собирать ответы без доступа в ERP (например, до выдачи учётки).
- Маппинг колонок CSV → поля Employee один раз описать и использовать при импорте.

**Минусы:**
- Ручной шаг: выгрузка из Sheets → загрузка в ERP.
- Дубли и опечатки нужно разбирать вручную (или править после импорта в ERP).
- Ссылки на Google Drive остаются внешними; при желании «всё в ERP» их придётся дублировать во вложения (Attachment) при импорте или оставить как текст.

**Реализация:**  
В ERP: экран «Импорт сотрудников из CSV» (формат как у выгрузки Google Form). Парсинг строк, маппинг колонок, создание/обновление записей Employee (и при необходимости создание User + привязка). Валидация: обязательные поля, дубли по National ID / email (на усмотрение продукта).

---

### Вариант 2: Только форма в ERP (без Google Form)

**Плюсы:**
- Все данные сразу в одной системе; нет ручного переноса.
- Единый контроль полей и валидации; можно сразу загружать файлы в Attachment (R2/S3).
- Меньше зависимостей от Google.

**Минусы:**
- Нужно дать сотруднику ссылку на форму/страницу (гостевая или по одноразовой ссылке) или ввод данных делает HR/админ со слов сотрудника.
- Изменение привычного процесса для тех, кто уже заполнял Google Form.

**Реализация:**  
В ERP: форма «Новый сотрудник» (многошаговая или одна длинная страница), поля как в разделе 5 ниже. Права: создание/редактирование Employee — Admin/SuperAdmin; при необходимости отдельная «публичная» форма (без входа) с капчей и сохранением в черновик/на модерацию.

---

### Вариант 3: Гибрид (рекомендуется на старте)

- **Google Form остаётся** каналом сбора первичных данных (как сейчас).
- В ERP добавляется:
  - **Импорт из CSV** (выгрузка из Sheets в формате, совместимом с формой).
  - **Ручное создание/редактирование** Employee в ERP (для правок, для сотрудников, заведённых без формы).
- В перспективе форму можно заменить на форму в ERP (вариант 2), не меняя структуру Employee.

Так сохраняется привычный процесс и одновременно появляется единое хранилище и выгрузки для бухгалтерии.

---

## 5. Модель данных Employee (предложение)

Ниже — поля, которых достаточно, чтобы покрыть форму и выгрузки для бухгалтерии. Типы и обязательность уточняются при реализации.

| Поле | Тип | Описание |
|------|-----|----------|
| id | BIGINT PK | |
| employee_number | VARCHAR(50) UNIQUE | EMP-YYYY-NNNNNN (автогенерация) |
| user_id | BIGINT FK(users.id) NULL UNIQUE | Связь с учётной записью (опционально) |
| surname | VARCHAR(200) | Фамилия |
| first_name | VARCHAR(200) | Имя |
| second_name | VARCHAR(200) NULL | Отчество / второе имя |
| gender | VARCHAR(20) NULL | male / female / other |
| marital_status | VARCHAR(50) NULL | Single, Married, … |
| nationality | VARCHAR(100) NULL | Kenyan, … |
| date_of_birth | DATE NULL | |
| mobile_phone | VARCHAR(50) NULL | |
| email | VARCHAR(255) NULL | |
| physical_address | TEXT NULL | |
| town | VARCHAR(200) NULL | |
| postal_address | VARCHAR(500) NULL | |
| postal_code | VARCHAR(20) NULL | |
| job_title | VARCHAR(200) NULL | Teacher, Cleaner, … |
| employee_start_date | DATE NULL | Дата начала работы |
| salary | DECIMAL(15,2) NULL | Оклад/зарплата (KES) |
| national_id_number | VARCHAR(50) NULL | |
| kra_pin_number | VARCHAR(50) NULL | |
| nssf_number | VARCHAR(50) NULL | |
| nhif_number | VARCHAR(100) NULL | SHA number и т.д. |
| bank_name | VARCHAR(200) NULL | |
| bank_branch_name | VARCHAR(200) NULL | |
| bank_code | VARCHAR(20) NULL | |
| branch_code | VARCHAR(20) NULL | |
| bank_account_number | VARCHAR(50) NULL | |
| bank_account_holder_name | VARCHAR(200) NULL | |
| next_of_kin_name | VARCHAR(200) NULL | |
| next_of_kin_relationship | VARCHAR(100) NULL | |
| next_of_kin_phone | VARCHAR(50) NULL | |
| next_of_kin_address | TEXT NULL | |
| has_mortgage_relief | BOOLEAN DEFAULT FALSE | |
| has_insurance_relief | BOOLEAN DEFAULT FALSE | |
| status | VARCHAR(20) | active / inactive / terminated (по желанию) |
| notes | TEXT NULL | |
| created_at, updated_at, created_by_id | | Аудит |

**Вложения:**  
- **Загруженные в ERP** (форма сотрудника): те же механизмы, что и для подтверждений платежей и proof — сущность **Attachment** (см. `docs/PAYMENT_CONFIRMATION_UPLOADS.md`). Файл сохраняется в **локальную папку** `uploads/` в dev или в **Cloudflare R2** (S3-совместимое хранилище) в prod (см. `docs/CLOUDFLARE_R2.md`). В модели Employee — поля-ссылки на Attachment (например `national_id_attachment_id`, `kra_pin_attachment_id` и т.д., FK на attachments.id).
- **При импорте из CSV** (выгрузка Google Form): в CSV приходят только **ссылки на Google Drive**. В текущей реализации ссылки не переносятся в отдельные поля Employee — сохраняются только структурированные HR-данные и реквизиты. Перенос самих файлов в наше хранилище (R2/local) требует отдельного процесса (скачивание по ссылке или интеграция с Google Drive API).

---

## 6. Выгрузки для бухгалтерии

Нужен экспорт по списку сотрудников (или по фильтру: активные, по подразделению/должности и т.д.) с полями, необходимыми для:
- расчёта/передачи зарплаты;
- отчётности в KRA/NSSF/NHIF;
- банковских платежей.

Пример набора для выгрузки (формат CSV/Excel на выбор):
- employee_number, surname, first_name, second_name, job_title, employee_start_date
- salary
- national_id_number, kra_pin_number, nssf_number, nhif_number
- bank_name, bank_branch_name, bank_code, branch_code, bank_account_number, bank_account_holder_name
- has_mortgage_relief, has_insurance_relief
- (опционально) contact: email, mobile_phone

Реализация: endpoint вида `GET /api/v1/employees/export?format=csv|xlxs&status=active` с правами Admin/SuperAdmin/Accountant (по политике доступа к персональным данным).

---

## 7. Импорт CSV (маппинг с Google Form)

Ориентир — заголовки из текущей выгрузки формы (имена колонок в CSV). Пример маппинга:

| CSV column | Employee field |
|------------|----------------|
| Timestamp | — (или created_at при создании) |
| Surname / Last Name | surname |
| First Name | first_name |
| Second Name | second_name |
| Gender | gender (нормализовать: Female→female, Male→male) |
| Marital Status | marital_status |
| Nationality | nationality |
| Date of Birth | date_of_birth (парсинг формата из формы) |
| Mobile Phone Number | mobile_phone |
| Email Address | email |
| Physical Address | physical_address |
| Town | town |
| Postal Address | postal_address |
| Postal Code | postal_code |
| Job Title / Role | job_title |
| Employee Start Date | employee_start_date |
| National ID Number | national_id_number |
| KRA PIN Number | kra_pin_number |
| NSSF Number | nssf_number |
| NHIF / SHA Number | nhif_number |
| Bank Name | bank_name |
| Bank Branch Name | bank_branch_name |
| Bank Code | bank_code |
| Branch Code | branch_code |
| Account Number | bank_account_number |
| Account Holder Name | bank_account_holder_name |
| Next of Kin – Full Name | next_of_kin_name |
| Relationship to Employee | next_of_kin_relationship |
| Next of Kin – Mobile Phone Number | next_of_kin_phone |
| Next of Kin – Physical Address | next_of_kin_address |
| Do you have Mortgage Relief? | has_mortgage_relief (Yes/No → true/false) |
| Do you have Insurance Reliefs? | has_insurance_relief |
| Upload … (URLs) | url_* поля или импорт в Attachment (отдельная задача) |

При импорте решать: создавать только новую запись или обновлять по ключу (например, national_id_number или email), если запись уже есть.

---

## 7.1 Варианты переноса файлов с Google Drive в ERP

После импорта CSV в Employee попадают только ссылки на Google Drive. Ниже — варианты, как получить сами файлы в наше хранилище (R2 / локальная папка) и привязать к Attachment.

### Вариант A: Ручная дозагрузка в карточке сотрудника

**Суть:** В карточке сотрудника показываем сохранённые URL (кликабельные). Админ/HR при необходимости открывает ссылку, скачивает файл и загружает его в ERP через форму «Загрузить скан» (как для подтверждений платежей). URL потом можно оставить для истории или скрыть после появления Attachment.

**Плюсы:** Без разработки интеграции, без доступа к Google API, подходит для небольшого потока.  
**Минусы:** Ручной труд, легко забыть дозагрузить.

---

### Вариант B: Скачивание по публичной ссылке (скрипт / фоновый процесс)

**Суть:** Ссылки вида `https://drive.google.com/open?id=...` или `https://drive.google.com/file/d/ID/view` по умолчанию требуют авторизацию. Если в настройках Google Drive файл или папка открыты «для всех, у кого есть ссылка», можно попробовать скачать по прямому URL вида `https://drive.google.com/uc?export=download&id=FILE_ID`. Реализация: скрипт или endpoint (например, «Перенести вложения по ссылкам для сотрудника»), который для каждого url_* поля извлекает FILE_ID из ссылки, выполняет HTTP GET, сохраняет байты через существующий Attachment-сервис и проставляет employee.national_id_attachment_id и т.д.

**Плюсы:** Частичная автоматизация без OAuth.  
**Минусы:** Нестабильно: при смене прав доступа или формата ссылок скачивание ломается; большие файлы могут требовать подтверждение в браузере (Google отдаёт предупреждение). Подходит скорее для разового переноса с заранее открытыми ссылками.

---

### Вариант C: Google Drive API (Service Account)

**Суть:** Создать проект в Google Cloud, включить Drive API, создать Service Account и выдать ему доступ к папке/файлам (например, папка, куда форма сохраняет вложения, расшарена на email сервисного аккаунта). Бэкенд по FILE_ID (из URL в Employee) вызывает Drive API `files.get` с параметром `alt=media`, получает поток байтов, сохраняет в Attachment и обновляет поля employee.*_attachment_id.

**Плюсы:** Надёжно, под полным контролем приложения, можно автоматизировать при импорте CSV или по кнопке «Скачать файлы с Drive».  
**Минусы:** Нужна настройка Google Cloud, хранение credentials (JSON ключа), папку формы нужно шарить на service account.

---

### Вариант D: Google Picker / выбор файла из Drive в UI

**Суть:** На странице редактирования сотрудника добавить кнопку «Выбрать из Google Drive». Через Google Picker API пользователь (под своей учёткой Google) выбирает файл; фронтенд получает ссылку или временный URL. Дальше либо фронт скачивает файл и шлёт на `POST /attachments`, либо бэкенд по переданному fileId и токену пользователя запрашивает файл через Drive API.

**Плюсы:** Удобно для пользователя, не нужно вручную скачивать и загружать.  
**Минусы:** Нужна OAuth для пользователя (Google Sign-In), настройка проекта в Google Cloud и учёт того, что не у всех сотрудников есть Google-аккаунт.

---

### Вариант E: Форма в ERP вместо Drive для новых сотрудников

**Суть:** Для новых приёмов перейти на форму в ERP (или гибрид: форма в ERP + опционально импорт старых ответов из CSV). Файлы сразу загружаются в Attachment при отправке формы. Старые записи с URL из Google Form либо переносить по варианту A/B/C, либо оставить ссылками.

**Плюсы:** Один источник правды, никакой зависимости от Drive для новых данных.  
**Минусы:** Меняется процесс для сотрудников (заполняют форму в ERP или отдают документы HR для загрузки).

---

### Рекомендация

- **Старт (MVP):** загружать сканы напрямую в ERP в карточке сотрудника; для legacy-данных из Google Form переносить файлы отдельной задачей (вариант A/B/C).
- **Разовый перенос архива:** если ссылки открыты «по ссылке» — скрипт по варианту B; иначе — ручная выгрузка или вариант C при готовности настраивать Service Account.
- **Долгосрочно:** для новых данных — форма в ERP с загрузкой в Attachment (вариант E); опционально Google Picker (вариант D) как удобство для тех, у кого файлы уже в Drive.

---

## 8. Краткое сравнение вариантов процесса

| Критерий | Только Google Form + импорт | Только форма в ERP | Гибрид (форма + импорт + ручной ввод) |
|----------|-----------------------------|--------------------|----------------------------------------|
| Привычность процесса | Да | Нет (новый процесс) | Да |
| Один источник правды | После импорта — да | Да | Да |
| Загрузка файлов в ERP | По желанию (парсинг URL или отдельно) | Сразу в Attachment | Как в варианте 1 или 2 |
| Дубли в форме | Разбирать при импорте | Меньше (валидация в форме) | Разбирать при импорте / править в ERP |
| Разработка | Импорт + маппинг | Форма UI + бэкенд | Импорт + форма/редактирование в ERP |

**Рекомендация:** гибрид (вариант 3): оставить сбор через Google Form, добавить импорт CSV и ручное создание/редактирование Employee в ERP; при необходимости позже заменить форму на форму в ERP.

---

## 9. Зависимости и порядок работ

1. **Модель и миграции:** таблица `employees`, при выборе варианта B — миграция compensations на `employee_id` → `employees.id`, создание записей Employee для существующих User с claims/payouts/balances.
2. **API:** CRUD Employee, импорт CSV (маппинг как в п. 7), экспорт для бухгалтерии (CSV/Excel).
3. **UI:** список и карточка Employee, форма создания/редактирования, экран импорта CSV, кнопка/страница выгрузки для бухгалтерии.
4. **Права:** доступ к персональным данным и экспорту — в соответствии с ролями (например, Admin, SuperAdmin, при необходимости Accountant только на экспорт).
5. **Вложения:** при необходимости — хранение сканоков (ID, KRA, NSSF, NHIF, банк) в Attachment с привязкой к Employee; импорт URL из формы можно на первом этапе сохранять в текстовые поля.

Детальный чеклист задач вынесен в **TASKS.md**, секция «Фаза: HR — Справочник сотрудников».
