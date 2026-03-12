# Доступ для внешнего бухгалтера (Accountant Role)

## Назначение

Внешний бухгалтер ведет бухгалтерский учет в своей системе (QuickBooks, Xero, Excel, или другой учетной системе). Ему нужен доступ к **первичным документам** и **сырым данным** для:
- Ввода транзакций в свою бухгалтерскую систему
- Reconciliation (сверка) банковских выписок
- Подготовки налоговых деклараций (VAT, WHT, Corporation Tax)
- Проверки правильности документов (audit)
- Подготовки финансовой отчетности для налоговой

**Важно:** Бухгалтер НЕ делает отчеты в нашей системе. Он берет данные и делает отчеты у себя.

## Роль в системе: Read-Only

- **Нет прав редактирования** (не может создавать/изменять инвойсы, платежи, закупки)
- **Полный доступ на чтение** ко всем финансовым документам
- **Экспорт данных** в CSV/Excel для импорта в свою систему
- **Просмотр audit trail** для проверки кто и что менял
- **Скачивание PDF** первичных документов (receipts, invoices, etc.)

## 1. Первичные документы для бухгалтера

### 1.1 Payment Receipts (Чеки об оплате)

**Что это:** Документы, подтверждающие получение денег от студентов/родителей.

**Доступ:**
- Список всех чеков с фильтрами (по дате, методу оплаты, студенту)
- Просмотр деталей каждого чека
- Скачивание PDF чека
- Массовый экспорт в Excel/CSV

**Поля в чеке:**
```
Receipt Number: RCP-2026-000456
Date: 28 Jan 2026
Student: John Doe (Admission #2024-0123)
Parent: Mary Doe
Payment Method: M-Pesa
Amount: 50,000 KES

Allocation:
- Invoice #INV-2026-000123: 30,000 KES (School Fee)
- Invoice #INV-2026-000124: 20,000 KES (Transport)

Received by: Admin User
Notes: Payment via M-Pesa transaction #ABC123456
```

**PDF формат:**
- Логотип школы
- Детали чека
- QR-код с номером чека (опционально)
- Подпись администратора (цифровая или скан)

### 1.2 Student Invoices (Счета студентам)

**Что это:** Счета, выставленные студентам за обучение, транспорт, форму и т.д.

**Доступ:**
- Список всех инвойсов с фильтрами (по триместру, студенту, статусу)
- Просмотр деталей каждого инвойса
- Скачивание PDF инвойса
- Экспорт в Excel/CSV

**Поля в инвойсе:**
```
Invoice Number: INV-2026-000123
Date: 15 Jan 2026
Due Date: 31 Jan 2026
Term: Term 1 2025/2026

Student: John Doe (Grade 7)
Parent: Mary Doe
Phone: +254 712 345 678

Line Items:
- School Fee: 100,000 KES
- Transport Fee: 30,000 KES
- Uniform Bundle: 15,000 KES
- Books: 5,000 KES

Subtotal: 150,000 KES
Discount (10% Sibling): -15,000 KES
Total: 135,000 KES

Status: Partially Paid
Paid to date: 50,000 KES
Balance: 85,000 KES
```

### 1.3 Purchase Orders (Заказы поставщикам)

**Что это:** Документы на закупку товаров/услуг у поставщиков.

**Доступ:**
- Список всех PO с фильтрами
- Просмотр деталей PO
- Скачивание PDF
- Экспорт в Excel/CSV

**Поля в PO:**
```
PO Number: PO-2026-000123
Date: 15 Jan 2026
Expected Delivery: 25 Jan 2026

Supplier: ABC Uniforms Ltd
Contact: Jane Smith
Email: jane@abcuniforms.co.ke

Items:
- School Shirt (Size M): 50 pcs × 800 KES = 40,000 KES
- School Trousers (Size L): 30 pcs × 1,200 KES = 36,000 KES

Subtotal: 76,000 KES
VAT (16%): 12,160 KES
Total: 88,160 KES

Status: Received
GRN: GRN-2026-000045
```

