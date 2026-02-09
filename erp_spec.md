# Детальное техническое задание
## ERP-система для кенийской школы (MVP)

**Версия:** 2.0  
**Дата:** 2026-01-25  
**Статус:** Детальная спецификация для разработки

---

## ОГЛАВЛЕНИЕ

1. [Введение и общие положения](#1-введение-и-общие-положения)
2. [Архитектура данных и модель предметной области](#2-архитектура-данных-и-модель-предметной-области)
3. [Детальные спецификации сущностей](#3-детальные-спецификации-сущностей)
4. [Бизнес-логика и алгоритмы](#4-бизнес-логика-и-алгоритмы)
5. [Диаграммы состояний и жизненные циклы](#5-диаграммы-состояний-и-жизненные-циклы)
6. [Правила валидации и ограничения целостности](#6-правила-валидации-и-ограничения-целостности)
7. [Детальные бизнес-процессы](#7-детальные-бизнес-процессы)
8. [Формулы и расчеты](#8-формулы-и-расчеты)
9. [Права доступа и безопасность](#9-права-доступа-и-безопасность)
10. [Спецификации интерфейсов и API](#10-спецификации-интерфейсов-и-api)
11. [Отчеты и аналитика](#11-отчеты-и-аналитика)
12. [Нефункциональные требования](#12-нефункциональные-требования)
13. [Тестовые сценарии](#13-тестовые-сценарии)

---

## 1. ВВЕДЕНИЕ И ОБЩИЕ ПОЛОЖЕНИЯ

### 1.1. Цель системы

Система предназначена для автоматизации основных операционных процессов частной школы в Кении, включая:

- **Финансовый учет учеников** (начисления, платежи, долги, кредиты)
- **Управление складом** (учет, приемка, выдача, инвентаризация)
- **Управление закупками** (заказы, приемка, платежи, долги поставщикам)
- **Компенсации сотрудникам** (учет расходов, балансы, выплаты)

### 1.2. Границы системы

**В рамках MVP:**
- Управление учениками и их финансовыми обязательствами
- Система начислений по триместрам (Terms)
- Прием платежей и автоматическое распределение
- Продажа школьной формы с отложенной выдачей после оплаты
- Складской учет с контролем остатков
- Управление закупками от заказа до оплаты
- Учет расходов сотрудников и компенсаций
- Аудит всех операций
- Генерация документов (счета, квитанции, отчеты)

**За рамками MVP:**
- Родительский портал / мобильное приложение для родителей
- Автоматическая интеграция с платежными системами
- Учительский портал и академический модуль
- Система расписания и посещаемости
- HR-модуль (зарплата, табели, отпуска)
- Детальная CRM-воронка приема учеников
- Учет основных средств как отдельный модуль

### 1.3. Технологический стек (рекомендации)

**Backend:**
- Язык: Python (FastAPI/Django) или Node.js (Express/NestJS)
- База данных: PostgreSQL (рекомендуется для транзакционности и JSON-полей)
- ORM: SQLAlchemy / Prisma / Django ORM

**Frontend:**
- React / Vue.js / Next.js
- UI Kit: Tailwind CSS (выбрано в проекте; UI на кастомных компонентах, без MUI)
- PDF Generation: jsPDF / PDFKit / WeasyPrint

**Infrastructure:**
- Хостинг: Cloud (AWS/GCP/Azure/DigitalOcean)
- Файловое хранилище: S3-compatible storage для вложений
- Backup: ежедневные автоматические бэкапы БД

### 1.4. Ключевые принципы разработки

1. **Транзакционность**: все финансовые и складские операции должны быть атомарными
2. **Аудит**: каждое изменение данных фиксируется
3. **Иммутабельность документов**: удаление = перевод в статус Cancelled
4. **Валидация на всех уровнях**: клиент, API, база данных
5. **Последовательная нумерация**: непрерывные номера документов по годам
6. **Explicit over implicit**: явные операции вместо скрытой магии

---

## 2. АРХИТЕКТУРА ДАННЫХ И МОДЕЛЬ ПРЕДМЕТНОЙ ОБЛАСТИ

### 2.1. Общая структура доменов

Система разделена на 4 основных домена:

```
┌─────────────────────────────────────────────────────────────┐
│                     STUDENTS & BILLING                       │
│  Student, Term, Invoice, InvoiceLine, Payment,              │
│  CreditBalance, Discount, Receipt                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    INVENTORY & WAREHOUSE                     │
│  Item, Category, StockBalance, StockMovement,               │
│  IssueRequest, UniformFulfillment                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  PROCUREMENT & EXPENSES                      │
│  PurchaseOrder, GoodsReceived, ProcurementPayment,          │
│  SupplierDebt, ExpenseCategory                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 EMPLOYEE COMPENSATIONS                       │
│  ExpenseClaim, CompensationPayout, EmployeeBalance          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CROSS-CUTTING CONCERNS                    │
│  User, Role, AuditLog, Attachment, SystemSettings           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2. Связи между доменами

**Students ↔ Inventory:**
- UniformFulfillment связывает продажу формы (Invoice) с выдачей SKU (StockMovement)

**Procurement ↔ Inventory:**
- GoodsReceived создает StockMovement типа Receive

**Procurement ↔ Compensations:**
- ProcurementPayment с employee_paid=true автоматически создает ExpenseClaim

**Students ↔ Billing:**
- Payment распределяется по InvoiceLines через allocation_details

### 2.3. Типы данных и стандарты

**Денежные значения:**
- Тип: DECIMAL(15, 2)
- Валюта: KES (Kenyan Shilling)
- Округление: ROUND_HALF_UP

**Даты и время:**
- Формат хранения: ISO 8601 (UTC)
- Формат отображения: DD/MM/YYYY для дат, DD/MM/YYYY HH:mm для timestamps

**Текстовые поля:**
- Кодировка: UTF-8
- Длина имен: VARCHAR(200)
- Длина описаний: TEXT / VARCHAR(2000)

**Идентификаторы:**
- Primary Keys: BIGINT AUTO_INCREMENT или UUID
- Document Numbers: VARCHAR(50), формат PREFIX-YYYY-NNNNNN

---

## 3. ДЕТАЛЬНЫЕ СПЕЦИФИКАЦИИ СУЩНОСТЕЙ

### 3.1. DOMAIN: Students & Billing

#### 3.1.1. Student (Ученик)

**Таблица: `students`**

```sql
CREATE TABLE students (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_number VARCHAR(50) UNIQUE NOT NULL,  -- STU-YYYY-NNNNNN
    
    -- Personal Information
    surname VARCHAR(200) NOT NULL,
    first_name VARCHAR(200) NOT NULL,
    middle_name VARCHAR(200),
    date_of_birth DATE,
    gender ENUM('M', 'F', 'Other'),
    
    -- Status and Classification
    status ENUM('Lead', 'Student', 'Enrolled', 'Inactive') DEFAULT 'Student',
    grade VARCHAR(50),  -- 'Grade 1', 'Grade 2', etc.
    class_section VARCHAR(50),  -- 'A', 'B', etc. (optional)
    
    -- Contact Information
    address TEXT,
    
    -- Guardian Information
    guardian_name VARCHAR(200) NOT NULL,
    guardian_phone VARCHAR(50) NOT NULL,
    guardian_email VARCHAR(200),
    guardian_relationship VARCHAR(100),
    
    -- Next of Kin
    next_of_kin_name VARCHAR(200),
    next_of_kin_phone VARCHAR(50),
    next_of_kin_relationship VARCHAR(100),
    
    -- Transport
    transport_enabled BOOLEAN DEFAULT FALSE,
    transport_zone_id BIGINT,  -- FK to transport_zones
    
    -- Uniform
    current_uniform_size VARCHAR(20),  -- '8y', '10y', '12y', etc.
    
    -- Flags
    admission_fee_settled BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    notes TEXT,
    created_by BIGINT NOT NULL,  -- FK to users
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by BIGINT,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (transport_zone_id) REFERENCES transport_zones(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (updated_by) REFERENCES users(id),
    
    INDEX idx_status (status),
    INDEX idx_grade (grade),
    INDEX idx_guardian_phone (guardian_phone)
);
```

**Бизнес-правила:**

1. `student_number` генерируется автоматически при создании: `STU-{YYYY}-{NNNNNN}`
2. Переход в статус `Enrolled` происходит после первого платежа по school fee текущего Term
3. При переходе в `Inactive` прекращается генерация новых Term invoices
4. `admission_fee_settled` устанавливается в `TRUE` после полной оплаты admission fee
5. Изменение `grade` или `transport_zone_id` влияет на новые начисления (не на уже созданные)

**Валидации:**

- `surname` и `first_name`: обязательны, не пустые
- `guardian_name` и `guardian_phone`: обязательны
- `guardian_phone`: валидный телефонный формат (Kenyan: +254...)
- `grade`: из предопределенного списка ('PP1', 'PP2', 'Grade 1' ... 'Grade 8')
- `current_uniform_size`: из списка размеров ('6y', '8y', '10y', '12y', '14y', '16y')

---

#### 3.1.2. Term (Триместр/Семестр)

**Таблица: `terms`**

```sql
CREATE TABLE terms (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    year INT NOT NULL,  -- 2026, 2027, etc.
    term_number INT NOT NULL,  -- 1, 2, 3
    display_name VARCHAR(100) NOT NULL,  -- '2026-T1', '2026 Term 1', etc.
    
    status ENUM('Draft', 'Active', 'Closed') DEFAULT 'Draft',
    
    start_date DATE,
    end_date DATE,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by BIGINT,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_term (year, term_number),
    FOREIGN KEY (created_by) REFERENCES users(id),
    
    INDEX idx_status (status),
    INDEX idx_year (year)
);
```

**Бизнес-правила:**

1. Комбинация `(year, term_number)` уникальна
2. При создании нового Term система предлагает скопировать pricing из последнего Term
3. Только один Term может быть в статусе `Active` одновременно (бизнес-ограничение)
4. Переход Term в статус `Closed` блокирует создание новых invoices для этого Term

---

#### 3.1.3. PriceSettings (Настройки цен)

**Таблица: `price_settings`**

```sql
CREATE TABLE price_settings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    term_id BIGINT NOT NULL,
    
    -- School Fees by Grade
    grade VARCHAR(50) NOT NULL,
    school_fee_amount DECIMAL(15, 2) NOT NULL,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (term_id) REFERENCES terms(id),
    UNIQUE KEY unique_term_grade (term_id, grade),
    INDEX idx_term (term_id)
);

CREATE TABLE transport_zones (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    zone_name VARCHAR(100) NOT NULL UNIQUE,
    zone_code VARCHAR(20) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transport_pricing (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    term_id BIGINT NOT NULL,
    zone_id BIGINT NOT NULL,
    transport_fee_amount DECIMAL(15, 2) NOT NULL,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (term_id) REFERENCES terms(id),
    FOREIGN KEY (zone_id) REFERENCES transport_zones(id),
    UNIQUE KEY unique_term_zone (term_id, zone_id)
);

CREATE TABLE fixed_fees (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fee_type VARCHAR(50) NOT NULL,  -- 'Admission', 'Interview', 'Diary', etc.
    amount DECIMAL(15, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    applies_from_date DATE,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**Бизнес-правила:**

1. Каждый Term имеет свой набор цен (price_settings, transport_pricing)
2. При создании нового Term цены копируются из предыдущего, но могут быть изменены
3. Изменение цен в существующем Term НЕ влияет на уже созданные invoices
4. `fixed_fees` (admission, interview, diary) могут иметь версионность по датам

---

#### 3.1.4. Invoice (Счет)

**Таблица: `invoices`**

```sql
CREATE TABLE invoices (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,  -- INV-YYYY-NNNNNN
    
    student_id BIGINT NOT NULL,
    term_id BIGINT NOT NULL,
    
    invoice_type ENUM('Term', 'Sales', 'Other') DEFAULT 'Term',
    
    status ENUM('Draft', 'Issued', 'PartiallyPaid', 'Paid', 'Cancelled') DEFAULT 'Draft',
    
    -- Amounts
    subtotal DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    discount_total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,  -- subtotal - discount_total
    paid_total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    amount_due DECIMAL(15, 2) NOT NULL DEFAULT 0.00,  -- total - paid_total
    
    -- Metadata
    issue_date DATE,
    due_date DATE,
    cancelled_reason TEXT,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by BIGINT,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (term_id) REFERENCES terms(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    
    INDEX idx_student (student_id),
    INDEX idx_term (term_id),
    INDEX idx_status (status),
    INDEX idx_invoice_number (invoice_number)
);
```

**Бизнес-правила:**

1. `invoice_number` генерируется автоматически: `INV-{YYYY}-{NNNNNN}`
2. `subtotal` = сумма всех invoice_lines (line_total)
3. `total` = subtotal - discount_total
4. `amount_due` = total - paid_total
5. Статус пересчитывается при изменении платежей:
   - `paid_total = 0` → `Issued`
   - `0 < paid_total < total` → `PartiallyPaid`
   - `paid_total >= total` → `Paid`
6. При отмене обязателен `cancelled_reason`

---

#### 3.1.5. InvoiceLine (Строка счета)

**Таблица: `invoice_lines`**

```sql
CREATE TABLE invoice_lines (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    invoice_id BIGINT NOT NULL,
    
    line_type ENUM('SchoolFee', 'Transport', 'Admission', 'Interview', 
                   'UniformBundle', 'DiaryBooks', 'Other') NOT NULL,
    
    description VARCHAR(500) NOT NULL,
    
    quantity DECIMAL(10, 2) DEFAULT 1.00,
    unit_price DECIMAL(15, 2) NOT NULL,
    line_total DECIMAL(15, 2) NOT NULL,  -- quantity * unit_price
    
    -- Payment tracking
    paid_amount DECIMAL(15, 2) DEFAULT 0.00,
    remaining_amount DECIMAL(15, 2),  -- line_total - paid_amount
    
    -- Flags
    must_be_paid_in_full BOOLEAN DEFAULT FALSE,
    allow_partial_payment BOOLEAN DEFAULT TRUE,
    
    -- For UniformBundle
    uniform_size VARCHAR(20),
    
    line_order INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    
    INDEX idx_invoice (invoice_id),
    INDEX idx_line_type (line_type)
);
```

**Правила для `must_be_paid_in_full`:**

- `TRUE` для: UniformBundle, Admission, Interview, DiaryBooks
- `FALSE` для: SchoolFee, Transport

**Правила для `allow_partial_payment`:**

- `TRUE` для: SchoolFee, Transport
- `FALSE` для: UniformBundle, Admission, Interview (но оплата может быть несколькими платежами, главное - 100% перед выполнением)

**Расчеты:**

- `line_total = quantity * unit_price`
- `remaining_amount = line_total - paid_amount`

---

#### 3.1.6. Payment (Платеж)

**Таблица: `payments`**

```sql
CREATE TABLE payments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_number VARCHAR(50) UNIQUE NOT NULL,  -- PAY-YYYY-NNNNNN
    
    student_id BIGINT NOT NULL,
    
    payment_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    
    payment_method ENUM('M-Pesa', 'Bank', 'Cash') DEFAULT 'M-Pesa',
    reference_number VARCHAR(200),  -- M-Pesa transaction ID
    
    status ENUM('Posted', 'Cancelled') DEFAULT 'Posted',
    
    -- Allocation (stored as JSON or separate table)
    allocation_details JSON,  -- [{invoice_line_id, allocated_amount}, ...]
    
    receipt_number VARCHAR(50),  -- RCT-YYYY-NNNNNN (FK to receipts)
    
    cancelled_reason TEXT,
    cancelled_by BIGINT,
    cancelled_at TIMESTAMP,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (cancelled_by) REFERENCES users(id),
    
    INDEX idx_student (student_id),
    INDEX idx_payment_date (payment_date),
    INDEX idx_status (status)
);
```

**Структура `allocation_details` (JSON):**

```json
[
  {
    "invoice_line_id": 123,
    "invoice_id": 45,
    "line_type": "UniformBundle",
    "allocated_amount": 5000.00
  },
  {
    "invoice_line_id": 124,
    "invoice_id": 45,
    "line_type": "SchoolFee",
    "allocated_amount": 3000.00
  }
]
```

**Бизнес-правила:**

1. При создании платежа автоматически запускается allocation алгоритм
2. Генерируется Receipt (квитанция) одновременно с Payment
3. При отмене платежа (`status = Cancelled`):
   - allocation сторнируется
   - invoice_lines.paid_amount уменьшается
   - invoice статусы пересчитываются
   - receipt помечается как voided
   - обязателен `cancelled_reason`

---

#### 3.1.7. CreditBalance (Кредит/Переплата)

**Таблица: `credit_balances`**

```sql
CREATE TABLE credit_balances (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_id BIGINT NOT NULL UNIQUE,
    
    balance_amount DECIMAL(15, 2) DEFAULT 0.00,
    
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id),
    INDEX idx_student (student_id)
);

CREATE TABLE credit_transactions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    student_id BIGINT NOT NULL,
    
    transaction_type ENUM('Increase', 'Decrease'),
    amount DECIMAL(15, 2) NOT NULL,
    balance_before DECIMAL(15, 2) NOT NULL,
    balance_after DECIMAL(15, 2) NOT NULL,
    
    related_payment_id BIGINT,
    description TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (related_payment_id) REFERENCES payments(id),
    INDEX idx_student (student_id)
);
```

**Бизнес-правила:**

1. Кредит увеличивается когда платеж превышает долг
2. Кредит уменьшается когда применяется к новым invoices/платежам
3. Все изменения кредита записываются в `credit_transactions` для аудита
4. Кредит НЕ возвращается родителям (только используется для будущих платежей)

---

#### 3.1.8. Discount (Скидка)

**Таблица: `discounts`**

```sql
CREATE TABLE discounts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    student_id BIGINT,  -- NULL if global/rule-based
    invoice_id BIGINT,  -- NULL if applied at line level
    invoice_line_id BIGINT,  -- NULL if applied at invoice level
    
    discount_type ENUM('Percentage', 'Fixed') NOT NULL,
    discount_value DECIMAL(15, 2) NOT NULL,
    calculated_amount DECIMAL(15, 2) NOT NULL,  -- actual KES amount
    
    reason_category VARCHAR(100) NOT NULL,  -- from predefined list
    reason_detail TEXT,
    
    valid_from DATE,
    valid_to DATE,
    
    applied_by BIGINT NOT NULL,
    approved_by BIGINT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (invoice_line_id) REFERENCES invoice_lines(id),
    FOREIGN KEY (applied_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id),
    
    INDEX idx_student (student_id),
    INDEX idx_invoice (invoice_id)
);

CREATE TABLE discount_reasons (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    reason_code VARCHAR(50) UNIQUE NOT NULL,
    reason_name VARCHAR(200) NOT NULL,
    requires_approval BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Sample data
INSERT INTO discount_reasons (reason_code, reason_name) VALUES
('SIBLING_3RD', '3rd or 4th Sibling Discount'),
('STAFF_CHILD', 'Staff Child Discount'),
('FINANCIAL_AID', 'Financial Aid/Scholarship'),
('EARLY_PAYMENT', 'Early Payment Discount'),
('SPECIAL_CASE', 'Special Case (Admin Discretion)'),
('OTHER', 'Other (specify in detail)');
```

**Бизнес-правила:**

1. Скидка применяется к invoice или invoice_line (взаимоисключающе)
2. Расчет `calculated_amount`:
   - Percentage: `base_amount * (discount_value / 100)`
   - Fixed: `discount_value`
3. Скидки требуют approve от Admin/SuperAdmin (в зависимости от причины)
4. При отмене скидки invoice_totals пересчитываются

---

#### 3.1.9. Receipt (Квитанция)

**Таблица: `receipts`**

```sql
CREATE TABLE receipts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    receipt_number VARCHAR(50) UNIQUE NOT NULL,  -- RCT-YYYY-NNNNNN
    
    payment_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    
    receipt_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    
    status ENUM('Valid', 'Voided') DEFAULT 'Valid',
    voided_reason TEXT,
    
    pdf_path VARCHAR(500),  -- path to generated PDF
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    voided_at TIMESTAMP,
    
    FOREIGN KEY (payment_id) REFERENCES payments(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    
    INDEX idx_payment (payment_id),
    INDEX idx_receipt_number (receipt_number)
);
```

**Бизнес-правила:**

1. Receipt создается автоматически при создании Payment
2. При отмене Payment → Receipt статус меняется на `Voided`
3. PDF генерируется синхронно при создании (или асинхронно через queue)

---

### 3.2. DOMAIN: Inventory & Warehouse

#### 3.2.1. Category (Категория товаров)

**Таблица: `categories`**

```sql
CREATE TABLE categories (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(200) NOT NULL UNIQUE,
    parent_category_id BIGINT,  -- для вложенности
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (parent_category_id) REFERENCES categories(id),
    INDEX idx_parent (parent_category_id)
);

-- Sample data
INSERT INTO categories (category_name) VALUES
('Stationery'),
('Uniforms'),
('Kitchen Supplies'),
('Cleaning Supplies'),
('Teaching Materials'),
('Books');
```

---

#### 3.2.2. Item (Товар/SKU)

**Таблица: `items`**

```sql
CREATE TABLE items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    item_code VARCHAR(100) UNIQUE NOT NULL,  -- SKU
    item_name VARCHAR(300) NOT NULL,
    
    category_id BIGINT NOT NULL,
    
    unit_of_measure VARCHAR(50) DEFAULT 'pcs',  -- pcs, packs, kg, liters, etc.
    
    -- Flags
    track_stock BOOLEAN DEFAULT TRUE,
    is_uniform_item BOOLEAN DEFAULT FALSE,
    
    -- For uniform items
    uniform_size VARCHAR(20),  -- '8y', '10y', etc.
    uniform_component VARCHAR(100),  -- 'Shirt', 'Shorts', 'Sweater', 'Socks', 'Shoes'
    
    -- Pricing (for reference/reporting, not used in invoicing for uniforms)
    cost_price DECIMAL(15, 2),
    
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    
    INDEX idx_category (category_id),
    INDEX idx_item_code (item_code),
    INDEX idx_uniform (is_uniform_item)
);
```

**Бизнес-правила:**

1. `item_code` (SKU) генерируется автоматически или вводится вручную (уникальный)
2. Для uniform items обязательны поля `uniform_size` и `uniform_component`
3. `track_stock = FALSE` используется для услуг/расходов без складского учета

---

#### 3.2.3. StockBalance (Остаток)

**Таблица: `stock_balances`**

```sql
CREATE TABLE stock_balances (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    item_id BIGINT NOT NULL UNIQUE,
    
    quantity_on_hand DECIMAL(15, 3) DEFAULT 0.000,
    
    last_movement_at TIMESTAMP,
    
    FOREIGN KEY (item_id) REFERENCES items(id),
    INDEX idx_item (item_id)
);
```

**Бизнес-правила:**

1. Создается автоматически при создании Item (с quantity = 0)
2. Обновляется только через StockMovement (транзакционно)
3. **НИКОГДА не должен быть отрицательным** (валидация перед Issue/WriteOff)

---

#### 3.2.4. StockMovement (Движение склада)

**Таблица: `stock_movements`**

```sql
CREATE TABLE stock_movements (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    movement_number VARCHAR(50) UNIQUE,  -- MOV-YYYY-NNNNNN
    
    item_id BIGINT NOT NULL,
    movement_type ENUM('Receive', 'Issue', 'WriteOff', 'Adjustment') NOT NULL,
    
    quantity_delta DECIMAL(15, 3) NOT NULL,  -- positive or negative
    quantity_before DECIMAL(15, 3) NOT NULL,
    quantity_after DECIMAL(15, 3) NOT NULL,
    
    -- Related documents
    related_document_type VARCHAR(50),  -- 'GRN', 'IssueRequest', 'UniformFulfillment', etc.
    related_document_id BIGINT,
    
    destination VARCHAR(200),  -- For Issue: Grade 3, Kitchen, Admin, etc.
    reason TEXT,  -- For WriteOff/Adjustment
    
    movement_date DATE NOT NULL,
    
    created_by BIGINT NOT NULL,
    approved_by BIGINT,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (item_id) REFERENCES items(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id),
    
    INDEX idx_item (item_id),
    INDEX idx_type (movement_type),
    INDEX idx_date (movement_date)
);
```

**Бизнес-правила:**

1. **Транзакционность**: создание movement и обновление balance должны быть в одной транзакции
2. Всегда фиксируется `quantity_before` и `quantity_after` для аудита
3. `quantity_delta`:
   - Positive для Receive, Adjustment (increase)
   - Negative для Issue, WriteOff, Adjustment (decrease)
4. WriteOff и Adjustment требуют approve от Admin
5. Issue может требовать approve в зависимости от настроек

**Алгоритм создания Movement:**

```python
def create_stock_movement(item_id, movement_type, quantity_delta, ...):
    # 1. Lock row in stock_balances
    balance = StockBalance.objects.select_for_update().get(item_id=item_id)
    
    # 2. Validate
    if balance.quantity_on_hand + quantity_delta < 0:
        raise ValidationError("Insufficient stock")
    
    # 3. Create movement
    movement = StockMovement.objects.create(
        item_id=item_id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        quantity_before=balance.quantity_on_hand,
        quantity_after=balance.quantity_on_hand + quantity_delta,
        ...
    )
    
    # 4. Update balance
    balance.quantity_on_hand += quantity_delta
    balance.last_movement_at = now()
    balance.save()
    
    return movement
```

---

#### 3.2.5. IssueRequest (Заявка на выдачу)

**Таблица: `issue_requests`**

```sql
CREATE TABLE issue_requests (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_number VARCHAR(50) UNIQUE NOT NULL,  -- ISS-REQ-YYYY-NNNNNN
    
    requested_by BIGINT NOT NULL,
    destination VARCHAR(200) NOT NULL,  -- Grade 3, Kitchen, Admin, etc.
    
    status ENUM('Draft', 'PendingApproval', 'Approved', 'PartiallyIssued', 
                'Issued', 'Cancelled') DEFAULT 'Draft',
    
    request_date DATE NOT NULL,
    required_date DATE,
    
    approved_by BIGINT,
    approved_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (requested_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id),
    
    INDEX idx_status (status),
    INDEX idx_requested_by (requested_by)
);

CREATE TABLE issue_request_lines (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_id BIGINT NOT NULL,
    
    item_id BIGINT NOT NULL,
    quantity_requested DECIMAL(15, 3) NOT NULL,
    quantity_issued DECIMAL(15, 3) DEFAULT 0.000,
    quantity_pending DECIMAL(15, 3),  -- requested - issued
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (request_id) REFERENCES issue_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id),
    
    INDEX idx_request (request_id),
    INDEX idx_item (item_id)
);
```

**Бизнес-правила:**

1. User создает request в статусе Draft
2. Admin approve переводит в Approved
3. При выдаче (Issue):
   - создается StockMovement с `related_document_type='IssueRequest'`
   - обновляется `quantity_issued` в request line
   - пересчитывается `quantity_pending`
   - статус request обновляется:
     - все строки issued → Issued
     - хотя бы одна частично → PartiallyIssued
4. Возможно закрытие request с pending остатками (Cancel Remaining)

---

#### 3.2.6. UniformFulfillment (Выдача формы)

**Таблица: `uniform_fulfillments`**

```sql
CREATE TABLE uniform_fulfillments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    student_id BIGINT NOT NULL,
    invoice_line_id BIGINT NOT NULL,  -- link to UniformBundle line
    
    uniform_size VARCHAR(20) NOT NULL,
    
    status ENUM('Pending', 'Partial', 'Fulfilled') DEFAULT 'Pending',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (invoice_line_id) REFERENCES invoice_lines(id),
    
    INDEX idx_student (student_id),
    INDEX idx_status (status)
);

CREATE TABLE uniform_fulfillment_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fulfillment_id BIGINT NOT NULL,
    
    item_id BIGINT NOT NULL,  -- uniform SKU
    quantity_required INT NOT NULL,
    quantity_issued INT DEFAULT 0,
    quantity_pending INT,  -- required - issued
    
    issued_by BIGINT,
    issued_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (fulfillment_id) REFERENCES uniform_fulfillments(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id),
    FOREIGN KEY (issued_by) REFERENCES users(id),
    
    INDEX idx_fulfillment (fulfillment_id),
    INDEX idx_pending (quantity_pending)
);
```

**Бизнес-правила:**

1. UniformFulfillment создается автоматически при 100% оплате UniformBundle line
2. Система определяет required items по размеру:
   - Shirt (size X) - qty 2
   - Shorts (size X) - qty 2
   - Sweater (size X) - qty 1
   - Socks (size X) - qty 3 pairs
   - Shoes (size X) - qty 1 pair
3. При выдаче элемента:
   - создается StockMovement типа Issue
   - обновляется `quantity_issued` и `quantity_pending`
   - пересчитывается статус fulfillment
4. Выдача может быть частичной (если stock недостаточен)

**Определение комплекта (business logic):**

```python
UNIFORM_BUNDLE_DEFINITION = {
    '6y': [
        {'component': 'Shirt', 'size': '6y', 'qty': 2},
        {'component': 'Shorts', 'size': '6y', 'qty': 2},
        {'component': 'Sweater', 'size': '6y', 'qty': 1},
        {'component': 'Socks', 'size': '6y', 'qty': 3},
        {'component': 'Shoes', 'size': '6y', 'qty': 1},
    ],
    '8y': [...],
    # etc.
}
```

---

### 3.3. DOMAIN: Procurement & Expenses

#### 3.3.1. PurchaseOrder (Заказ)

**Таблица: `purchase_orders`**

```sql
CREATE TABLE purchase_orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    po_number VARCHAR(50) UNIQUE NOT NULL,  -- PO-YYYY-NNNNNN
    
    supplier_name VARCHAR(300) NOT NULL,
    supplier_contact VARCHAR(200),
    
    status ENUM('Draft', 'Ordered', 'PartiallyReceived', 'Received', 'Cancelled') 
        DEFAULT 'Draft',
    
    order_date DATE NOT NULL,
    expected_delivery_date DATE,
    
    -- Track to warehouse flag
    track_to_warehouse BOOLEAN DEFAULT TRUE,
    
    -- Totals
    expected_total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    received_value DECIMAL(15, 2) DEFAULT 0.00,
    paid_total DECIMAL(15, 2) DEFAULT 0.00,
    debt_amount DECIMAL(15, 2) DEFAULT 0.00,  -- received_value - paid_total
    
    notes TEXT,
    
    cancelled_reason TEXT,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by BIGINT,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (created_by) REFERENCES users(id),
    
    INDEX idx_status (status),
    INDEX idx_supplier (supplier_name),
    INDEX idx_po_number (po_number)
);

CREATE TABLE purchase_order_lines (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    po_id BIGINT NOT NULL,
    
    item_id BIGINT,  -- NULL if not warehouse item
    description VARCHAR(500) NOT NULL,
    
    quantity_expected DECIMAL(15, 3) NOT NULL,
    unit_price DECIMAL(15, 2) NOT NULL,
    line_total DECIMAL(15, 2) NOT NULL,  -- qty * price
    
    quantity_received DECIMAL(15, 3) DEFAULT 0.000,
    
    line_order INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id),
    
    INDEX idx_po (po_id)
);
```

**Бизнес-правила:**

1. `expected_total` = сумма всех line_total
2. Статус меняется на основе `quantity_received`:
   - все строки received = 100% → Received
   - хотя бы одна > 0% → PartiallyReceived
3. `debt_amount = received_value - paid_total`
4. Если `track_to_warehouse = FALSE`, то это расход без складского учета

---

#### 3.3.2. GoodsReceived (Приемка)

**Таблица: `goods_received_notes`**

```sql
CREATE TABLE goods_received_notes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    grn_number VARCHAR(50) UNIQUE NOT NULL,  -- GRN-YYYY-NNNNNN
    
    po_id BIGINT NOT NULL,
    
    status ENUM('Draft', 'Approved', 'Cancelled') DEFAULT 'Draft',
    
    received_date DATE NOT NULL,
    received_by BIGINT NOT NULL,
    
    approved_by BIGINT,
    approved_at TIMESTAMP,
    
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
    FOREIGN KEY (received_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id),
    
    INDEX idx_po (po_id),
    INDEX idx_status (status)
);

CREATE TABLE goods_received_lines (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    grn_id BIGINT NOT NULL,
    po_line_id BIGINT NOT NULL,
    
    item_id BIGINT,
    quantity_received DECIMAL(15, 3) NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (grn_id) REFERENCES goods_received_notes(id) ON DELETE CASCADE,
    FOREIGN KEY (po_line_id) REFERENCES purchase_order_lines(id),
    FOREIGN KEY (item_id) REFERENCES items(id),
    
    INDEX idx_grn (grn_id)
);
```

**Бизнес-правила:**

1. GRN создается на основе PO
2. При approve GRN:
   - создаются StockMovement типа Receive (если track_to_warehouse)
   - обновляется `quantity_received` в PO lines
   - пересчитывается `received_value` в PO
   - обновляется статус PO
3. GRN требует approve от Admin

**Алгоритм approve GRN:**

```python
def approve_grn(grn_id, approved_by):
    grn = GRN.objects.get(id=grn_id)
    po = grn.purchase_order
    
    with transaction.atomic():
        # 1. Create stock movements
        for line in grn.lines.all():
            if po.track_to_warehouse and line.item_id:
                create_stock_movement(
                    item_id=line.item_id,
                    movement_type='Receive',
                    quantity_delta=line.quantity_received,
                    related_document_type='GRN',
                    related_document_id=grn.id
                )
        
        # 2. Update PO lines
        for line in grn.lines.all():
            po_line = line.po_line
            po_line.quantity_received += line.quantity_received
            po_line.save()
        
        # 3. Recalculate PO received_value and status
        po.received_value = sum(
            line.quantity_received * line.unit_price
            for line in po.lines.all()
        )
        
        if all(line.quantity_received >= line.quantity_expected for line in po.lines.all()):
            po.status = 'Received'
        elif any(line.quantity_received > 0 for line in po.lines.all()):
            po.status = 'PartiallyReceived'
        
        po.save()
        
        # 4. Approve GRN
        grn.status = 'Approved'
        grn.approved_by = approved_by
        grn.approved_at = now()
        grn.save()
```

---

#### 3.3.3. ProcurementPayment (Платеж по закупке)

**Таблица: `procurement_payments`**

```sql
CREATE TABLE procurement_payments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_number VARCHAR(50) UNIQUE NOT NULL,  -- PPAY-YYYY-NNNNNN
    
    po_id BIGINT NOT NULL,
    
    payment_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    
    payment_method ENUM('M-Pesa', 'Bank', 'Cash', 'Other') DEFAULT 'Bank',
    reference_number VARCHAR(200),
    
    -- Payer
    company_paid BOOLEAN DEFAULT TRUE,
    employee_paid_id BIGINT,  -- if employee paid
    
    status ENUM('Posted', 'Cancelled') DEFAULT 'Posted',
    
    cancelled_reason TEXT,
    cancelled_by BIGINT,
    cancelled_at TIMESTAMP,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
    FOREIGN KEY (employee_paid_id) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (cancelled_by) REFERENCES users(id),
    
    INDEX idx_po (po_id),
    INDEX idx_status (status),
    INDEX idx_employee (employee_paid_id)
);
```

**Бизнес-правила:**

1. При создании платежа:
   - обновляется `po.paid_total`
   - пересчитывается `po.debt_amount`
2. Если `employee_paid_id` указан, автоматически создается ExpenseClaim
3. При отмене платежа (`status = Cancelled`):
   - `po.paid_total` уменьшается
   - если был создан ExpenseClaim, он тоже отменяется

**Алгоритм создания платежа:**

```python
def create_procurement_payment(po_id, amount, employee_paid_id=None, ...):
    po = PurchaseOrder.objects.get(id=po_id)
    
    with transaction.atomic():
        # 1. Create payment
        payment = ProcurementPayment.objects.create(
            po_id=po_id,
            amount=amount,
            employee_paid_id=employee_paid_id,
            ...
        )
        
        # 2. Update PO
        po.paid_total += amount
        po.debt_amount = po.received_value - po.paid_total
        po.save()
        
        # 3. Create claim if employee paid
        if employee_paid_id:
            ExpenseClaim.objects.create(
                employee_id=employee_paid_id,
                amount=amount,
                category='Procurement',
                description=f'Payment for PO {po.po_number}',
                auto_created_from_payment=True,
                related_procurement_payment_id=payment.id,
                status='PendingApproval'
            )
        
        return payment
```

---

### 3.4. DOMAIN: Employee Compensations

#### 3.4.1. ExpenseClaim (Расход сотрудника)

**Таблица: `expense_claims`**

```sql
CREATE TABLE expense_claims (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    claim_number VARCHAR(50) UNIQUE NOT NULL,  -- CLM-YYYY-NNNNNN
    
    employee_id BIGINT NOT NULL,
    
    expense_category VARCHAR(100) NOT NULL,  -- from expense_categories
    amount DECIMAL(15, 2) NOT NULL,
    description TEXT NOT NULL,
    
    expense_date DATE NOT NULL,
    
    proof_required BOOLEAN DEFAULT TRUE,
    proof_provided BOOLEAN DEFAULT FALSE,
    no_proof_reason TEXT,
    
    status ENUM('Draft', 'PendingApproval', 'Approved', 'PartiallyPaid', 
                'Paid', 'Rejected', 'Cancelled') DEFAULT 'Draft',
    
    paid_amount DECIMAL(15, 2) DEFAULT 0.00,
    remaining_amount DECIMAL(15, 2),  -- amount - paid_amount
    
    -- Auto-creation tracking
    auto_created_from_payment BOOLEAN DEFAULT FALSE,
    related_procurement_payment_id BIGINT,
    
    -- Approval
    approved_by BIGINT,
    approved_at TIMESTAMP,
    rejected_by BIGINT,
    rejected_at TIMESTAMP,
    rejection_reason TEXT,
    
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (employee_id) REFERENCES users(id),
    FOREIGN KEY (related_procurement_payment_id) REFERENCES procurement_payments(id),
    FOREIGN KEY (approved_by) REFERENCES users(id),
    FOREIGN KEY (rejected_by) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    
    INDEX idx_employee (employee_id),
    INDEX idx_status (status),
    INDEX idx_category (expense_category)
);

CREATE TABLE expense_categories (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(100) UNIQUE NOT NULL,
    requires_proof BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample data
INSERT INTO expense_categories (category_name) VALUES
('Procurement'),
('Transport'),
('Marketing'),
('Utilities'),
('Meals & Entertainment'),
('Office Supplies'),
('Other');
```

**Бизнес-правила:**

1. User может создавать claims для себя
2. Admin может создавать claims для любого сотрудника
3. Approve требуется от SuperAdmin
4. `remaining_amount = amount - paid_amount`
5. Статус меняется при выплатах:
   - `paid_amount = 0` → Approved
   - `0 < paid_amount < amount` → PartiallyPaid
   - `paid_amount >= amount` → Paid

---

#### 3.4.2. CompensationPayout (Выплата компенсации)

**Таблица: `compensation_payouts`**

```sql
CREATE TABLE compensation_payouts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payout_number VARCHAR(50) UNIQUE NOT NULL,  -- CPO-YYYY-NNNNNN
    
    employee_id BIGINT NOT NULL,
    
    payout_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    
    payment_method VARCHAR(100),
    reference_number VARCHAR(200),
    
    notes TEXT,
    
    created_by BIGINT NOT NULL,  -- SuperAdmin
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (employee_id) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    
    INDEX idx_employee (employee_id),
    INDEX idx_payout_date (payout_date)
);

CREATE TABLE payout_allocations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payout_id BIGINT NOT NULL,
    claim_id BIGINT NOT NULL,
    
    allocated_amount DECIMAL(15, 2) NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (payout_id) REFERENCES compensation_payouts(id) ON DELETE CASCADE,
    FOREIGN KEY (claim_id) REFERENCES expense_claims(id),
    
    INDEX idx_payout (payout_id),
    INDEX idx_claim (claim_id)
);
```

**Бизнес-правила:**

1. Payout создается только SuperAdmin
2. При создании payout:
   - сумма распределяется по approved claims (oldest first)
   - обновляется `paid_amount` в claims
   - пересчитывается статус claims
   - обновляется employee balance

**Алгоритм создания payout:**

```python
def create_payout(employee_id, amount, ...):
    with transaction.atomic():
        # 1. Get approved unpaid/partially paid claims (oldest first)
        claims = ExpenseClaim.objects.filter(
            employee_id=employee_id,
            status__in=['Approved', 'PartiallyPaid']
        ).order_by('created_at')
        
        # 2. Create payout
        payout = CompensationPayout.objects.create(
            employee_id=employee_id,
            amount=amount,
            ...
        )
        
        # 3. Allocate amount to claims
        remaining = amount
        for claim in claims:
            if remaining <= 0:
                break
            
            claim_remaining = claim.amount - claim.paid_amount
            allocate = min(remaining, claim_remaining)
            
            PayoutAllocation.objects.create(
                payout_id=payout.id,
                claim_id=claim.id,
                allocated_amount=allocate
            )
            
            claim.paid_amount += allocate
            claim.remaining_amount = claim.amount - claim.paid_amount
            
            if claim.paid_amount >= claim.amount:
                claim.status = 'Paid'
            else:
                claim.status = 'PartiallyPaid'
            
            claim.save()
            
            remaining -= allocate
        
        # 4. Update employee balance
        update_employee_balance(employee_id)
        
        return payout
```

---

#### 3.4.3. EmployeeBalance (Баланс сотрудника)

**Таблица: `employee_balances`**

```sql
CREATE TABLE employee_balances (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id BIGINT NOT NULL UNIQUE,
    
    total_approved DECIMAL(15, 2) DEFAULT 0.00,  -- sum of approved claims
    total_paid DECIMAL(15, 2) DEFAULT 0.00,      -- sum of payouts
    balance DECIMAL(15, 2) DEFAULT 0.00,          -- approved - paid (can be negative)
    
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (employee_id) REFERENCES users(id),
    INDEX idx_employee (employee_id)
);
```

**Бизнес-правила:**

1. `balance = total_approved - total_paid`
2. Положительный balance = школа должна сотруднику
3. Отрицательный balance = сотрудник должен школе (аванс)
4. Обновляется при:
   - approve claim
   - reject/cancel claim
   - create payout
   - cancel payout

---

### 3.5. DOMAIN: Cross-cutting

#### 3.5.1. User (Пользователь)

**Таблица: `users`**

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    full_name VARCHAR(200) NOT NULL,
    phone VARCHAR(50),
    
    role ENUM('SuperAdmin', 'Admin', 'User', 'Accountant') NOT NULL,
    
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    
    INDEX idx_email (email),
    INDEX idx_role (role)
);
```

**Роли и права:**

| Роль | Описание | Основные права |
|------|----------|----------------|
| **SuperAdmin** | Полный доступ | Все операции, включая финансовые approve, manage users |
| **Admin** | Операционный админ | Создание документов, складские approve, НЕ финансовые approve |
| **User** | Сотрудник | Создание requests/claims, просмотр своих данных |
| **Accountant** | Бухгалтер (read-only) | Просмотр всех данных, документов, отчетов; БЕЗ изменений |

---

#### 3.5.2. AuditLog (Журнал аудита)

**Таблица: `audit_logs`**

```sql
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    user_id BIGINT,
    action VARCHAR(100) NOT NULL,  -- CREATE, UPDATE, DELETE, APPROVE, CANCEL, etc.
    
    entity_type VARCHAR(100) NOT NULL,  -- Student, Invoice, Payment, etc.
    entity_id BIGINT NOT NULL,
    entity_identifier VARCHAR(200),  -- document number or name for display
    
    old_values JSON,  -- state before change
    new_values JSON,  -- state after change
    
    comment TEXT,
    
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    
    INDEX idx_user (user_id),
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);
```

**Что логировать:**

1. **Критичные операции:**
   - Создание/изменение Invoice, Payment, Discount
   - Approve/Cancel любых документов
   - Изменение цен (PriceSettings)
   - Reallocation платежей
   - Складские движения (Issue, WriteOff, Adjustment)
   - Закупки и компенсации

2. **Изменение данных студента:**
   - Смена grade, transport zone
   - Смена статуса (Student → Inactive и обратно)

3. **Финансовые операции:**
   - Все payments, credits, compensations

**Формат JSON полей:**

```json
{
  "old_values": {
    "status": "PartiallyPaid",
    "paid_total": 10000.00,
    "amount_due": 5000.00
  },
  "new_values": {
    "status": "Paid",
    "paid_total": 15000.00,
    "amount_due": 0.00
  }
}
```

---

#### 3.5.3. Attachment (Вложения)

**Таблица: `attachments`**

```sql
CREATE TABLE attachments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    
    entity_type VARCHAR(100) NOT NULL,
    entity_id BIGINT NOT NULL,
    
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_size BIGINT,  -- in bytes
    mime_type VARCHAR(100),
    
    attachment_type VARCHAR(100),  -- 'Quotation', 'Receipt', 'Proof', 'Invoice PDF', etc.
    
    uploaded_by BIGINT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (uploaded_by) REFERENCES users(id),
    
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_uploaded_by (uploaded_by)
);
```

**Где используются вложения:**

- **PurchaseOrder**: quotation, supplier documents
- **ExpenseClaim**: receipt/proof images
- **CompensationPayout**: payment confirmation
- **Payment** (student): optional payment screenshot
- **Invoice/Receipt**: generated PDFs

---

## 4. БИЗНЕС-ЛОГИКА И АЛГОРИТМЫ

### 4.1. Payment Allocation Algorithm (Распределение платежа)

**Приоритеты распределения:**

1. **Must be paid in full first** (по порядку создания invoice):
   - UniformBundle
   - Admission
   - Interview
   - DiaryBooks

2. **Allow partial payment** (по порядку создания invoice):
   - SchoolFee
   - Transport

3. **Excess → Credit Balance**

**Псевдокод:**

```python
def allocate_payment(student_id, payment_amount):
    # 1. Get existing credit
    credit = CreditBalance.get_or_create(student_id=student_id)
    
    # 2. Apply existing credit first
    total_to_allocate = payment_amount + credit.balance_amount
    
    # 3. Get all open invoice lines (unpaid or partially paid)
    lines = InvoiceLine.objects.filter(
        invoice__student_id=student_id,
        invoice__status__in=['Issued', 'PartiallyPaid']
    ).order_by(
        # Priority: must_be_paid_in_full first
        Case(When(must_be_paid_in_full=True, then=0), default=1),
        # Then by invoice creation date
        'invoice__created_at',
        'invoice__id',
        'id'
    )
    
    allocations = []
    remaining = total_to_allocate
    
    for line in lines:
        if remaining <= 0:
            break
        
        line_remaining = line.line_total - line.paid_amount
        
        if line.must_be_paid_in_full:
            # Must allocate full amount or nothing
            if remaining >= line_remaining:
                allocate = line_remaining
            else:
                continue  # Skip this line for now
        else:
            # Can allocate partial
            allocate = min(remaining, line_remaining)
        
        if allocate > 0:
            allocations.append({
                'invoice_line_id': line.id,
                'invoice_id': line.invoice_id,
                'line_type': line.line_type,
                'allocated_amount': allocate
            })
            
            line.paid_amount += allocate
            line.remaining_amount = line.line_total - line.paid_amount
            line.save()
            
            remaining -= allocate
    
    # 4. Update invoice statuses
    update_invoice_statuses(student_id)
    
    # 5. Remaining goes to credit
    if remaining > 0:
        credit.balance_amount = remaining
    else:
        credit.balance_amount = 0
    credit.save()
    
    return allocations, credit.balance_amount
```

---

### 4.2. Invoice Status Calculation

**Логика:**

```python
def calculate_invoice_status(invoice):
    total = invoice.total
    paid = invoice.paid_total
    
    if paid == 0:
        return 'Issued'
    elif paid >= total:
        return 'Paid'
    else:
        return 'PartiallyPaid'

def update_invoice_totals_and_status(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    
    # 1. Recalculate totals from lines
    lines = invoice.lines.all()
    
    invoice.subtotal = sum(line.line_total for line in lines)
    invoice.total = invoice.subtotal - invoice.discount_total
    invoice.paid_total = sum(line.paid_amount for line in lines)
    invoice.amount_due = invoice.total - invoice.paid_total
    
    # 2. Recalculate status
    invoice.status = calculate_invoice_status(invoice)
    
    invoice.save()
```

---

### 4.3. Student Status Calculation

**Enrolled Status Logic:**

```python
def update_student_enrollment_status(student_id):
    student = Student.objects.get(id=student_id)
    
    if student.status == 'Inactive':
        return  # Don't change inactive students
    
    # Get current term
    current_term = Term.objects.get(status='Active')
    
    # Get school fee line for current term
    school_fee_lines = InvoiceLine.objects.filter(
        invoice__student_id=student_id,
        invoice__term_id=current_term.id,
        line_type='SchoolFee'
    )
    
    if school_fee_lines.exists():
        # Check if any payment made
        if any(line.paid_amount > 0 for line in school_fee_lines):
            student.status = 'Enrolled'
        else:
            student.status = 'Student'
    else:
        student.status = 'Student'
    
    student.save()
```

---

### 4.4. Procurement Debt Calculation

**Formula:**

```
Debt = ReceivedValue - PaidTotal

Where:
- ReceivedValue = sum(GRN lines: quantity_received * unit_price)
- PaidTotal = sum(ProcurementPayments where status='Posted')
```

**Implementation:**

```python
def recalculate_po_debt(po_id):
    po = PurchaseOrder.objects.get(id=po_id)
    
    # 1. Calculate received value
    received_value = 0
    for line in po.lines.all():
        received_value += line.quantity_received * line.unit_price
    
    # 2. Calculate paid total
    paid_total = ProcurementPayment.objects.filter(
        po_id=po_id,
        status='Posted'
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # 3. Update PO
    po.received_value = received_value
    po.paid_total = paid_total
    po.debt_amount = received_value - paid_total
    po.save()
```

**Important:**
- Debt is calculated from **received** value, not **expected** value
- This means if ordered 100 items but received 90, debt is based on 90

---

### 4.5. Employee Compensation Balance Calculation

**Formula:**

```
Balance = TotalApproved - TotalPaid

Where:
- TotalApproved = sum(ExpenseClaims where status='Approved' or 'PartiallyPaid' or 'Paid')
- TotalPaid = sum(CompensationPayouts)
```

**Implementation:**

```python
def update_employee_balance(employee_id):
    # 1. Calculate total approved
    total_approved = ExpenseClaim.objects.filter(
        employee_id=employee_id,
        status__in=['Approved', 'PartiallyPaid', 'Paid']
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # 2. Calculate total paid
    total_paid = CompensationPayout.objects.filter(
        employee_id=employee_id
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # 3. Update or create balance
    balance, created = EmployeeBalance.objects.get_or_create(
        employee_id=employee_id
    )
    
    balance.total_approved = total_approved
    balance.total_paid = total_paid
    balance.balance = total_approved - total_paid
    balance.save()
    
    return balance
```

**Note:** 
- Positive balance = school owes employee
- Negative balance = employee owes school (advance)

---

## 5. ДИАГРАММЫ СОСТОЯНИЙ И ЖИЗНЕННЫЕ ЦИКЛЫ

### 5.1. Student Status Lifecycle

```
┌──────┐
│ Lead │ (optional starting point)
└──┬───┘
   │
   │ convert_to_student()
   ↓
┌─────────┐
│ Student │ (main starting point)
└────┬────┘
     │
     │ receive_payment(school_fee)
     ↓
┌──────────┐
│ Enrolled │
└────┬─────┘
     │
     │ mark_inactive()
     ↓
┌──────────┐
│ Inactive │
└────┬─────┘
     │
     │ reactivate()
     ↓
┌─────────┐
│ Student │ (back to active)
└─────────┘
```

**State Transitions:**

| From | To | Trigger | Conditions |
|------|----|---------|-----------| 
| Lead | Student | Convert to student | Manual action |
| Student | Enrolled | Payment received | Payment applied to school fee |
| Enrolled | Student | New term started | No payment in new term yet |
| Student/Enrolled | Inactive | Mark inactive | Manual action |
| Inactive | Student | Reactivate | Manual action |

---

### 5.2. Invoice Status Lifecycle

```
┌───────┐
│ Draft │
└───┬───┘
    │
    │ issue()
    ↓
┌────────┐
│ Issued │
└────┬───┘
     │
     │ receive_payment() [partial]
     ↓
┌──────────────────┐
│ PartiallyPaid    │←──┐
└────┬─────────────┘   │
     │                 │
     │ receive_payment() [partial]
     │─────────────────┘
     │
     │ receive_payment() [full]
     ↓
┌──────┐
│ Paid │
└──────┘

Any status can go to:
     │ cancel()
     ↓
┌───────────┐
│ Cancelled │
└───────────┘
```

---

### 5.3. Payment Status Lifecycle

```
┌────────┐
│ Posted │ (created and active)
└───┬────┘
    │
    │ cancel_payment()
    ↓
┌───────────┐
│ Cancelled │ (voided, allocations reversed)
└───────────┘
```

**Note:** Payments cannot be edited, only cancelled.

---

### 5.4. PurchaseOrder Status Lifecycle

```
┌───────┐
│ Draft │
└───┬───┘
    │
    │ submit_order()
    ↓
┌─────────┐
│ Ordered │
└────┬────┘
     │
     │ receive_goods() [partial]
     ↓
┌──────────────────────┐
│ PartiallyReceived    │←──┐
└────┬─────────────────┘   │
     │                     │
     │ receive_goods() [partial]
     │─────────────────────┘
     │
     │ receive_goods() [complete]
     ↓
┌──────────┐
│ Received │
└──────────┘

Any status can go to:
     │ cancel()
     ↓
┌───────────┐
│ Cancelled │
└───────────┘
```

---

### 5.5. IssueRequest Status Lifecycle

```
┌───────┐
│ Draft │
└───┬───┘
    │
    │ submit()
    ↓
┌──────────────────┐
│ PendingApproval  │
└────┬─────────────┘
     │
     │ approve()
     ↓
┌──────────┐
│ Approved │
└────┬─────┘
     │
     │ issue_items() [partial]
     ↓
┌──────────────────┐
│ PartiallyIssued  │←──┐
└────┬─────────────┘   │
     │                 │
     │ issue_items() [partial]
     │─────────────────┘
     │
     │ issue_items() [complete]
     ↓
┌────────┐
│ Issued │
└────────┘

From PendingApproval or Approved:
     │ cancel()
     ↓
┌───────────┐
│ Cancelled │
└───────────┘
```

---

### 5.6. ExpenseClaim Status Lifecycle

```
┌───────┐
│ Draft │
└───┬───┘
    │
    │ submit()
    ↓
┌──────────────────┐
│ PendingApproval  │
└────┬─────────────┘
     │
     │ approve()          │ reject()
     ↓                    ↓
┌──────────┐         ┌──────────┐
│ Approved │         │ Rejected │
└────┬─────┘         └──────────┘
     │
     │ create_payout() [partial]
     ↓
┌──────────────────┐
│ PartiallyPaid    │←──┐
└────┬─────────────┘   │
     │                 │
     │ create_payout() [partial]
     │─────────────────┘
     │
     │ create_payout() [complete]
     ↓
┌──────┐
│ Paid │
└──────┘

From any status:
     │ cancel()
     ↓
┌───────────┐
│ Cancelled │
└───────────┘
```

---

## 6. ПРАВИЛА ВАЛИДАЦИИ И ОГРАНИЧЕНИЯ ЦЕЛОСТНОСТИ

### 6.1. Student Validations

**При создании/изменении:**

```python
STUDENT_VALIDATIONS = {
    'surname': {
        'required': True,
        'min_length': 1,
        'max_length': 200,
        'pattern': r'^[a-zA-Z\s\-\']+$'  # Letters, spaces, hyphens, apostrophes
    },
    'first_name': {
        'required': True,
        'min_length': 1,
        'max_length': 200,
        'pattern': r'^[a-zA-Z\s\-\']+$'
    },
    'guardian_phone': {
        'required': True,
        'pattern': r'^\+254[0-9]{9}$'  # Kenyan format
    },
    'guardian_name': {
        'required': True,
        'min_length': 1,
        'max_length': 200
    },
    'grade': {
        'required': True,
        'choices': ['PP1', 'PP2', 'Grade 1', 'Grade 2', 'Grade 3', 
                    'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8']
    },
    'current_uniform_size': {
        'choices': ['6y', '8y', '10y', '12y', '14y', '16y']
    }
}
```

**Business Rules:**

1. Cannot change grade if there's an unpaid invoice for current term
2. Cannot set status to Inactive if there's unpaid debt (warning only, not blocking)
3. Cannot delete student (only mark Inactive)

---

### 6.2. Invoice/Payment Validations

**Invoice:**

```python
INVOICE_VALIDATIONS = {
    'student_id': {'required': True, 'exists_in': 'students'},
    'term_id': {'required': True, 'exists_in': 'terms'},
    'total': {'min': 0},
    'discount_total': {'min': 0, 'max': 'subtotal'},
    
    # Business rules
    'term_must_not_be_closed': True,
    'student_must_be_active': True  # Warning only
}
```

**Payment:**

```python
PAYMENT_VALIDATIONS = {
    'student_id': {'required': True, 'exists_in': 'students'},
    'amount': {'required': True, 'min': 0.01},
    'payment_date': {'required': True, 'max': 'today'},
    'reference_number': {'required': True, 'min_length': 1},
    
    # Business rules
    'cannot_create_payment_for_cancelled_invoice': True
}
```

**Cancel Payment:**

```python
CANCEL_PAYMENT_VALIDATIONS = {
    'cancelled_reason': {'required': True, 'min_length': 10},
    'only_super_admin_can_cancel': True,
    'cannot_cancel_already_cancelled': True
}
```

---

### 6.3. Inventory Validations

**Stock Movement:**

```python
STOCK_MOVEMENT_VALIDATIONS = {
    'item_id': {'required': True, 'exists_in': 'items'},
    'quantity_delta': {'required': True, 'not_zero': True},
    
    # Critical business rule
    'result_cannot_be_negative': lambda movement: (
        get_current_stock(movement.item_id) + movement.quantity_delta >= 0
    ),
    
    # For Issue
    'destination_required_for_issue': True,
    
    # For WriteOff/Adjustment
    'reason_required_for_writeoff_adjustment': True,
    'approval_required': True
}
```

**Issue Request:**

```python
ISSUE_REQUEST_VALIDATIONS = {
    'destination': {'required': True, 'min_length': 1},
    'lines': {'min_count': 1},
    
    # Line validations
    'line.item_id': {'required': True, 'exists_in': 'items'},
    'line.quantity_requested': {'required': True, 'min': 0.001},
    
    # Business rules
    'cannot_approve_own_request': True,
    'cannot_issue_more_than_stock': True  # At time of issue
}
```

---

### 6.4. Procurement Validations

**Purchase Order:**

```python
PURCHASE_ORDER_VALIDATIONS = {
    'supplier_name': {'required': True, 'min_length': 1},
    'order_date': {'required': True},
    'lines': {'min_count': 1},
    
    # Line validations
    'line.quantity_expected': {'required': True, 'min': 0.001},
    'line.unit_price': {'required': True, 'min': 0.01},
    
    # Business rules
    'cannot_edit_received_po': True,
    'attachment_recommended': True  # Warning only
}
```

**Goods Received:**

```python
GOODS_RECEIVED_VALIDATIONS = {
    'po_id': {'required': True, 'exists_in': 'purchase_orders'},
    'received_date': {'required': True, 'max': 'today'},
    'lines': {'min_count': 1},
    
    # Line validations
    'line.quantity_received': {'required': True, 'min': 0.001},
    
    # Business rules
    'quantity_received_cannot_exceed_expected': True,
    'approval_required': True,
    'cannot_approve_own_grn': True
}
```

---

### 6.5. Compensation Validations

**Expense Claim:**

```python
EXPENSE_CLAIM_VALIDATIONS = {
    'employee_id': {'required': True, 'exists_in': 'users'},
    'amount': {'required': True, 'min': 0.01},
    'expense_category': {'required': True, 'exists_in': 'expense_categories'},
    'description': {'required': True, 'min_length': 10},
    'expense_date': {'required': True, 'max': 'today'},
    
    # Proof validations
    'proof_attachment_or_no_proof_reason': lambda claim: (
        claim.proof_provided or claim.no_proof_reason
    ),
    
    # Business rules
    'approval_required': True,
    'only_super_admin_can_approve': True,
    'cannot_approve_own_claim': True
}
```

---

### 6.6. Database Integrity Constraints

**Foreign Keys:**

All foreign keys should have explicit ON DELETE behavior:

- Most relations: `ON DELETE RESTRICT` (prevent deletion)
- Child records: `ON DELETE CASCADE` (invoice_lines, payment_allocations, etc.)
- Soft-delete entities: No ON DELETE (handle in application)

**Unique Constraints:**

```sql
-- Document numbers UNIQUE per table
UNIQUE (invoice_number)
UNIQUE (payment_number)
UNIQUE (po_number)
etc.

-- Business uniqueness
UNIQUE (year, term_number)  -- terms
UNIQUE (student_id)  -- credit_balances
UNIQUE (employee_id)  -- employee_balances
```

**Check Constraints:**

```sql
-- Positive amounts
CHECK (amount >= 0)
CHECK (quantity > 0)

-- Logical constraints
CHECK (total = subtotal - discount_total)
CHECK (amount_due = total - paid_total)
```

---

## 7. ДЕТАЛЬНЫЕ БИЗНЕС-ПРОЦЕССЫ

### 7.1. Process: Start New Term

**Actors:** Admin, SuperAdmin

**Preconditions:**
- User has Admin or SuperAdmin role
- Previous term exists (for price copying)

**Steps:**

1. **Create Term Record**
   ```python
   term = Term.create(
       year=2026,
       term_number=1,
       display_name='2026-T1',
       status='Draft'
   )
   ```

2. **Copy or Set Pricing**
   - If previous term exists:
     ```python
     prev_term = Term.get_latest()
     
     # Copy school fees
     for price in prev_term.price_settings:
         PriceSetting.create(
             term_id=term.id,
             grade=price.grade,
             school_fee_amount=price.school_fee_amount
         )
     
     # Copy transport pricing
     for transport in prev_term.transport_pricing:
         TransportPricing.create(
             term_id=term.id,
             zone_id=transport.zone_id,
             transport_fee_amount=transport.transport_fee_amount
         )
     ```
   - Admin can modify prices before activating term

3. **Activate Term**
   ```python
   term.status = 'Active'
   term.save()
   
   # Deactivate previous term
   prev_term.status = 'Closed'
   prev_term.save()
   ```

4. **Generate Invoices**
   ```python
   active_students = Student.filter(
       status__in=['Student', 'Enrolled']
   )
   
   for student in active_students:
       invoice = Invoice.create(
           student_id=student.id,
           term_id=term.id,
           invoice_type='Term',
           status='Issued'
       )
       
       # Add school fee line
       price = PriceSetting.get(term_id=term.id, grade=student.grade)
       InvoiceLine.create(
           invoice_id=invoice.id,
           line_type='SchoolFee',
           description=f'School Fee - {student.grade}',
           quantity=1,
           unit_price=price.school_fee_amount,
           line_total=price.school_fee_amount,
           must_be_paid_in_full=False,
           allow_partial_payment=True
       )
       
       # Add transport line if enabled
       if student.transport_enabled:
           transport = TransportPricing.get(
               term_id=term.id, 
               zone_id=student.transport_zone_id
           )
           InvoiceLine.create(
               invoice_id=invoice.id,
               line_type='Transport',
               description=f'Transport - {transport.zone.zone_name}',
               quantity=1,
               unit_price=transport.transport_fee_amount,
               line_total=transport.transport_fee_amount,
               must_be_paid_in_full=False,
               allow_partial_payment=True
           )
       
       # Add admission fee if first term
       if not student.admission_fee_settled:
           admission_fee = FixedFee.get(fee_type='Admission')
           InvoiceLine.create(
               invoice_id=invoice.id,
               line_type='Admission',
               description='Admission Fee',
               quantity=1,
               unit_price=admission_fee.amount,
               line_total=admission_fee.amount,
               must_be_paid_in_full=True,
               allow_partial_payment=False
           )
       
       # Calculate invoice totals
       invoice.recalculate_totals()
       invoice.save()
   ```

5. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='CREATE_TERM',
       entity_type='Term',
       entity_id=term.id,
       entity_identifier=term.display_name,
       comment=f'Generated {len(active_students)} invoices'
   )
   ```

**Postconditions:**
- New term created and activated
- Previous term closed
- All active students have invoices for new term

---

### 7.2. Process: Receive Payment

**Actors:** Admin, SuperAdmin

**Preconditions:**
- Student exists
- Payment amount > 0
- Payment reference provided

**Steps:**

1. **Validate Input**
   ```python
   if payment_amount <= 0:
       raise ValidationError("Payment amount must be positive")
   
   if not reference_number:
       raise ValidationError("M-Pesa reference required")
   ```

2. **Create Payment Record**
   ```python
   payment = Payment.create(
       student_id=student_id,
       amount=payment_amount,
       payment_date=date.today(),
       payment_method='M-Pesa',
       reference_number=reference_number,
       status='Posted',
       created_by=current_user.id
   )
   ```

3. **Run Allocation Algorithm**
   ```python
   allocations, final_credit = allocate_payment(student_id, payment_amount)
   
   payment.allocation_details = json.dumps(allocations)
   payment.save()
   ```

4. **Update Invoice Lines and Invoices**
   ```python
   for allocation in allocations:
       line = InvoiceLine.get(id=allocation['invoice_line_id'])
       line.paid_amount += allocation['allocated_amount']
       line.remaining_amount = line.line_total - line.paid_amount
       line.save()
   
   # Update invoice totals and statuses
   affected_invoices = set(a['invoice_id'] for a in allocations)
   for invoice_id in affected_invoices:
       update_invoice_totals_and_status(invoice_id)
   ```

5. **Update Credit Balance**
   ```python
   credit = CreditBalance.get_or_create(student_id=student_id)
   old_balance = credit.balance_amount
   credit.balance_amount = final_credit
   credit.save()
   
   if final_credit != old_balance:
       CreditTransaction.create(
           student_id=student_id,
           transaction_type='Increase' if final_credit > old_balance else 'Decrease',
           amount=abs(final_credit - old_balance),
           balance_before=old_balance,
           balance_after=final_credit,
           related_payment_id=payment.id,
           description=f'Payment {payment.payment_number}'
       )
   ```

6. **Update Student Status**
   ```python
   update_student_enrollment_status(student_id)
   ```

7. **Generate Receipt**
   ```python
   receipt = Receipt.create(
       payment_id=payment.id,
       student_id=student_id,
       receipt_date=date.today(),
       amount=payment_amount,
       status='Valid'
   )
   
   # Generate PDF
   pdf_path = generate_receipt_pdf(receipt)
   receipt.pdf_path = pdf_path
   receipt.save()
   
   payment.receipt_number = receipt.receipt_number
   payment.save()
   ```

8. **Check Uniform Fulfillment Activation**
   ```python
   # If any UniformBundle line was fully paid, create fulfillment
   for allocation in allocations:
       line = InvoiceLine.get(id=allocation['invoice_line_id'])
       
       if (line.line_type == 'UniformBundle' and 
           line.paid_amount >= line.line_total and
           not UniformFulfillment.exists(invoice_line_id=line.id)):
           
           create_uniform_fulfillment(
               student_id=student_id,
               invoice_line_id=line.id,
               uniform_size=line.uniform_size
           )
   ```

9. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='CREATE_PAYMENT',
       entity_type='Payment',
       entity_id=payment.id,
       entity_identifier=payment.payment_number,
       new_values=json.dumps({
           'student': student.full_name,
           'amount': payment_amount,
           'allocations': len(allocations),
           'credit': final_credit
       })
   )
   ```

**Postconditions:**
- Payment created and allocated
- Invoice statuses updated
- Credit balance updated
- Receipt generated
- Student enrollment status updated
- Uniform fulfillment created if applicable

---

### 7.3. Process: Sell Uniform Bundle

**Actors:** Admin, SuperAdmin

**Preconditions:**
- Student exists and is active
- Uniform size selected

**Steps:**

1. **Get/Create Sales Invoice**
   ```python
   current_term = Term.get_active()
   
   # Check for existing sales invoice for this term
   invoice = Invoice.get_or_none(
       student_id=student_id,
       term_id=current_term.id,
       invoice_type='Sales',
       status__in=['Draft', 'Issued', 'PartiallyPaid']
   )
   
   if not invoice:
       invoice = Invoice.create(
           student_id=student_id,
           term_id=current_term.id,
           invoice_type='Sales',
           status='Issued',
           created_by=current_user.id
       )
   ```

2. **Get Bundle Price**
   ```python
   # Fixed price for uniform bundle (could be in settings)
   UNIFORM_BUNDLE_PRICE = 5000.00  # KES
   ```

3. **Add Invoice Line**
   ```python
   InvoiceLine.create(
       invoice_id=invoice.id,
       line_type='UniformBundle',
       description=f'School Uniform Bundle - Size {uniform_size}',
       quantity=1,
       unit_price=UNIFORM_BUNDLE_PRICE,
       line_total=UNIFORM_BUNDLE_PRICE,
       uniform_size=uniform_size,
       must_be_paid_in_full=True,
       allow_partial_payment=False
   )
   ```

4. **Update Invoice Totals**
   ```python
   invoice.recalculate_totals()
   invoice.save()
   ```

5. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='SELL_UNIFORM',
       entity_type='InvoiceLine',
       entity_id=line.id,
       entity_identifier=f'{student.full_name} - {uniform_size}',
       new_values=json.dumps({
           'invoice_number': invoice.invoice_number,
           'size': uniform_size,
           'amount': UNIFORM_BUNDLE_PRICE
       })
   )
   ```

**Postconditions:**
- Invoice line created for uniform bundle
- Invoice totals updated
- Student can see outstanding balance
- Fulfillment will be created after 100% payment

---

### 7.4. Process: Create Uniform Fulfillment (Auto-triggered)

**Trigger:** UniformBundle invoice line fully paid

**Steps:**

1. **Create Fulfillment Record**
   ```python
   fulfillment = UniformFulfillment.create(
       student_id=student_id,
       invoice_line_id=line.id,
       uniform_size=line.uniform_size,
       status='Pending'
   )
   ```

2. **Determine Required Items**
   ```python
   # Get bundle definition for size
   bundle_def = UNIFORM_BUNDLE_DEFINITION[line.uniform_size]
   
   for component in bundle_def:
       # Find item SKU
       item = Item.get(
           is_uniform_item=True,
           uniform_component=component['component'],
           uniform_size=component['size']
       )
       
       UniformFulfillmentItem.create(
           fulfillment_id=fulfillment.id,
           item_id=item.id,
           quantity_required=component['qty'],
           quantity_issued=0,
           quantity_pending=component['qty']
       )
   ```

3. **Log Audit**
   ```python
   AuditLog.create(
       user_id=SYSTEM_USER_ID,
       action='CREATE_FULFILLMENT',
       entity_type='UniformFulfillment',
       entity_id=fulfillment.id,
       entity_identifier=f'{student.full_name} - {line.uniform_size}',
       comment='Auto-created after 100% payment'
   )
   ```

**Postconditions:**
- Fulfillment record created with pending items
- Appears in "Pending Fulfillments" screen
- Ready for warehouse staff to issue items

---

### 7.5. Process: Issue Uniform Items

**Actors:** Admin (warehouse staff)

**Preconditions:**
- UniformFulfillment exists in Pending or Partial status
- Items are in stock

**Steps:**

1. **Check Stock Availability**
   ```python
   fulfillment = UniformFulfillment.get(id=fulfillment_id)
   pending_items = fulfillment.items.filter(quantity_pending__gt=0)
   
   available_items = []
   for item_record in pending_items:
       stock = StockBalance.get(item_id=item_record.item_id)
       
       can_issue = min(item_record.quantity_pending, stock.quantity_on_hand)
       if can_issue > 0:
           available_items.append({
               'item_record': item_record,
               'can_issue': can_issue
           })
   ```

2. **Issue Available Items**
   ```python
   with transaction.atomic():
       for available in available_items:
           item_record = available['item_record']
           qty = available['can_issue']
           
           # Create stock movement
           movement = create_stock_movement(
               item_id=item_record.item_id,
               movement_type='Issue',
               quantity_delta=-qty,
               related_document_type='UniformFulfillment',
               related_document_id=fulfillment.id,
               destination=f'Student: {fulfillment.student.full_name}',
               created_by=current_user.id,
               approved_by=current_user.id,
               movement_date=date.today()
           )
           
           # Update fulfillment item
           item_record.quantity_issued += qty
           item_record.quantity_pending -= qty
           item_record.issued_by = current_user.id
           item_record.issued_at = now()
           item_record.save()
   ```

3. **Update Fulfillment Status**
   ```python
   total_required = sum(i.quantity_required for i in fulfillment.items.all())
   total_issued = sum(i.quantity_issued for i in fulfillment.items.all())
   
   if total_issued >= total_required:
       fulfillment.status = 'Fulfilled'
   elif total_issued > 0:
       fulfillment.status = 'Partial'
   else:
       fulfillment.status = 'Pending'
   
   fulfillment.save()
   ```

4. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='ISSUE_UNIFORM',
       entity_type='UniformFulfillment',
       entity_id=fulfillment.id,
       entity_identifier=f'{fulfillment.student.full_name}',
       new_values=json.dumps({
           'items_issued': len(available_items),
           'status': fulfillment.status
       })
   )
   ```

**Postconditions:**
- Stock reduced for issued items
- Fulfillment item quantities updated
- Fulfillment status updated
- Stock movements recorded

---

### 7.6. Process: Create Purchase Order

**Actors:** Admin, SuperAdmin

**Preconditions:**
- User has appropriate role
- Supplier information provided
- At least one line item

**Steps:**

1. **Create PO Header**
   ```python
   po = PurchaseOrder.create(
       supplier_name=supplier_name,
       supplier_contact=supplier_contact,
       order_date=date.today(),
       expected_delivery_date=expected_delivery,
       track_to_warehouse=track_to_warehouse,
       status='Draft',
       created_by=current_user.id
   )
   ```

2. **Add Line Items**
   ```python
   for line_data in line_items:
       POLine.create(
           po_id=po.id,
           item_id=line_data.get('item_id'),  # nullable
           description=line_data['description'],
           quantity_expected=line_data['quantity'],
           unit_price=line_data['unit_price'],
           line_total=line_data['quantity'] * line_data['unit_price'],
           line_order=line_data.get('order', 0)
       )
   ```

3. **Calculate Totals**
   ```python
   po.expected_total = sum(line.line_total for line in po.lines.all())
   po.save()
   ```

4. **Upload Attachments**
   ```python
   if quotation_file:
       Attachment.create(
           entity_type='PurchaseOrder',
           entity_id=po.id,
           file_name=quotation_file.name,
           file_path=save_file(quotation_file),
           attachment_type='Quotation',
           uploaded_by=current_user.id
       )
   ```

5. **Submit Order**
   ```python
   po.status = 'Ordered'
   po.save()
   ```

6. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='CREATE_PO',
       entity_type='PurchaseOrder',
       entity_id=po.id,
       entity_identifier=po.po_number,
       new_values=json.dumps({
           'supplier': supplier_name,
           'lines_count': len(line_items),
           'total': float(po.expected_total)
       })
   )
   ```

**Postconditions:**
- PO created with lines
- PO in Ordered status
- Attachments uploaded
- Ready for receiving

---

### 7.7. Process: Receive Goods (GRN)

**Actors:** Admin

**Preconditions:**
- PO exists in Ordered or PartiallyReceived status
- Goods physically received

**Steps:**

1. **Create GRN**
   ```python
   grn = GoodsReceivedNote.create(
       po_id=po_id,
       received_date=date.today(),
       received_by=current_user.id,
       status='Draft'
   )
   ```

2. **Add Received Lines**
   ```python
   for po_line in selected_lines:
       GRNLine.create(
           grn_id=grn.id,
           po_line_id=po_line.id,
           item_id=po_line.item_id,
           quantity_received=received_quantities[po_line.id]
       )
   ```

3. **Request Approval**
   ```python
   grn.status = 'PendingApproval'  # In UI, or directly approve if admin
   grn.save()
   ```

4. **Approve GRN** (separate action or immediate)
   ```python
   def approve_grn(grn_id, approving_user):
       grn = GoodsReceivedNote.get(id=grn_id)
       po = grn.purchase_order
       
       if approving_user.id == grn.received_by:
           raise ValidationError("Cannot approve own GRN")
       
       with transaction.atomic():
           # Create stock movements
           if po.track_to_warehouse:
               for grn_line in grn.lines.all():
                   if grn_line.item_id:
                       create_stock_movement(
                           item_id=grn_line.item_id,
                           movement_type='Receive',
                           quantity_delta=grn_line.quantity_received,
                           related_document_type='GRN',
                           related_document_id=grn.id,
                           created_by=grn.received_by,
                           approved_by=approving_user.id,
                           movement_date=grn.received_date
                       )
           
           # Update PO lines
           for grn_line in grn.lines.all():
               po_line = grn_line.po_line
               po_line.quantity_received += grn_line.quantity_received
               po_line.save()
           
           # Recalculate PO status and values
           recalculate_po_debt(po.id)
           
           # Update PO status
           all_lines = po.lines.all()
           if all(line.quantity_received >= line.quantity_expected for line in all_lines):
               po.status = 'Received'
           elif any(line.quantity_received > 0 for line in all_lines):
               po.status = 'PartiallyReceived'
           po.save()
           
           # Approve GRN
           grn.status = 'Approved'
           grn.approved_by = approving_user.id
           grn.approved_at = now()
           grn.save()
           
           # Log audit
           AuditLog.create(
               user_id=approving_user.id,
               action='APPROVE_GRN',
               entity_type='GoodsReceivedNote',
               entity_id=grn.id,
               entity_identifier=grn.grn_number
           )
   ```

**Postconditions:**
- GRN created and approved
- Stock increased (if warehouse tracking)
- PO quantities and status updated
- Debt recalculated

---

### 7.8. Process: Record Procurement Payment

**Actors:** Admin, SuperAdmin

**Preconditions:**
- PO exists
- Payment amount > 0

**Steps:**

1. **Create Payment**
   ```python
   payment = ProcurementPayment.create(
       po_id=po_id,
       payment_date=payment_date,
       amount=amount,
       payment_method=method,
       reference_number=reference,
       company_paid=not employee_paid,
       employee_paid_id=employee_id if employee_paid else None,
       status='Posted',
       created_by=current_user.id
   )
   ```

2. **Update PO Debt**
   ```python
   recalculate_po_debt(po_id)
   ```

3. **Auto-create Claim if Employee Paid**
   ```python
   if employee_paid and employee_id:
       claim = ExpenseClaim.create(
           employee_id=employee_id,
           expense_category='Procurement',
           amount=amount,
           description=f'Payment for {po.po_number} - {po.supplier_name}',
           expense_date=payment_date,
           proof_required=True,
           auto_created_from_payment=True,
           related_procurement_payment_id=payment.id,
           status='PendingApproval',
           created_by=current_user.id
       )
       
       # Link payment attachment to claim
       if payment_attachment:
           Attachment.create(
               entity_type='ExpenseClaim',
               entity_id=claim.id,
               file_name=payment_attachment.name,
               file_path=save_file(payment_attachment),
               attachment_type='Proof',
               uploaded_by=current_user.id
           )
   ```

4. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='CREATE_PROCUREMENT_PAYMENT',
       entity_type='ProcurementPayment',
       entity_id=payment.id,
       entity_identifier=payment.payment_number,
       new_values=json.dumps({
           'po': po.po_number,
           'amount': float(amount),
           'employee_paid': employee_paid,
           'claim_created': claim.claim_number if claim else None
       })
   )
   ```

**Postconditions:**
- Payment recorded
- PO debt updated
- Claim auto-created if employee paid
- Ready for claim approval

---

### 7.9. Process: Create and Approve Expense Claim

**Actors:** User (employee), SuperAdmin (approver)

**Preconditions:**
- User is authenticated
- Expense occurred

**Steps (Employee):**

1. **Create Claim**
   ```python
   claim = ExpenseClaim.create(
       employee_id=current_user.id,
       expense_category=category,
       amount=amount,
       description=description,
       expense_date=expense_date,
       proof_required=True,
       status='Draft',
       created_by=current_user.id
   )
   ```

2. **Upload Proof**
   ```python
   if proof_file:
       Attachment.create(
           entity_type='ExpenseClaim',
           entity_id=claim.id,
           file_name=proof_file.name,
           file_path=save_file(proof_file),
           attachment_type='Proof',
           uploaded_by=current_user.id
       )
       claim.proof_provided = True
   else:
       claim.no_proof_reason = no_proof_reason
       claim.proof_provided = False
   
   claim.save()
   ```

3. **Submit for Approval**
   ```python
   claim.status = 'PendingApproval'
   claim.save()
   ```

**Steps (SuperAdmin Approval):**

4. **Review Claim**
   ```python
   claim = ExpenseClaim.get(id=claim_id)
   
   # Validate
   if claim.status != 'PendingApproval':
       raise ValidationError("Claim not in pending status")
   
   if not claim.proof_provided and not claim.no_proof_reason:
       raise ValidationError("Proof or reason required")
   ```

5. **Approve or Reject**
   ```python
   if approve:
       claim.status = 'Approved'
       claim.approved_by = current_user.id
       claim.approved_at = now()
       claim.remaining_amount = claim.amount
       claim.save()
       
       # Update employee balance
       update_employee_balance(claim.employee_id)
       
       action = 'APPROVE_CLAIM'
   else:
       claim.status = 'Rejected'
       claim.rejected_by = current_user.id
       claim.rejected_at = now()
       claim.rejection_reason = rejection_reason
       claim.save()
       
       action = 'REJECT_CLAIM'
   ```

6. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action=action,
       entity_type='ExpenseClaim',
       entity_id=claim.id,
       entity_identifier=claim.claim_number,
       comment=rejection_reason if not approve else None
   )
   ```

**Postconditions:**
- Claim approved or rejected
- Employee balance updated (if approved)
- Ready for payout (if approved)

---

### 7.10. Process: Create Compensation Payout

**Actors:** SuperAdmin only

**Preconditions:**
- Employee has approved unpaid claims
- Payout amount > 0

**Steps:**

1. **Get Employee Claims**
   ```python
   claims = ExpenseClaim.objects.filter(
       employee_id=employee_id,
       status__in=['Approved', 'PartiallyPaid']
   ).order_by('created_at')
   
   total_available = sum(
       claim.amount - claim.paid_amount 
       for claim in claims
   )
   ```

2. **Create Payout**
   ```python
   payout = CompensationPayout.create(
       employee_id=employee_id,
       payout_date=date.today(),
       amount=payout_amount,
       payment_method=method,
       reference_number=reference,
       notes=notes,
       created_by=current_user.id
   )
   ```

3. **Allocate to Claims (oldest first)**
   ```python
   remaining = payout_amount
   
   with transaction.atomic():
       for claim in claims:
           if remaining <= 0:
               break
           
           claim_remaining = claim.amount - claim.paid_amount
           allocate = min(remaining, claim_remaining)
           
           # Create allocation
           PayoutAllocation.create(
               payout_id=payout.id,
               claim_id=claim.id,
               allocated_amount=allocate
           )
           
           # Update claim
           claim.paid_amount += allocate
           claim.remaining_amount = claim.amount - claim.paid_amount
           
           if claim.paid_amount >= claim.amount:
               claim.status = 'Paid'
           else:
               claim.status = 'PartiallyPaid'
           
           claim.save()
           
           remaining -= allocate
       
       # Update employee balance
       update_employee_balance(employee_id)
   ```

4. **Upload Proof**
   ```python
   if proof_file:
       Attachment.create(
           entity_type='CompensationPayout',
           entity_id=payout.id,
           file_name=proof_file.name,
           file_path=save_file(proof_file),
           attachment_type='Payment Proof',
           uploaded_by=current_user.id
       )
   ```

5. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='CREATE_PAYOUT',
       entity_type='CompensationPayout',
       entity_id=payout.id,
       entity_identifier=payout.payout_number,
       new_values=json.dumps({
           'employee': employee.full_name,
           'amount': float(payout_amount),
           'claims_paid': len([a for a in payout.allocations.all()])
       })
   )
   ```

**Postconditions:**
- Payout created
- Claims updated (paid or partially paid)
- Employee balance reduced
- Proof attached

---

### 7.11. Process: Issue Stock by Request

**Actors:** User (requester), Admin (approver/issuer)

**Preconditions:**
- User authenticated
- Items exist in system

**Steps (Requester):**

1. **Create Request**
   ```python
   request = IssueRequest.create(
       requested_by=current_user.id,
       destination=destination,
       request_date=date.today(),
       status='Draft'
   )
   ```

2. **Add Line Items**
   ```python
   for item_data in items:
       IssueRequestLine.create(
           request_id=request.id,
           item_id=item_data['item_id'],
           quantity_requested=item_data['quantity'],
           quantity_pending=item_data['quantity']
       )
   ```

3. **Submit Request**
   ```python
   request.status = 'PendingApproval'
   request.save()
   ```

**Steps (Admin Approval):**

4. **Review and Approve**
   ```python
   request = IssueRequest.get(id=request_id)
   
   if current_user.id == request.requested_by:
       raise ValidationError("Cannot approve own request")
   
   request.status = 'Approved'
   request.approved_by = current_user.id
   request.approved_at = now()
   request.save()
   ```

**Steps (Admin Issue):**

5. **Check Stock and Issue**
   ```python
   with transaction.atomic():
       for line in request.lines.all():
           stock = StockBalance.get(item_id=line.item_id)
           
           # Determine how much can be issued
           can_issue = min(line.quantity_pending, stock.quantity_on_hand)
           
           if can_issue > 0:
               # Create stock movement
               create_stock_movement(
                   item_id=line.item_id,
                   movement_type='Issue',
                   quantity_delta=-can_issue,
                   related_document_type='IssueRequest',
                   related_document_id=request.id,
                   destination=request.destination,
                   created_by=current_user.id,
                   approved_by=current_user.id,
                   movement_date=date.today()
               )
               
               # Update request line
               line.quantity_issued += can_issue
               line.quantity_pending -= can_issue
               line.save()
       
       # Update request status
       total_requested = sum(l.quantity_requested for l in request.lines.all())
       total_issued = sum(l.quantity_issued for l in request.lines.all())
       
       if total_issued >= total_requested:
           request.status = 'Issued'
       elif total_issued > 0:
           request.status = 'PartiallyIssued'
       
       request.save()
   ```

6. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='ISSUE_STOCK',
       entity_type='IssueRequest',
       entity_id=request.id,
       entity_identifier=request.request_number,
       new_values=json.dumps({
           'destination': request.destination,
           'status': request.status
       })
   )
   ```

**Postconditions:**
- Stock issued and reduced
- Request status updated
- Movements logged

---

### 7.12. Process: Fast Issue (Direct Issue without Request)

**Actors:** Admin

**Preconditions:**
- User is Admin
- Items in stock

**Steps:**

1. **Select Items and Quantity**
   ```python
   # UI allows admin to select multiple items directly
   issue_data = [
       {'item_id': 123, 'quantity': 10},
       {'item_id': 456, 'quantity': 5}
   ]
   destination = "Grade 3"
   ```

2. **Validate Stock**
   ```python
   for item_data in issue_data:
       stock = StockBalance.get(item_id=item_data['item_id'])
       if stock.quantity_on_hand < item_data['quantity']:
           raise ValidationError(f"Insufficient stock for item {item_data['item_id']}")
   ```

3. **Create Movements**
   ```python
   with transaction.atomic():
       for item_data in issue_data:
           create_stock_movement(
               item_id=item_data['item_id'],
               movement_type='Issue',
               quantity_delta=-item_data['quantity'],
               related_document_type='DirectIssue',
               related_document_id=None,
               destination=destination,
               reason='Fast issue by Admin',
               created_by=current_user.id,
               approved_by=current_user.id,
               movement_date=date.today()
           )
   ```

4. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='FAST_ISSUE',
       entity_type='StockMovement',
       entity_id=None,
       entity_identifier='Multiple items',
       new_values=json.dumps({
           'destination': destination,
           'items_count': len(issue_data)
       })
   )
   ```

**Postconditions:**
- Stock immediately reduced
- Movements created and logged

---

### 7.13. Process: Write-off (Spoilage/Loss)

**Actors:** User (create), Admin (approve)

**Preconditions:**
- Items exist
- Reason provided

**Steps:**

1. **Create Write-off Request**
   ```python
   writeoff_lines = [
       {'item_id': 789, 'quantity': 3, 'reason': 'Spoiled bread'},
       {'item_id': 790, 'quantity': 1, 'reason': 'Damaged'}
   ]
   ```

2. **Request Approval**
   ```python
   # In UI, user submits for approval
   # Or Admin creates and approves directly
   ```

3. **Admin Approves**
   ```python
   with transaction.atomic():
       for line in writeoff_lines:
           # Validate stock
           stock = StockBalance.get(item_id=line['item_id'])
           if stock.quantity_on_hand < line['quantity']:
               raise ValidationError(f"Insufficient stock for writeoff")
           
           # Create movement
           create_stock_movement(
               item_id=line['item_id'],
               movement_type='WriteOff',
               quantity_delta=-line['quantity'],
               reason=line['reason'],
               created_by=request_user_id,
               approved_by=current_user.id,
               movement_date=date.today()
           )
   ```

4. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='APPROVE_WRITEOFF',
       entity_type='StockMovement',
       entity_id=movement.id,
       entity_identifier=movement.movement_number,
       comment=line['reason']
   )
   ```

**Postconditions:**
- Stock reduced
- Write-off recorded and approved

---

### 7.14. Process: Inventory Count and Adjustment

**Actors:** Admin, SuperAdmin

**Preconditions:**
- Physical count completed

**Steps:**

1. **Enter Count Results**
   ```python
   count_results = {
       item_id_1: {'system': 100, 'actual': 95},
       item_id_2: {'system': 50, 'actual': 52},
       # ...
   }
   ```

2. **Calculate Adjustments**
   ```python
   adjustments = []
   for item_id, counts in count_results.items():
       delta = counts['actual'] - counts['system']
       if delta != 0:
           adjustments.append({
               'item_id': item_id,
               'delta': delta,
               'system': counts['system'],
               'actual': counts['actual']
           })
   ```

3. **Create Adjustment Movements**
   ```python
   with transaction.atomic():
       for adj in adjustments:
           create_stock_movement(
               item_id=adj['item_id'],
               movement_type='Adjustment',
               quantity_delta=adj['delta'],
               reason=f"Inventory count: System {adj['system']}, Actual {adj['actual']}",
               created_by=current_user.id,
               approved_by=approving_admin.id,
               movement_date=date.today()
           )
   ```

4. **Generate Adjustment Report**
   ```python
   report = {
       'count_date': date.today(),
       'counted_by': current_user.full_name,
       'total_items': len(count_results),
       'items_with_variance': len(adjustments),
       'adjustments': adjustments
   }
   ```

5. **Log Audit**
   ```python
   AuditLog.create(
       user_id=approving_admin.id,
       action='INVENTORY_ADJUSTMENT',
       entity_type='StockMovement',
       entity_id=None,
       entity_identifier='Bulk adjustment',
       new_values=json.dumps(report)
   )
   ```

**Postconditions:**
- Stock balances match physical count
- All adjustments documented
- Variance report available

---

### 7.15. Process: Cancel Payment (Reversal)

**Actors:** SuperAdmin only

**Preconditions:**
- Payment exists in Posted status
- Cancellation reason provided

**Steps:**

1. **Validate Cancellation**
   ```python
   payment = Payment.get(id=payment_id)
   
   if payment.status == 'Cancelled':
       raise ValidationError("Payment already cancelled")
   
   if not cancellation_reason or len(cancellation_reason) < 10:
       raise ValidationError("Detailed cancellation reason required")
   ```

2. **Reverse Allocations**
   ```python
   with transaction.atomic():
       allocations = json.loads(payment.allocation_details)
       
       for allocation in allocations:
           line = InvoiceLine.get(id=allocation['invoice_line_id'])
           
           # Reverse payment
           line.paid_amount -= allocation['allocated_amount']
           line.remaining_amount = line.line_total - line.paid_amount
           line.save()
       
       # Update invoice statuses
       affected_invoices = set(a['invoice_id'] for a in allocations)
       for invoice_id in affected_invoices:
           update_invoice_totals_and_status(invoice_id)
   ```

3. **Reverse Credit**
   ```python
   # If payment created credit, reduce it
   credit = CreditBalance.get(student_id=payment.student_id)
   
   # Recalculate from scratch
   student_total_paid = Payment.objects.filter(
       student_id=payment.student_id,
       status='Posted'
   ).exclude(id=payment.id).aggregate(Sum('amount'))['amount__sum'] or 0
   
   student_total_invoiced = Invoice.objects.filter(
       student_id=payment.student_id,
       status__in=['Issued', 'PartiallyPaid', 'Paid']
   ).aggregate(Sum('total'))['total__sum'] or 0
   
   new_credit = max(0, student_total_paid - student_total_invoiced)
   
   credit.balance_amount = new_credit
   credit.save()
   ```

4. **Cancel Payment**
   ```python
   payment.status = 'Cancelled'
   payment.cancelled_reason = cancellation_reason
   payment.cancelled_by = current_user.id
   payment.cancelled_at = now()
   payment.save()
   ```

5. **Void Receipt**
   ```python
   receipt = Receipt.get(payment_id=payment.id)
   receipt.status = 'Voided'
   receipt.voided_reason = cancellation_reason
   receipt.save()
   ```

6. **Reverse Uniform Fulfillment (if applicable)**
   ```python
   # Check if cancellation affects paid uniform bundles
   for allocation in allocations:
       line = InvoiceLine.get(id=allocation['invoice_line_id'])
       
       if line.line_type == 'UniformBundle':
           # If line is now unpaid and items were issued
           if line.paid_amount < line.line_total:
               fulfillment = UniformFulfillment.get_or_none(
                   invoice_line_id=line.id
               )
               
               if fulfillment and fulfillment.status != 'Pending':
                   # Mark as exception (items issued but bundle not fully paid)
                   fulfillment.notes = f"Exception: Payment {payment.payment_number} cancelled"
                   fulfillment.save()
                   
                   # Log alert for admin
                   AuditLog.create(
                       user_id=current_user.id,
                       action='FULFILLMENT_EXCEPTION',
                       entity_type='UniformFulfillment',
                       entity_id=fulfillment.id,
                       entity_identifier=f'{fulfillment.student.full_name}',
                       comment='Items issued but payment cancelled'
                   )
   ```

7. **Log Audit**
   ```python
   AuditLog.create(
       user_id=current_user.id,
       action='CANCEL_PAYMENT',
       entity_type='Payment',
       entity_id=payment.id,
       entity_identifier=payment.payment_number,
       old_values=json.dumps({
           'amount': float(payment.amount),
           'allocations': allocations
       }),
       comment=cancellation_reason
   )
   ```

**Postconditions:**
- Payment cancelled
- All allocations reversed
- Invoice statuses recalculated
- Credit balance adjusted
- Receipt voided
- Exceptions flagged if uniform items issued

---

## 8. ФОРМУЛЫ И РАСЧЕТЫ

### 8.1. Invoice Calculations

**Line Total:**
```
line_total = quantity × unit_price
```

**Invoice Subtotal:**
```
subtotal = Σ(line_total) for all lines
```

**Invoice Total:**
```
total = subtotal - discount_total
```

**Amount Due:**
```
amount_due = total - paid_total
```

**Discount Amount (Percentage):**
```
discount_amount = base_amount × (discount_percentage / 100)
```

**Discount Amount (Fixed):**
```
discount_amount = discount_fixed_value
```

---

### 8.2. Student Balances

**Total Outstanding (Debt):**
```
outstanding = Σ(invoice.amount_due) 
              for all invoices where status IN ('Issued', 'PartiallyPaid')
```

**Credit Balance:**
```
credit = total_paid - total_invoiced

where:
  total_paid = Σ(payment.amount) for status='Posted'
  total_invoiced = Σ(invoice.total) for all non-cancelled invoices
  
If credit < 0: credit = 0 (no negative credit)
```

**Total Owed (Net Position):**
```
net_position = outstanding - credit

If net_position > 0: student owes school
If net_position < 0: school owes student (shouldn't happen with credit system)
If net_position = 0: all settled
```

---

### 8.3. Procurement Debt Calculations

**Expected Total:**
```
expected_total = Σ(po_line.quantity_expected × po_line.unit_price)
```

**Received Value:**
```
received_value = Σ(po_line.quantity_received × po_line.unit_price)
```

**Paid Total:**
```
paid_total = Σ(procurement_payment.amount) 
             where status='Posted'
```

**Debt (Supplier Balance):**
```
debt = received_value - paid_total

If debt > 0: school owes supplier
If debt < 0: supplier owes school (prepayment/credit)
If debt = 0: settled
```

---

### 8.4. Employee Compensation Balances

**Total Approved:**
```
total_approved = Σ(claim.amount) 
                 where status IN ('Approved', 'PartiallyPaid', 'Paid')
```

**Total Paid:**
```
total_paid = Σ(payout.amount)
```

**Balance:**
```
balance = total_approved - total_paid

If balance > 0: school owes employee
If balance < 0: employee owes school (advance)
If balance = 0: settled
```

**Claim Remaining:**
```
claim.remaining_amount = claim.amount - claim.paid_amount
```

---

### 8.5. Stock Calculations

**Stock Balance After Movement:**
```
new_balance = current_balance + quantity_delta

where quantity_delta can be:
  Positive: Receive, Adjustment (increase)
  Negative: Issue, WriteOff, Adjustment (decrease)
```

**Constraint:**
```
new_balance >= 0  (MUST be enforced)
```

**Available for Issue:**
```
available = current_stock_balance - reserved_quantity

(reserved_quantity = items in pending fulfillments, optional)
```

---

### 8.6. Rounding Rules

**All monetary calculations:**
- Round to 2 decimal places
- Method: ROUND_HALF_UP (0.5 rounds up)

**Examples:**
```
10.125 → 10.13
10.124 → 10.12
10.115 → 10.12
```

**Stock quantities:**
- Most items: round to 3 decimal places
- Count items (pcs): round to 0 decimal places

---

## 9. ПРАВА ДОСТУПА И БЕЗОПАСНОСТЬ

### 9.1. Role Permission Matrix

| Action | SuperAdmin | Admin | User | Accountant |
|--------|-----------|-------|------|------------|
| **Students** |
| Create/Edit Student | ✓ | ✓ | ✗ | ✗ |
| View Student | ✓ | ✓ | ✗ | ✓ |
| Delete Student | ✗ | ✗ | ✗ | ✗ |
| Mark Inactive | ✓ | ✓ | ✗ | ✗ |
| **Billing** |
| Create Invoice | ✓ | ✓ | ✗ | ✗ |
| Apply Discount | ✓ | ✓ | ✗ | ✗ |
| Record Payment | ✓ | ✓ | ✗ | ✗ |
| Cancel Payment | ✓ | ✗ | ✗ | ✗ |
| Reallocate Payment | ✓ | ✓* | ✗ | ✗ |
| View Invoices/Payments | ✓ | ✓ | ✗ | ✓ |
| **Terms** |
| Create Term | ✓ | ✓ | ✗ | ✗ |
| Edit Pricing | ✓ | ✓ | ✗ | ✗ |
| Generate Term Invoices | ✓ | ✓ | ✗ | ✗ |
| **Inventory** |
| Create Item | ✓ | ✓ | ✗ | ✗ |
| Create Issue Request | ✓ | ✓ | ✓ | ✗ |
| Approve Request | ✓ | ✓ | ✗ | ✗ |
| Issue Stock | ✓ | ✓ | ✗ | ✗ |
| Fast Issue | ✓ | ✓ | ✗ | ✗ |
| Write-off | ✓ (approve) | ✓ (approve) | ✓ (create) | ✗ |
| Inventory Adjustment | ✓ | ✓ | ✗ | ✗ |
| View Stock | ✓ | ✓ | ✓ | ✓ |
| **Procurement** |
| Create PO | ✓ | ✓ | ✗ | ✗ |
| Approve GRN | ✓ | ✓ | ✗ | ✗ |
| Record Procurement Payment | ✓ | ✓ | ✗ | ✗ |
| Cancel Procurement Payment | ✓ | ✗ | ✗ | ✗ |
| View PO/GRN | ✓ | ✓ | ✗ | ✓ |
| **Compensations** |
| Create Own Claim | ✓ | ✓ | ✓ | ✓ |
| Create Claim for Others | ✓ | ✓ | ✗ | ✗ |
| Approve Claim | ✓ | ✗ | ✗ | ✗ |
| Create Payout | ✓ | ✗ | ✗ | ✗ |
| View All Claims | ✓ | ✓ | ✗ | ✓ |
| View Own Claims | ✓ | ✓ | ✓ | ✓ |
| **Reports** |
| View All Reports | ✓ | ✓ | ✗ | ✓ |
| Export CSV | ✓ | ✓ | ✗ | ✓ |
| **System** |
| Manage Users | ✓ | ✗ | ✗ | ✗ |
| View Audit Log | ✓ | ✓ | ✗ | ✓ |
| System Settings | ✓ | ✗ | ✗ | ✗ |

\* Admin can reallocate but requires comment

---

### 9.2. Data Access Rules

**Row-Level Security:**

1. **Users (Employees)**
   - Can view/edit own claims
   - Cannot view other employees' claims (except Admin/SuperAdmin)

2. **Students**
   - No parent portal in MVP
   - All student data accessible by Admin/SuperAdmin/Accountant

3. **Payments/Invoices**
   - Accessible by role, not by creator
   - No "my payments only" filter

**Field-Level Security:**

1. **Sensitive Fields (view-only for most):**
   - Discount amounts and reasons
   - Payment cancellation reasons
   - Employee compensation balances

2. **Approval Fields:**
   - Only approver can set approved_by, approved_at

---

### 9.3. Audit Requirements

**Must Be Logged:**

1. All CREATE operations on:
   - Student, Invoice, Payment, PurchaseOrder, ExpenseClaim

2. All UPDATE operations on:
   - Student (grade, status, transport changes)
   - Invoice (discounts, totals)
   - Payment (allocation changes)
   - PriceSettings

3. All APPROVE/CANCEL operations:
   - Payments, Claims, GRNs, IssueRequests, WriteOffs

4. All STOCK operations:
   - Receive, Issue, WriteOff, Adjustment

**Audit Log Fields:**
- user_id (who performed action)
- timestamp (when)
- action (CREATE, UPDATE, APPROVE, CANCEL, etc.)
- entity_type and entity_id
- old_values and new_values (JSON)
- comment (for critical operations)
- ip_address (optional but recommended)

---

### 9.4. Security Best Practices

**Authentication:**
- Password minimum 8 characters
- Password must include: uppercase, lowercase, number
- Password hashing: bcrypt or Argon2
- Session timeout: 60 minutes of inactivity

**Authorization:**
- Check role on every API endpoint
- Implement at both API and UI levels
- Use middleware/decorators for role checks

**Data Validation:**
- Validate on both client and server
- Sanitize all inputs (prevent SQL injection, XSS)
- Validate file uploads (type, size, virus scan)

**Sensitive Data:**
- Do not log passwords or payment details in plaintext
- Mask sensitive data in logs (show last 4 digits of phone numbers)
- HTTPS only for all connections

---

## 10. СПЕЦИФИКАЦИИ ИНТЕРФЕЙСОВ И API

### 10.1. API Architecture

**Style:** RESTful API

**Base URL:** `https://api.schoolerp.example.com/v1`

**Authentication:** Bearer Token (JWT)

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Response Format:**
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful",
  "errors": []
}
```

**Error Response:**
```json
{
  "success": false,
  "data": null,
  "message": "Validation error",
  "errors": [
    {
      "field": "amount",
      "message": "Amount must be positive"
    }
  ]
}
```

---

### 10.2. Core API Endpoints

#### Authentication

**POST /auth/login**
```json
Request:
{
  "email": "admin@school.com",
  "password": "SecurePass123"
}

Response:
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": 1,
      "email": "admin@school.com",
      "full_name": "Admin User",
      "role": "Admin"
    }
  }
}
```

**POST /auth/logout**

**POST /auth/refresh**

---

#### Students

**GET /students**
```
Query Parameters:
- status: Lead|Student|Enrolled|Inactive
- grade: Grade 1|Grade 2|...
- search: string (name or phone)
- page: int
- limit: int

Response:
{
  "success": true,
  "data": {
    "students": [...],
    "total": 150,
    "page": 1,
    "limit": 20
  }
}
```

**GET /students/:id**

**POST /students**
```json
Request:
{
  "surname": "Kamau",
  "first_name": "James",
  "grade": "Grade 3",
  "guardian_name": "Mary Kamau",
  "guardian_phone": "+254712345678",
  "transport_enabled": true,
  "transport_zone_id": 5,
  "current_uniform_size": "10y"
}

Response:
{
  "success": true,
  "data": {
    "id": 123,
    "student_number": "STU-2026-000123",
    ...
  }
}
```

**PUT /students/:id**

**PUT /students/:id/status**
```json
Request:
{
  "status": "Inactive",
  "reason": "Left school"
}
```

---

#### Invoices

**GET /invoices**
```
Query Parameters:
- student_id: int
- term_id: int
- status: Draft|Issued|PartiallyPaid|Paid|Cancelled
- page, limit
```

**GET /invoices/:id**

**POST /invoices/:id/discount**
```json
Request:
{
  "discount_type": "Percentage",
  "discount_value": 10,
  "reason_category": "SIBLING_3RD",
  "reason_detail": "3rd child discount"
}

Response:
{
  "success": true,
  "data": {
    "discount_id": 456,
    "calculated_amount": 500.00,
    "new_invoice_total": 4500.00
  }
}
```

**POST /invoices/:id/sell-uniform**
```json
Request:
{
  "uniform_size": "10y"
}

Response:
{
  "success": true,
  "data": {
    "invoice_line_id": 789,
    "amount": 5000.00
  }
}
```

**GET /invoices/:id/pdf**
Returns PDF file

---

#### Payments

**POST /payments**
```json
Request:
{
  "student_id": 123,
  "amount": 10000.00,
  "payment_date": "2026-01-25",
  "payment_method": "M-Pesa",
  "reference_number": "ABC123XYZ"
}

Response:
{
  "success": true,
  "data": {
    "payment_id": 456,
    "payment_number": "PAY-2026-000456",
    "receipt_number": "RCT-2026-000456",
    "allocations": [
      {
        "invoice_line_id": 789,
        "line_type": "SchoolFee",
        "allocated_amount": 8000.00
      },
      {
        "invoice_line_id": 790,
        "line_type": "Transport",
        "allocated_amount": 2000.00
      }
    ],
    "credit_balance": 0.00
  }
}
```

**POST /payments/:id/cancel**
```json
Request:
{
  "cancelled_reason": "Payment was made in error - wrong student"
}

Response:
{
  "success": true,
  "message": "Payment cancelled successfully"
}
```

**POST /payments/:id/reallocate**
```json
Request:
{
  "allocations": [
    {
      "invoice_line_id": 789,
      "allocated_amount": 5000.00
    },
    {
      "invoice_line_id": 791,
      "allocated_amount": 5000.00
    }
  ],
  "comment": "Reallocated to prioritize transport fee"
}
```

---

#### Terms

**GET /terms**

**POST /terms**
```json
Request:
{
  "year": 2026,
  "term_number": 2,
  "display_name": "2026 Term 2",
  "copy_pricing_from_term_id": 1
}

Response:
{
  "success": true,
  "data": {
    "term_id": 2,
    "price_settings_copied": true
  }
}
```

**POST /terms/:id/activate**

**POST /terms/:id/generate-invoices**
```json
Response:
{
  "success": true,
  "data": {
    "invoices_generated": 150,
    "students_processed": 150
  }
}
```

---

#### Inventory

**GET /items**
```
Query Parameters:
- category_id: int
- is_uniform_item: bool
- search: string
```

**POST /items**

**GET /stock-balances**

**GET /stock-movements**
```
Query Parameters:
- item_id: int
- movement_type: Receive|Issue|WriteOff|Adjustment
- from_date, to_date
```

**POST /stock/issue-request**
```json
Request:
{
  "destination": "Grade 3",
  "required_date": "2026-01-30",
  "lines": [
    {
      "item_id": 123,
      "quantity_requested": 20
    },
    {
      "item_id": 456,
      "quantity_requested": 10
    }
  ]
}

Response:
{
  "success": true,
  "data": {
    "request_id": 789,
    "request_number": "ISS-REQ-2026-000789",
    "status": "PendingApproval"
  }
}
```

**POST /stock/issue-request/:id/approve**

**POST /stock/issue-request/:id/issue**
```json
Request:
{
  "lines": [
    {
      "line_id": 1,
      "quantity_to_issue": 20  // can be less than requested
    },
    {
      "line_id": 2,
      "quantity_to_issue": 8   // partial issue
    }
  ]
}

Response:
{
  "success": true,
  "data": {
    "issued_items": 2,
    "status": "PartiallyIssued"
  }
}
```

**POST /stock/fast-issue**
```json
Request:
{
  "destination": "Kitchen",
  "items": [
    {
      "item_id": 123,
      "quantity": 10
    }
  ]
}
```

**POST /stock/writeoff**
```json
Request:
{
  "items": [
    {
      "item_id": 123,
      "quantity": 3,
      "reason": "Spoiled food"
    }
  ]
}
```

**POST /stock/adjustment**
```json
Request:
{
  "count_date": "2026-01-25",
  "adjustments": [
    {
      "item_id": 123,
      "system_quantity": 100,
      "actual_quantity": 95
    },
    {
      "item_id": 456,
      "system_quantity": 50,
      "actual_quantity": 52
    }
  ]
}

Response:
{
  "success": true,
  "data": {
    "adjustments_created": 2,
    "total_variance": -3
  }
}
```

---

#### Uniform Fulfillment

**GET /uniform/pending**
```
Returns list of students with pending uniform items

Response:
{
  "success": true,
  "data": {
    "pending_fulfillments": [
      {
        "fulfillment_id": 123,
        "student": {
          "id": 456,
          "full_name": "James Kamau",
          "grade": "Grade 3"
        },
        "uniform_size": "10y",
        "status": "Pending",
        "pending_items": [
          {
            "item_id": 789,
            "item_name": "Shirt 10y",
            "quantity_required": 2,
            "quantity_issued": 0,
            "quantity_pending": 2,
            "in_stock": 5
          },
          ...
        ]
      },
      ...
    ]
  }
}
```

**POST /uniform/fulfillment/:id/issue**
```json
Request:
{
  "items": [
    {
      "fulfillment_item_id": 123,
      "quantity": 2
    },
    {
      "fulfillment_item_id": 124,
      "quantity": 1
    }
  ]
}

Response:
{
  "success": true,
  "data": {
    "items_issued": 2,
    "fulfillment_status": "Partial"
  }
}
```

---

#### Procurement

**GET /purchase-orders**

**POST /purchase-orders**
```json
Request:
{
  "supplier_name": "ABC Suppliers Ltd",
  "supplier_contact": "+254700123456",
  "order_date": "2026-01-25",
  "track_to_warehouse": true,
  "lines": [
    {
      "item_id": 123,
      "description": "Exercise Books A4",
      "quantity_expected": 100,
      "unit_price": 50.00
    },
    {
      "description": "Cleaning Services",
      "quantity_expected": 1,
      "unit_price": 5000.00
    }
  ]
}

Response:
{
  "success": true,
  "data": {
    "po_id": 456,
    "po_number": "PO-2026-000456",
    "expected_total": 10000.00
  }
}
```

**POST /purchase-orders/:id/receive**
```json
Request:
{
  "received_date": "2026-01-26",
  "lines": [
    {
      "po_line_id": 789,
      "quantity_received": 95
    },
    {
      "po_line_id": 790,
      "quantity_received": 1
    }
  ]
}

Response:
{
  "success": true,
  "data": {
    "grn_id": 123,
    "grn_number": "GRN-2026-000123",
    "status": "Approved",
    "po_status": "PartiallyReceived"
  }
}
```

**POST /purchase-orders/:id/payment**
```json
Request:
{
  "payment_date": "2026-01-27",
  "amount": 5000.00,
  "payment_method": "Bank",
  "reference_number": "TXN12345",
  "employee_paid": true,
  "employee_paid_id": 10
}

Response:
{
  "success": true,
  "data": {
    "payment_id": 789,
    "payment_number": "PPAY-2026-000789",
    "claim_created": true,
    "claim_number": "CLM-2026-001234"
  }
}
```

---

#### Expense Claims

**GET /claims**
```
Query Parameters:
- employee_id: int
- status: Draft|PendingApproval|Approved|Paid|Rejected
- category: string
```

**POST /claims**
```json
Request:
{
  "expense_category": "Transport",
  "amount": 500.00,
  "description": "Taxi to supplier for urgent purchase",
  "expense_date": "2026-01-25",
  "proof_provided": true
}

Response:
{
  "success": true,
  "data": {
    "claim_id": 123,
    "claim_number": "CLM-2026-000123",
    "upload_url": "https://upload.../claims/123"  // for proof upload
  }
}
```

**POST /claims/:id/submit**

**POST /claims/:id/approve**
```json
Request:
{
  "approved": true
}

// OR

{
  "approved": false,
  "rejection_reason": "Insufficient documentation"
}
```

---

#### Compensation Payouts

**GET /compensations/balances**
```
Returns list of employees with their compensation balances

Response:
{
  "success": true,
  "data": {
    "balances": [
      {
        "employee_id": 10,
        "employee_name": "John Doe",
        "total_approved": 15000.00,
        "total_paid": 10000.00,
        "balance": 5000.00,
        "pending_claims_count": 3
      },
      ...
    ]
  }
}
```

**POST /compensations/payout**
```json
Request:
{
  "employee_id": 10,
  "payout_date": "2026-01-25",
  "amount": 5000.00,
  "payment_method": "M-Pesa",
  "reference_number": "MPesa123",
  "notes": "Full settlement"
}

Response:
{
  "success": true,
  "data": {
    "payout_id": 456,
    "payout_number": "CPO-2026-000456",
    "claims_paid": [
      {
        "claim_number": "CLM-2026-000120",
        "allocated": 2000.00
      },
      {
        "claim_number": "CLM-2026-000121",
        "allocated": 3000.00
      }
    ],
    "new_balance": 0.00
  }
}
```

---

#### Reports

**GET /reports/accounts-receivable**
```
Query Parameters:
- term_id: int (optional)
- grade: string (optional)
- status: Student|Enrolled|Inactive
- format: json|csv

Response (JSON):
{
  "success": true,
  "data": {
    "report_date": "2026-01-25",
    "term": "2026-T1",
    "students": [
      {
        "student_id": 123,
        "student_number": "STU-2026-000123",
        "full_name": "James Kamau",
        "grade": "Grade 3",
        "total_invoiced": 25000.00,
        "total_paid": 15000.00,
        "outstanding": 10000.00,
        "credit": 0.00
      },
      ...
    ],
    "summary": {
      "total_students": 150,
      "total_invoiced": 3750000.00,
      "total_paid": 3000000.00,
      "total_outstanding": 750000.00
    }
  }
}
```

**GET /reports/collections**

**GET /reports/procurement-debts**

**GET /reports/compensations**

**GET /reports/inventory-valuation**

**GET /reports/stock-movements**

---

#### Audit Log

**GET /audit-log**
```
Query Parameters:
- user_id: int
- entity_type: string
- action: string
- from_date, to_date
- page, limit

Response:
{
  "success": true,
  "data": {
    "logs": [
      {
        "id": 12345,
        "user": "Admin User",
        "action": "CREATE_PAYMENT",
        "entity_type": "Payment",
        "entity_identifier": "PAY-2026-000456",
        "timestamp": "2026-01-25T14:30:00Z",
        "comment": null
      },
      ...
    ],
    "total": 5000,
    "page": 1
  }
}
```

---

### 10.3. File Upload Endpoints

**POST /upload/attachment**
```
Content-Type: multipart/form-data

Fields:
- file: binary
- entity_type: string
- entity_id: int
- attachment_type: string

Response:
{
  "success": true,
  "data": {
    "attachment_id": 789,
    "file_name": "receipt.jpg",
    "file_path": "attachments/2026/01/receipt_abc123.jpg"
  }
}
```

---

### 10.4. Bulk Operations

**POST /students/bulk-import**
```
Content-Type: multipart/form-data

Fields:
- file: CSV file

CSV Format:
surname,first_name,grade,guardian_name,guardian_phone,...

Response:
{
  "success": true,
  "data": {
    "imported": 50,
    "failed": 2,
    "errors": [
      {
        "row": 15,
        "error": "Invalid phone format"
      }
    ]
  }
}
```

---

## 11. ОТЧЕТЫ И АНАЛИТИКА

### 11.1. Accounts Receivable Report

**Purpose:** Show all outstanding balances per student

**Filters:**
- Term
- Grade
- Student status
- Minimum balance

**Columns:**
| Column | Description |
|--------|-------------|
| Student Number | STU-2026-NNNNNN |
| Student Name | Full name |
| Grade | Current grade |
| Total Invoiced | Sum of all invoices |
| Total Paid | Sum of payments |
| Outstanding | Amount due |
| Credit | Prepayment balance |
| Last Payment Date | Most recent payment |

**Summary:**
- Total Students
- Total Invoiced
- Total Paid
- Total Outstanding
- Average Balance per Student

**Export:** CSV, PDF

---

### 11.2. Collections Report

**Purpose:** Show payment collection breakdown

**Filters:**
- Term
- Date range
- Payment method
- Fee type (SchoolFee, Transport, Uniform, etc.)

**Grouping Options:**
- By Term
- By Grade
- By Fee Type
- By Date (daily/weekly/monthly)

**Columns:**
| Column | Description |
|--------|-------------|
| Period | Date or term |
| School Fee | Amount collected |
| Transport | Amount collected |
| Uniform | Amount collected |
| Admission | Amount collected |
| Other | Amount collected |
| Total | Sum |

**Summary:**
- Total Collected
- Collection Rate (% of invoiced amount)
- Outstanding Amount

---

### 11.3. Credit Balances Report

**Purpose:** Show students with prepayment/credit

**Columns:**
| Column | Description |
|--------|-------------|
| Student Number | |
| Student Name | |
| Grade | |
| Credit Balance | Positive amount |
| Last Credit Date | When credit was created |

---

### 11.4. Procurement Debts Report

**Purpose:** Show amounts owed to suppliers

**Filters:**
- Supplier
- Date range
- PO status

**Columns:**
| Column | Description |
|--------|-------------|
| PO Number | |
| Supplier Name | |
| Order Date | |
| Expected Total | Original order value |
| Received Value | Actual received |
| Paid Total | Amount paid |
| Debt | Outstanding balance |
| Last Payment Date | |

**Summary:**
- Total Expected
- Total Received
- Total Paid
- Total Debt

---

### 11.5. Compensation Balances Report

**Purpose:** Show amounts owed to employees

**Filters:**
- Employee
- Claim status
- Date range

**Columns:**
| Column | Description |
|--------|-------------|
| Employee Name | |
| Total Approved | Sum of approved claims |
| Total Paid | Sum of payouts |
| Balance | Outstanding |
| Pending Claims Count | |
| Last Payout Date | |

**Summary:**
- Total Employees
- Total Balance (school owes)
- Advances (employee owes school)

---

### 11.6. Inventory Valuation Report

**Purpose:** Show current stock value

**Filters:**
- Category
- Item type

**Columns:**
| Column | Description |
|--------|-------------|
| Item Code | SKU |
| Item Name | |
| Category | |
| Quantity On Hand | |
| Cost Price | Per unit |
| Total Value | Qty × Cost |

**Summary:**
- Total Items
- Total Value
- By Category breakdown

---

### 11.7. Stock Movements Report

**Purpose:** Detailed movement history

**Filters:**
- Item
- Movement type
- Date range
- Destination

**Columns:**
| Column | Description |
|--------|-------------|
| Movement Number | |
| Date | |
| Type | Receive/Issue/WriteOff/Adjustment |
| Item Name | |
| Quantity | + or - |
| Balance After | |
| Destination/Source | |
| User | Who performed |
| Document | Related PO/GRN/Request |

---

### 11.8. Discount Report

**Purpose:** Track all discounts given

**Filters:**
- Date range
- Discount reason
- Student
- Term

**Columns:**
| Column | Description |
|--------|-------------|
| Student Name | |
| Invoice Number | |
| Discount Type | Percentage/Fixed |
| Discount Value | |
| Amount (KES) | Calculated discount |
| Reason | |
| Applied By | |
| Date | |

**Summary:**
- Total Discounts Given
- By Reason breakdown
- Average Discount

---

### 11.9. Daily Cash Report

**Purpose:** Daily cash flow summary

**Date:** Single date

**Sections:**

**Receipts:**
- Student Payments (by method: M-Pesa, Bank, Cash)
- Total Received

**Expenses Paid:**
- Procurement Payments
- Compensation Payouts
- Total Paid

**Net Position:**
- Receipts - Expenses

---

### 11.10. Term Performance Report

**Purpose:** Overview of term financial performance

**Term:** Single term

**Sections:**

**Revenue:**
- School Fees Invoiced
- Transport Invoiced
- Uniform Sales
- Other Sales
- Total Invoiced

**Collections:**
- School Fees Collected
- Transport Collected
- Uniform Collected
- Other Collected
- Total Collected
- Collection Rate (%)

**Outstanding:**
- Total Outstanding
- By Grade breakdown

**Students:**
- Total Enrolled
- Active Students
- Inactive Students

---

## 12. НЕФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

### 12.1. Performance Requirements

**Response Times:**
- Page load: < 2 seconds
- API response (simple query): < 500ms
- API response (complex report): < 5 seconds
- PDF generation: < 3 seconds

**Throughput:**
- Support 50 concurrent users
- Handle 100 transactions per minute

**Data Volume:**
- 500 students (initial)
- 10,000 transactions per year
- Database size: < 10GB (first 3 years)

---

### 12.2. Scalability

**Horizontal Scaling:**
- Application tier: stateless, can add servers
- Database: single instance acceptable for MVP
- File storage: S3-compatible, unlimited

**Growth Capacity:**
- Support up to 1000 students without architecture changes
- Handle 5-year data retention

---

### 12.3. Availability

**Uptime:**
- Target: 99% (allows ~7 hours downtime/month)
- Maintenance window: Sundays 10 PM - 12 AM

**Backup:**
- Daily automated backups
- Retention: 30 days
- Backup verification: monthly test restore

**Disaster Recovery:**
- RTO (Recovery Time Objective): 4 hours
- RPO (Recovery Point Objective): 24 hours

---

### 12.4. Security Requirements

**Data Protection:**
- All data encrypted at rest (AES-256)
- All transmission encrypted (TLS 1.2+)
- Database credentials in environment variables

**Access Control:**
- Role-based access control (RBAC)
- Session management with secure cookies
- Auto-logout after 60 minutes inactivity

**Audit:**
- All critical operations logged
- Logs retained for 2 years
- Log integrity protection

**Compliance:**
- GDPR/data protection principles
- No unnecessary personal data collection
- Data retention policy defined

---

### 12.5. Usability

**Responsive Design:**
- Support desktop (1920×1080, 1366×768)
- Support tablet (768×1024)
- Mobile view (not full functionality, but readable)

**Browser Support:**
- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Edge (latest 2 versions)

**Accessibility:**
- WCAG 2.1 Level AA (recommended)
- Keyboard navigation
- Screen reader compatible (basic)

---

### 12.6. Localization

**Language:**
- English (primary)
- Future: Swahili support (structure in place)

**Date/Time:**
- Format: DD/MM/YYYY, 24-hour time
- Timezone: EAT (East Africa Time, UTC+3)

**Currency:**
- KES (Kenyan Shilling)
- Format: 1,234.56
- Symbol: KES or KSh

---

### 12.7. Monitoring and Logging

**Application Logs:**
- Error logs (all exceptions)
- Access logs (requests)
- Business logs (transactions)
- Performance logs (slow queries)

**Monitoring:**
- Server health (CPU, memory, disk)
- Database performance
- API response times
- Error rates

**Alerting:**
- Email alerts for critical errors
- SMS for system down (optional)

---

### 12.8. Data Retention

**Operational Data:**
- Students: permanent (anonymize on request)
- Transactions: 7 years
- Audit logs: 3 years
- Attachments: 7 years

**Backups:**
- Daily: 30 days
- Monthly: 12 months
- Annual: 7 years

---

## 13. ТЕСТОВЫЕ СЦЕНАРИИ

### 13.1. Student Management Tests

**Test 1: Create New Student**
```
Given: Admin is logged in
When: Admin creates student with all required fields
Then: 
  - Student is created with status "Student"
  - Student number is auto-generated (STU-2026-NNNNNN)
  - Student appears in list
```

**Test 2: Enroll Student After Payment**
```
Given: Student exists with status "Student"
  And: Term invoice generated
When: Payment is recorded for school fee
Then:
  - Student status changes to "Enrolled"
  - Payment is allocated to school fee
```

**Test 3: Mark Student Inactive**
```
Given: Student is Enrolled
When: Admin marks student as Inactive
Then:
  - Student status is "Inactive"
  - No new term invoices generated
  - Student visible in list with filter
```

---

### 13.2. Billing Tests

**Test 4: Generate Term Invoices**
```
Given: New term is created and activated
  And: 50 active students exist
When: Admin triggers "Generate Invoices"
Then:
  - 50 invoices created (one per student)
  - Each invoice has school fee line
  - Students with transport have transport line
  - First-term students have admission fee
```

**Test 5: Payment Allocation - Full Payment**
```
Given: Student has invoice for 25,000 KES (school fee)
When: Payment of 25,000 KES is recorded
Then:
  - Payment fully allocated to school fee
  - Invoice status is "Paid"
  - Receipt is generated
  - Student status is "Enrolled"
```

**Test 6: Payment Allocation - Partial Payment**
```
Given: Student has invoice for 25,000 KES
When: Payment of 10,000 KES is recorded
Then:
  - Payment allocated to school fee
  - Invoice status is "PartiallyPaid"
  - Invoice amount_due is 15,000
  - Receipt generated for 10,000
```

**Test 7: Payment with Overpayment (Credit)**
```
Given: Student has invoice for 25,000 KES
When: Payment of 30,000 KES is recorded
Then:
  - 25,000 allocated to invoice
  - Invoice status is "Paid"
  - Student credit balance is 5,000
  - Receipt shows full 30,000
```

**Test 8: Credit Applied to New Term**
```
Given: Student has credit of 5,000 KES
  And: New term invoice for 25,000 KES
When: Payment of 15,000 KES is recorded
Then:
  - Credit (5,000) applied first
  - Payment (15,000) applied next
  - Total applied: 20,000
  - Invoice amount_due: 5,000
  - Credit balance: 0
```

**Test 9: Priority Allocation - Uniform Before School Fee**
```
Given: Student has two invoice lines:
  - UniformBundle: 5,000 (must_be_paid_in_full)
  - SchoolFee: 20,000
When: Payment of 8,000 KES is recorded
Then:
  - 5,000 allocated to UniformBundle (fully paid)
  - 3,000 allocated to SchoolFee
  - UniformBundle triggers fulfillment creation
  - SchoolFee remains partially paid
```

**Test 10: Cancel Payment**
```
Given: Payment exists and is allocated
  And: Invoice was marked "Paid"
When: SuperAdmin cancels payment with reason
Then:
  - Payment status is "Cancelled"
  - Allocations are reversed
  - Invoice status recalculated (back to Issued or PartiallyPaid)
  - Receipt is voided
  - Audit log entry created
```

---

### 13.3. Discount Tests

**Test 11: Apply Percentage Discount**
```
Given: Invoice total is 25,000 KES
When: Admin applies 10% discount with reason "SIBLING_3RD"
Then:
  - Discount amount is 2,500
  - Invoice total becomes 22,500
  - Amount_due adjusts accordingly
  - Discount logged in audit
```

**Test 12: Apply Fixed Discount**
```
Given: Invoice total is 25,000 KES
When: Admin applies 5,000 KES fixed discount
Then:
  - Invoice total becomes 20,000
  - Discount record created
```

---

### 13.4. Uniform Tests

**Test 13: Sell Uniform - Creates Invoice Line**
```
Given: Student exists
When: Admin sells uniform size "10y"
Then:
  - Invoice line created for 5,000 KES
  - Line type is "UniformBundle"
  - must_be_paid_in_full is true
  - No fulfillment created yet (awaiting payment)
```

**Test 14: Uniform Fulfillment After Full Payment**
```
Given: UniformBundle line exists, unpaid
When: Payment fully covers UniformBundle
Then:
  - UniformFulfillment record created
  - Required items populated (Shirt×2, Shorts×2, Sweater×1, etc.)
  - Status is "Pending"
  - Appears in warehouse "Pending Fulfillments"
```

**Test 15: Issue Uniform Items Partially**
```
Given: UniformFulfillment has 5 pending items
  And: Stock available for 3 items only
When: Warehouse staff issues available items
Then:
  - 3 items marked as issued
  - Stock reduced for those items
  - Fulfillment status is "Partial"
  - 2 items remain pending
```

**Test 16: Complete Uniform Fulfillment**
```
Given: UniformFulfillment is "Partial"
  And: Stock replenished for remaining items
When: Warehouse issues remaining 2 items
Then:
  - All items issued
  - Fulfillment status is "Fulfilled"
  - No longer appears in pending list
```

---

### 13.5. Inventory Tests

**Test 17: Create Issue Request**
```
Given: User is logged in
When: User creates request for 20 pens to "Grade 3"
Then:
  - Request created with status "PendingApproval"
  - Request number generated
```

**Test 18: Approve and Issue Request**
```
Given: Request exists, approved
  And: Stock has 30 pens
When: Admin issues 20 pens
Then:
  - Stock reduced to 10
  - Request status is "Issued"
  - Stock movement created
```

**Test 19: Prevent Negative Stock**
```
Given: Stock has 10 pens
When: Admin tries to issue 15 pens
Then:
  - Error: "Insufficient stock"
  - Stock remains 10
  - No movement created
```

**Test 20: Fast Issue (Direct)**
```
Given: Admin role
  And: Stock has 50 notebooks
When: Admin directly issues 20 notebooks to "Grade 2"
Then:
  - Stock reduced to 30
  - Movement created immediately
  - No request record
```

**Test 21: Write-off Spoiled Items**
```
Given: Stock has 100 breads
When: Admin writes off 5 breads (reason: "Spoiled")
  And: SuperAdmin approves
Then:
  - Stock reduced to 95
  - Movement type "WriteOff" created
  - Reason logged
```

**Test 22: Inventory Adjustment**
```
Given: System shows 100 pens
When: Physical count finds 95 pens
  And: Admin enters adjustment
Then:
  - Adjustment movement created (-5)
  - Stock balance is 95
  - Reason: "Inventory count variance"
```

---

### 13.6. Procurement Tests

**Test 23: Create Purchase Order**
```
Given: Admin is logged in
When: Admin creates PO with supplier and 3 line items
Then:
  - PO created with status "Ordered"
  - PO number generated
  - Expected total calculated
```

**Test 24: Receive Goods Fully**
```
Given: PO exists for 100 notebooks
When: Admin creates GRN receiving all 100
  And: Admin approves GRN
Then:
  - Stock increased by 100
  - PO status is "Received"
  - PO received_value equals expected_total
```

**Test 25: Receive Goods Partially**
```
Given: PO for 100 notebooks
When: Admin receives 60
Then:
  - Stock increased by 60
  - PO status is "PartiallyReceived"
  - PO received_value is 60% of expected
```

**Test 26: Record Procurement Payment**
```
Given: PO received_value is 10,000
When: Admin records payment of 7,000
Then:
  - PO paid_total is 7,000
  - PO debt is 3,000
```

**Test 27: Employee Paid - Auto Claim**
```
Given: PO exists
When: Admin records payment with "employee_paid" flag
  And: Selects employee John
Then:
  - Payment recorded
  - ExpenseClaim auto-created for John
  - Claim status is "PendingApproval"
  - Claim amount matches payment
```

**Test 28: Procurement Debt Calculation**
```
Given: PO expected 100 items at 100 KES = 10,000
  And: Received 90 items = 9,000
  And: Paid 5,000
When: System calculates debt
Then:
  - Debt = 9,000 - 5,000 = 4,000
  - (NOT based on expected 10,000)
```

---

### 13.7. Compensation Tests

**Test 29: Employee Creates Claim**
```
Given: Employee is logged in
When: Employee creates claim for 500 KES with receipt
  And: Submits for approval
Then:
  - Claim created with status "PendingApproval"
  - Claim number generated
  - Receipt attached
```

**Test 30: SuperAdmin Approves Claim**
```
Given: Claim in "PendingApproval"
When: SuperAdmin approves
Then:
  - Claim status is "Approved"
  - Employee balance increases by claim amount
```

**Test 31: Create Payout - Full Settlement**
```
Given: Employee has 3 approved claims totaling 5,000
When: SuperAdmin creates payout for 5,000
Then:
  - All 3 claims marked "Paid"
  - Employee balance is 0
  - Payout record created
```

**Test 32: Create Payout - Partial**
```
Given: Employee has approved claims: 2,000 + 3,000 + 4,000 = 9,000
When: SuperAdmin creates payout for 6,000
Then:
  - Claim 1 (2,000) marked "Paid"
  - Claim 2 (3,000) marked "Paid"
  - Claim 3 (4,000) marked "PartiallyPaid" with 1,000 paid
  - Employee balance is 3,000
```

---

### 13.8. Edge Cases and Corner Cases

**Test 33: Payment Cancellation After Uniform Issue**
```
Given: UniformBundle paid → fulfillment created → 3 items issued
When: SuperAdmin cancels the payment
Then:
  - Payment cancelled
  - UniformBundle line becomes unpaid
  - Fulfillment status unchanged (items can't be un-issued)
  - Exception flag set on fulfillment
  - Alert created for admin review
```

**Test 34: Double Payment Prevention**
```
Given: Payment created with reference "ABC123"
When: Admin tries to create another payment with same reference
Then:
  - Warning: "Duplicate reference detected"
  - Allow with confirmation or reject
```

**Test 35: Reallocation of Payment**
```
Given: Payment allocated: 8,000 to SchoolFee, 2,000 to Transport
When: Admin reallocates: 5,000 to SchoolFee, 5,000 to Transport
  And: Provides comment
Then:
  - Allocations updated
  - Invoice lines recalculated
  - Audit log with old/new values
```

**Test 36: Multiple Terms Outstanding**
```
Given: Student has unpaid invoices from Term 1 and Term 2
When: Payment recorded
Then:
  - Allocates to oldest invoice first (Term 1)
  - Then Term 2
  - Follows priority rules within each invoice
```

**Test 37: Concurrent Stock Issue**
```
Given: Stock has 10 pens
When: User A and User B simultaneously try to issue 8 pens each
Then:
  - One succeeds (stock → 2)
  - Other fails with "Insufficient stock" error
  - No negative stock
```

**Test 38: Large Batch Invoice Generation**
```
Given: 500 active students
When: Admin generates term invoices
Then:
  - All 500 invoices created
  - Operation completes in < 30 seconds
  - No duplicates
  - No missing students
```

---

### 13.9. Security Tests

**Test 39: Role-Based Access**
```
Given: User has role "User"
When: User tries to approve a claim
Then:
  - Access denied (403)
  - No data changed
```

**Test 40: Cannot Approve Own Request**
```
Given: User created issue request
When: Same user tries to approve it
Then:
  - Error: "Cannot approve own request"
```

**Test 41: SuperAdmin Only Operations**
```
Given: User has role "Admin" (not SuperAdmin)
When: Admin tries to cancel a payment
Then:
  - Access denied
```

**Test 42: Accountant Read-Only**
```
Given: User has role "Accountant"
When: Accountant views reports and documents
Then:
  - All data visible
When: Accountant tries to edit/create/approve
Then:
  - All actions blocked
```

---

### 13.10. Report Tests

**Test 43: AR Report Accuracy**
```
Given: 10 students with various invoices and payments
When: Admin generates AR report
Then:
  - Report shows correct outstanding per student
  - Totals match sum of individual balances
  - Credit students show negative or zero outstanding
```

**Test 44: Export CSV**
```
Given: AR report generated
When: Admin clicks "Export CSV"
Then:
  - CSV file downloads
  - Contains all data from report
  - Format is valid (importable to Excel)
```

---

### 13.11. Audit Log Tests

**Test 45: Critical Operations Logged**
```
Given: Various operations performed:
  - Create payment
  - Cancel payment
  - Apply discount
  - Approve claim
When: Admin views audit log
Then:
  - All operations appear in log
  - With correct user, timestamp, entity
  - Old/new values visible
```

---

### 13.12. Performance Tests

**Test 46: Page Load Performance**
```
Given: Database has 500 students, 5000 transactions
When: User navigates to student list
Then:
  - Page loads in < 2 seconds
```

**Test 47: Report Generation Performance**
```
Given: 500 students with full year data
When: Admin generates AR report
Then:
  - Report completes in < 5 seconds
```

---

## ЗАКЛЮЧЕНИЕ

Данное техническое задание покрывает MVP-версию ERP-системы для кенийской школы со следующими основными модулями:

1. ✅ **Students & Billing** - полностью детализирован
2. ✅ **Inventory & Warehouse** - полностью детализирован
3. ✅ **Procurement & Expenses** - полностью детализирован
4. ✅ **Employee Compensations** - полностью детализирован
5. ✅ **Audit & Security** - полностью детализирован

### Ключевые особенности спецификации:

- **Транзакционная целостность**: все финансовые и складские операции
- **Полный аудит**: каждое изменение отслеживается
- **Гибкая система платежей**: автоматическое распределение с приоритетами
- **Форма с отложенной выдачей**: 100% оплата → pending → частичная выдача
- **Компенсации сотрудникам**: балансы, частичные выплаты
- **Детальные бизнес-процессы**: step-by-step алгоритмы
- **Комплексные тестовые сценарии**: 47+ тестов

### Следующие шаги для разработки:

1. Настроить инфраструктуру (database, backend, frontend)
2. Имплементировать схему БД (см. часть 1)
3. Разработать API endpoints (см. раздел 10)
4. Создать UI согласно UX-требованиям
5. Покрыть тестами