### 1.4 Goods Received Notes (Накладные на получение товара)

**Что это:** Подтверждение получения товара от поставщика.

**Поля в GRN:**
```
GRN Number: GRN-2026-000045
Date: 22 Jan 2026
PO Number: PO-2026-000123
Supplier: ABC Uniforms Ltd

Items Received:
- School Shirt (Size M): 50 pcs (ordered: 50)
- School Trousers (Size L): 28 pcs (ordered: 30) - 2 short

Notes: 2 trousers damaged during shipping, credited by supplier

Received by: Admin User
Approved by: SuperAdmin
```

### 1.5 Supplier Invoices (Счета от поставщиков)

**Что это:** Счета, которые поставщики выставляют школе.

**Примечание:** Это могут быть отсканированные PDF или данные, введенные вручную в систему.

**Поля:**
```
Supplier: ABC Uniforms Ltd
Invoice Number: ABC-INV-2026-0789
Date: 22 Jan 2026
PO Reference: PO-2026-000123

Amount: 88,160 KES (including VAT)
VAT Amount: 12,160 KES
Due Date: 21 Feb 2026

Payment Status: Unpaid
```

### 1.6 Procurement Payments (Платежи поставщикам)

**Что это:** Документы об оплате поставщикам.

**Поля:**
```
Payment Number: PP-2026-000089
Date: 25 Jan 2026
Supplier: ABC Uniforms Ltd
PO: PO-2026-000123
Amount: 88,160 KES
Method: Bank Transfer

WHT Deducted: 0 KES (or amount if applicable)
Net Paid: 88,160 KES

Paid by: Admin User (or via Employee Expense Claim)
Bank Reference: TXN-123456
```

### 1.7 Employee Expense Claims (Компенсации сотрудникам)

**Что это:** Заявки на возмещение расходов сотрудникам (проезд, питание, закупки за свой счет).

**Поля:**
```
Claim Number: CLM-2026-000045
Date: 20 Jan 2026
Employee: James Teacher
Description: Travel to conference in Nairobi

Expenses:
- Transport: 2,500 KES (Receipt attached)
- Meals: 1,500 KES (Receipt attached)
- Hotel: 8,000 KES (Invoice attached)

Total: 12,000 KES

Status: Approved
Approved by: SuperAdmin
Approval Date: 22 Jan 2026
Payment Status: Paid
Payment Date: 25 Jan 2026
```

### 1.8 Compensation Payouts (Выплаты компенсаций)

**Что это:** Группировка нескольких expense claims в один платеж.

**Поля:**
```
Payout Number: PAYOUT-2026-000012
Date: 25 Jan 2026
Employee: James Teacher

Claims included:
- CLM-2026-000045: 12,000 KES
- CLM-2026-000048: 3,500 KES

Total: 15,500 KES
Method: Bank Transfer
Reference: TXN-789012
```

## 2. Экспорт данных для бухгалтерской системы

### 2.1 Transactions Export (Главный экспорт)

**Формат:** CSV или Excel

**Назначение:** Импорт в QuickBooks, Xero, или другую систему учета.

**Параметры:**
- Date Range: от - до
- Transaction Types: All / Receipts / Invoices / Payments / etc.
- Include cancelled: Yes/No

**Колонки в CSV:**
```
Date | Type | Document# | Student/Supplier | Description | Debit | Credit | Category | Payment Method | Reference
```

**Пример данных:**
```csv
Date,Type,Document#,Party,Description,Debit,Credit,Category,Payment Method,Reference
2026-01-28,Receipt,RCP-2026-000456,John Doe,School Fee payment,50000,,Student Fees,M-Pesa,INV-2026-000123
2026-01-25,Payment,PP-2026-000089,ABC Uniforms Ltd,Uniform purchase payment,,88160,Procurement,Bank Transfer,PO-2026-000123
2026-01-22,GRN,GRN-2026-000045,ABC Uniforms Ltd,Uniforms received,,88160,Inventory Purchase,,PO-2026-000123
```

### 2.2 Student Payments Export

**Формат:** Excel/CSV

**Колонки:**
```
Receipt Date | Receipt# | Student Name | Admission# | Grade | Parent Name | Payment Method | Reference | Amount | Received By | Receipt PDF link | Attachment link
```

**Пример:**
```csv
2026-01-28,RCP-2026-000456,John Doe,2024-0123,Grade 7,Mary Doe,M-Pesa,ABC123456,50000,Admin User,https://app.school.co.ke/payment/456/receipt,https://app.school.co.ke/attachment/789/download
```

### 2.3 Procurement Payments Export

**Колонки:**
```
Payment Date | Payment# | Supplier | PO# | Invoice# | Gross Amount | VAT Amount | WHT Amount | Net Paid | Payment Method | Reference
```

### 2.4 VAT Transactions Export

**Для подготовки VAT Return.**

**Колонки:**
```
Date | Document Type | Document# | Party | Description | Gross Amount | VAT Amount | VAT Type (Input/Output)
```

**Пример:**
```csv
2026-01-28,Invoice,INV-2026-000123,John Doe,School fees,135000,0,Output (Exempt)
2026-01-22,GRN,GRN-2026-000045,ABC Uniforms Ltd,Uniform purchase,88160,12160,Input
```

**Примечание:** Некоторые образовательные услуги могут быть VAT-exempt в Кении.

### 2.5 Withholding Tax Export

**Для подготовки WHT Return.**

**Колонки:**
```
Payment Date | Payment# | Supplier | Supplier PIN | Service Type | Gross Amount | WHT Rate | WHT Amount
```

**Типичные WHT ставки в Кении:**
- Professional fees: 5%
- Consultancy: 5%
- Rent: 10%
- Management fees: 5%

## 3. Интерфейс для бухгалтера

### 3.1 Навигация (минимальная)

```
📄 Documents
   ├─ Payment Receipts
   ├─ Student Invoices
   ├─ Purchase Orders
   ├─ Goods Received Notes
   ├─ Supplier Invoices
   ├─ Procurement Payments
   └─ Employee Expenses

📊 Data Export
   ├─ All Transactions
   ├─ Student Payments
   ├─ Procurement Payments
   ├─ VAT Transactions
   └─ Withholding Tax

🔍 Audit Trail

⚙️ Settings
   └─ My Profile
```

### 3.2 Documents View (пример: Payment Receipts)

```
┌─────────────────────────────────────────────────────────┐
│ Payment Receipts                                         │
│ ┌─────────────────────────────────────────────────┐    │
│ │ Filters:                                         │    │
│ │ Date: [01/01/26] to [31/01/26]                  │    │
│ │ Method: [All ▼] Student: [Search...]            │    │
│ │ Status: [All ▼]                                  │    │
│ └─────────────────────────────────────────────────┘    │
│                                                          │
│ Showing 245 receipts | Total: 8,450,000 KES             │
│ [📄 Export CSV] [📊 Export Excel] [📥 Bulk Download PDFs]│
│                                                          │
│ Date      | Receipt# | Student    | Method | Amount     │
│ ─────────────────────────────────────────────────────── │
│ 28 Jan 26 | RCP-0456 | John Doe   | M-Pesa | 50,000    │
│           | [View] [PDF] [Email]                         │
│ 28 Jan 26 | RCP-0457 | Jane Smith | Cash   | 75,000    │
│           | [View] [PDF] [Email]                         │
│ 27 Jan 26 | RCP-0455 | Bob J.     | Bank   | 100,000   │
│           | [View] [PDF] [Email]                         │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Document Details View

При клике на "View" открывается детальная информация:

```
┌─────────────────────────────────────────────────────────┐
│ Receipt #RCP-2026-000456               [Download PDF]   │
├─────────────────────────────────────────────────────────┤
│ Date: 28 Jan 2026 10:30 AM                              │
│ Student: John Doe (Admission #2024-0123)                │
│ Parent: Mary Doe                                         │
│ Payment Method: M-Pesa                                   │
│ Amount: 50,000 KES                                       │
│                                                          │
│ Allocation:                                              │
│ - Invoice #INV-2026-000123: 30,000 KES                  │
│ - Invoice #INV-2026-000124: 20,000 KES                  │
│                                                          │
│ Received by: Admin User                                  │
│ Notes: M-Pesa transaction #ABC123456                     │
│                                                          │
│ Attachments: mpesa_confirmation.pdf                      │
│                                                [Close]   │
└─────────────────────────────────────────────────────────┘
```

### 3.4 Data Export Interface

```
┌─────────────────────────────────────────────────────────┐
│ Export Data for Accounting                               │
│                                                          │
│ 📊 All Transactions Export                              │
│ ┌─────────────────────────────────────────────────┐    │
│ │ Date Range: [01/01/2026] to [31/01/2026]        │    │
│ │ Include:                                         │    │
│ │ ☑ Student Payments                               │    │
│ │ ☑ Invoices                                       │    │
│ │ ☑ Procurement Payments                           │    │
│ │ ☑ Employee Expenses                              │    │
│ │ ☐ Include Cancelled                              │    │
│ │                                                   │    │
│ │ Format: ◉ CSV  ○ Excel                           │    │
│ │                                                   │    │
│ │ [Generate Export]                                 │    │
│ └─────────────────────────────────────────────────┘    │
│                                                          │
│ 💰 VAT Transactions Export                              │
│ ┌─────────────────────────────────────────────────┐    │
│ │ Period: [January 2026 ▼]                        │    │
│ │                                                   │    │
│ │ [Generate VAT Export]                             │    │
│ └─────────────────────────────────────────────────┘    │
│                                                          │
│ 📑 Withholding Tax Export                               │
│ ┌─────────────────────────────────────────────────┐    │
│ │ Period: [January 2026 ▼]                        │    │
│ │                                                   │    │
│ │ [Generate WHT Export]                             │    │
│ └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 4. Audit Trail (для проверки)

**Назначение:** Бухгалтер может проверить кто и когда создал/изменил документы.

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 Audit Trail                                          │
│ ┌─────────────────────────────────────────────────┐    │
│ │ Filters:                                         │    │
│ │ Date: [Last 30 days ▼] Custom: [...][...]       │    │
│ │ User: [All ▼]                                    │    │
│ │ Document Type: [All ▼]                           │    │
│ │ Action: [All ▼] CREATE | UPDATE | CANCEL        │    │
│ │                                                   │    │
│ │ [Apply] [Reset] [Export CSV]                     │    │
│ └─────────────────────────────────────────────────┘    │
│                                                          │
│ Showing 1,245 audit records                             │
│                                                          │
│ Date/Time     | User  | Action | Document    | Details  │
│ ─────────────────────────────────────────────────────── │
│ 28 Jan 10:30  | admin | CREATE | RCP-456     | 50,000  │
│   [View Details]                                        │
│ 27 Jan 16:45  | admin | CANCEL | PAY-123     | Duplicate│
│   [View Details]                                        │
└─────────────────────────────────────────────────────────┘
```

## 5. Технические требования

### 5.1 API Endpoints

```
# Documents
GET /api/v1/accountant/receipts
GET /api/v1/accountant/receipts/{id}
GET /api/v1/accountant/receipts/{id}/pdf

GET /api/v1/accountant/invoices
GET /api/v1/accountant/invoices/{id}
GET /api/v1/accountant/invoices/{id}/pdf

GET /api/v1/accountant/purchase-orders
GET /api/v1/accountant/purchase-orders/{id}
GET /api/v1/accountant/purchase-orders/{id}/pdf

GET /api/v1/accountant/grn
GET /api/v1/accountant/grn/{id}

GET /api/v1/accountant/procurement-payments
GET /api/v1/accountant/expense-claims

# Data Exports
GET /api/v1/accountant/export/transactions?start_date=2026-01-01&end_date=2026-01-31&format=csv
GET /api/v1/accountant/export/student-payments?start_date=2026-01-01&end_date=2026-01-31&format=excel
GET /api/v1/accountant/export/procurement-payments?start_date=2026-01-01&end_date=2026-01-31&format=csv
GET /api/v1/accountant/export/vat?period=2026-01&format=csv
GET /api/v1/accountant/export/wht?period=2026-01&format=csv

# Audit
GET /api/v1/accountant/audit-trail
```

### 5.2 PDF Generation

**Библиотеки:**
- Python: WeasyPrint, ReportLab
- Node.js: PDFKit, Puppeteer

**Требования к PDF:**
- Логотип школы вверху
- Четкая структура (таблицы с borders)
- Подпись/печать (цифровая или скан)
- Футер с номером страницы
- Watermark для cancelled documents

### 5.3 Bulk Download

Для массового скачивания PDF (например, все receipts за месяц):
- Генерировать ZIP архив
- Background job (если много документов)
- Email notification когда готово
- Link expires after 24 hours

### 5.4 Performance

- Кэшировать PDF на 1 час (если документ не изменился)
- Pagination для больших списков (100 records per page)
- Lazy loading для attachments
- Index на date fields для быстрых фильтров

### 5.5 Security

- Read-only role enforcement (на уровне DB и API)
- Audit log для всех exports и PDF downloads
- Rate limiting на export endpoints (max 10 exports per hour)
- No access to cancelled payment methods (если отменен - все равно виден, но с watermark)

## 6. Интеграция с внешними системами

### 6.1 QuickBooks/Xero Integration (Optional)

**API для автоматического импорта:**
- OAuth2 authentication
- Webhook для уведомления о новых транзакциях
- Mapping таблица (наши categories → QuickBooks accounts)

**Пример workflow:**
1. Бухгалтер настраивает OAuth подключение
2. Каждый день система отправляет новые транзакции в QuickBooks
3. Бухгалтер проверяет и categorizes в QuickBooks
4. Reconciliation делается автоматически

### 6.2 Email Delivery

**Scheduled exports:**
- Ежедневный export новых receipts/invoices
- Еженедельный summary
- Email с attached CSV/Excel файлами

**Email template:**
```
Subject: Daily Transactions Export - 28 Jan 2026

Dear Accountant,

Please find attached the daily transactions export for 28 Jan 2026:
- Receipts: 12 receipts, Total: 850,000 KES
- Payments: 3 payments, Total: 250,000 KES

Attachments:
- receipts_2026-01-28.csv
- payments_2026-01-28.csv

Best regards,
School ERP System
```

## 7. Checklist для бухгалтера (End of Month)

```
☐ Export all receipts for the month (CSV)
☐ Export all invoices issued (CSV)
☐ Export all procurement payments (CSV)
☐ Export VAT transactions (CSV)
☐ Export WHT transactions (if applicable) (CSV)
☐ Download PDFs of cancelled documents (for audit)
☐ Check audit trail for unusual activities
☐ Reconcile cash/M-Pesa/bank totals with system
☐ Prepare VAT return
☐ Prepare WHT return
☐ File returns with KRA (Kenya Revenue Authority)
```

## 8. Support for Accountant

### 8.1 Help Documentation

- "How to export data for QuickBooks"
- "Understanding VAT in Kenya education sector"
- "How to reconcile payments"
- "Reading the audit trail"

### 8.2 Contact Support

- Email: support@school.co.ke
- Phone: +254 XXX XXX XXX
- WhatsApp support group (optional)

### 8.3 Training

- Initial onboarding session (1 hour)
- Quarterly updates when new features added
- Video tutorials for common tasks
