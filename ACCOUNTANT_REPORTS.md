# Отчеты для бухгалтера

## Назначение
Внешний бухгалтер использует систему для:
- Подготовки финансовой отчетности
- Расчета налогов (VAT, Corporation Tax, Withholding Tax)
- Reconciliation банковских выписок
- Анализа cash flow школы
- Подготовки audit trail для проверок

## 1. Финансовые отчеты (Financial Reports)

### 1.1 Profit & Loss Statement (Отчет о прибылях и убытках)
**Параметры:**
- Период: дата начала - дата конца
- Группировка: по месяцам / кварталам / году
- Формат экспорта: PDF, Excel

**Структура:**
```
ДОХОДЫ (Revenue)
├─ Student Fees (плата за обучение)
│  ├─ School Fee
│  ├─ Transport Fee
│  ├─ Uniform Bundle
│  ├─ Admission Fee
│  └─ Other Fees
├─ Less: Discounts Applied
└─ Net Student Revenue

РАСХОДЫ (Expenses)
├─ Procurement (закупки)
│  ├─ Uniforms
│  ├─ Stationery
│  ├─ Food supplies
│  └─ Other inventory
├─ Employee Compensations
│  ├─ Travel expenses
│  ├─ Meals & Entertainment
│  └─ Other reimbursements
└─ Total Expenses

NET PROFIT/LOSS
```

### 1.2 Cash Flow Statement (Отчет о движении денежных средств)
**Параметры:**
- Период: дата начала - дата конца
- Группировка: по дням / неделям / месяцам

**Структура:**
```
OPENING BALANCE (начальный остаток)

RECEIPTS (Поступления)
├─ Student Payments (платежи студентов)
│  ├─ Cash
│  ├─ M-Pesa
│  ├─ Bank Transfer
│  └─ Cheque
└─ Other Income

PAYMENTS (Выплаты)
├─ Supplier Payments (оплата поставщикам)
├─ Employee Compensations (компенсации сотрудникам)
└─ Other Expenses

NET CASH FLOW

CLOSING BALANCE (конечный остаток)
```

### 1.3 Balance Sheet (Баланс)
**Параметры:**
- На дату (snapshot на конкретную дату)

**Структура:**
```
ASSETS (Активы)
├─ Current Assets
│  ├─ Cash on Hand
│  ├─ Accounts Receivable (Student Debts)
│  └─ Inventory (Stock Value at cost)
└─ Total Assets

LIABILITIES (Обязательства)
├─ Current Liabilities
│  ├─ Accounts Payable (Supplier Debts)
│  ├─ Student Credit Balances (prepayments)
│  └─ Employee Payable (pending compensations)
└─ Total Liabilities

EQUITY (Капитал)
└─ Retained Earnings

TOTAL LIABILITIES + EQUITY
```

## 2. Налоговые отчеты (Tax Reports)

### 2.1 VAT Report (16% in Kenya)
**Параметры:**
- Tax period (обычно месяц или квартал)
- Формат: Excel, PDF

**Структура:**
```
OUTPUT VAT (VAT Collected)
├─ Student Fees subject to VAT
│  ├─ Gross Amount
│  └─ VAT Amount (16%)
└─ Total Output VAT

INPUT VAT (VAT Paid)
├─ Procurement with VAT
│  ├─ Gross Amount
│  └─ VAT Amount (16%)
└─ Total Input VAT

VAT PAYABLE / REFUNDABLE
```

**Примечание:** Некоторые образовательные услуги могут быть VAT-exempt в Кении. Нужна гибкость для настройки.

### 2.2 Withholding Tax Report
**Параметры:**
- Tax period
- Тип WHT: on services, rent, professional fees, etc.

**Структура:**
```
Поставщик | PIN | Сумма платежа | Ставка WHT | Сумма WHT | Дата платежа
```

Типичные ставки в Кении:
- Professional fees: 5%
- Consultancy: 5%
- Rent: 10%
- Management fees: 5%

### 2.3 Corporation Tax Computation
**Параметры:**
- Financial year (обычно календарный год)

**Структура:**
```
Net Profit (from P&L)
Add back: Non-deductible expenses
Less: Capital allowances
Less: Other allowable deductions
Taxable Income
Corporation Tax @ 30%
Less: Advance tax paid
Tax Payable / (Refundable)
```

## 3. Операционные отчеты (Operational Reports)

### 3.1 Student Fees Summary
**Параметры:**
- Term (триместр)
- Grade/Class
- Status: All / Paid / Partially Paid / Unpaid

**Столбцы:**
- Student Name
- Class
- Total Invoiced
- Total Paid
- Balance Outstanding
- Credit Balance
- Last Payment Date

**Итоги:**
- Total Invoiced for Term
- Total Collected
- Total Outstanding
- Collection Rate %

### 3.2 Aged Receivables (Дебиторская задолженность по срокам)
**Параметры:**
- As at date (на дату)

**Структура:**
```
Student | Total Debt | Current | 1-30 days | 31-60 days | 61-90 days | 90+ days
```

### 3.3 Procurement Report
**Параметры:**
- Период: дата начала - дата конца
- Supplier (опционально)
- Status: All / Draft / Ordered / Received / Cancelled

**Столбцы:**
- PO Number
- Date
- Supplier
- Total Amount (с VAT)
- VAT Amount
- Status
- Payment Status (Unpaid / Partially Paid / Paid)
- Outstanding Amount

### 3.4 Supplier Aging (Кредиторская задолженность по срокам)
**Параметры:**
- As at date

**Структура:**
```
Supplier | Total Debt | Current | 1-30 days | 31-60 days | 61-90 days | 90+ days
```

### 3.5 Employee Compensation Report
**Параметры:**
- Период: дата начала - дата конца
- Employee (опционально)
- Status: All / Pending / Approved / Paid

**Столбцы:**
- Claim Number
- Date
- Employee
- Description
- Amount
- Status
- Approval Date
- Payment Date

### 3.6 Inventory Valuation Report
**Параметры:**
- As at date
- Category (опционально)

**Столбцы:**
- Item Code
- Item Name
- Category
- Quantity on Hand
- Unit Cost (latest purchase price)
- Total Value

**Итог:** Total Inventory Value

### 3.7 Stock Movement Report
**Параметры:**
- Период: дата начала - дата конца
- Item (опционально)
- Movement Type: All / Receive / Issue / Adjust / WriteOff

**Столбцы:**
- Date
- Reference (PO#, Request#, etc.)
- Item
- Movement Type
- Quantity
- Balance After
- User
- Notes

## 4. Аналитические отчеты (Analytics)

### 4.1 Revenue by Fee Type
**Параметры:**
- Период
- Группировка: Term / Month / Quarter

**Визуализация:** Pie chart или bar chart
```
School Fee: X KES (Y%)
Transport: X KES (Y%)
Uniform: X KES (Y%)
Other: X KES (Y%)
```

### 4.2 Collection Rate Trend
**Параметры:**
- Период (обычно 12 месяцев)

**График:** Line chart показывающий % сбора платежей по месяцам

### 4.3 Discount Analysis
**Параметры:**
- Период
- Discount Type (опционально)

**Столбцы:**
- Discount Name
- Number of Students
- Total Discount Amount
- Average Discount per Student

## 5. Аудит и Reconciliation

### 5.1 Audit Trail (Журнал аудита)
**Параметры:**
- Период
- Entity Type: All / Invoice / Payment / PurchaseOrder / etc.
- User (опционально)
- Action: All / CREATE / UPDATE / DELETE / APPROVE / CANCEL

**Столбцы:**
- Timestamp
- User
- Entity Type
- Entity ID
- Action
- Old Values (JSON)
- New Values (JSON)
- Comment

### 5.2 Payment Reconciliation Report
**Параметры:**
- Период
- Payment Method: All / Cash / M-Pesa / Bank Transfer / Cheque

**Структура:**
```
Payment Method: M-Pesa
├─ Opening Balance
├─ Total Receipts
│  └─ List of all payments with receipt numbers
├─ Total Expected
└─ Variance (if any)
```

### 5.3 Bank Reconciliation Helper
**Параметры:**
- Period
- Bank account

**Две колонки:**
- System Records (из Payment)
- Bank Statement (manual entry или import)

Показывает:
- Matched transactions ✓
- Unmatched in system
- Unmatched in bank

## 6. Формат экспорта

Все отчеты должны поддерживать:
- **PDF** - для архивирования и печати
- **Excel (.xlsx)** - для дальнейшей обработки бухгалтером
- **CSV** - для импорта в бухгалтерские системы (QuickBooks, Xero, etc.)

### Требования к Excel экспорту:
- Форматирование: заголовки жирным, итоги жирным + border
- Числовые форматы: валюта с 2 знаками после запятой
- Даты: DD/MM/YYYY или YYYY-MM-DD
- Фильтры на заголовках (Excel AutoFilter)
- Freeze panes на заголовках

## 7. Периодичность отчетов

| Отчет | Периодичность | Дедлайн |
|-------|---------------|---------|
| VAT Report | Ежемесячно | 20-е число следующего месяца |
| Withholding Tax | Ежемесячно | 20-е число следующего месяца |
| P&L Statement | Ежемесячно | 5-е число следующего месяца |
| Cash Flow | Еженедельно | Monday morning |
| Student Fees Summary | По окончании Term | 1 неделя после Term end |
| Aged Receivables | Ежемесячно | 1-е число месяца |
| Corporation Tax | Ежегодно | 6 месяцев после fiscal year end |

## 8. Технические требования

### API endpoints для отчетов:
```
GET /api/v1/reports/profit-loss?start_date=2026-01-01&end_date=2026-01-31&format=pdf
GET /api/v1/reports/cash-flow?start_date=2026-01-01&end_date=2026-01-31&format=excel
GET /api/v1/reports/balance-sheet?as_at_date=2026-01-31&format=pdf
GET /api/v1/reports/vat?period=2026-01&format=excel
GET /api/v1/reports/student-fees?term_id=1&format=excel
GET /api/v1/reports/aged-receivables?as_at_date=2026-01-31&format=excel
GET /api/v1/reports/procurement?start_date=2026-01-01&end_date=2026-01-31&format=excel
GET /api/v1/reports/audit-trail?start_date=2026-01-01&end_date=2026-01-31&format=excel
```

### Кэширование:
- Отчеты могут быть тяжелыми - использовать background jobs
- Кэшировать результаты на 1 час для одинаковых параметров
- Показывать progress bar при генерации больших отчетов

### Производительность:
- Отчеты за большие периоды (год) делать через background jobs (Celery/Redis)
- Email notification когда отчет готов
- Хранить generated reports в S3/storage на 7 дней

## 9. Дополнительные фичи

### 9.1 Scheduled Reports
Бухгалтер может настроить автоматическую отправку отчетов по email:
- VAT report - каждое 15-е число месяца
- P&L - каждое 1-е число месяца
- Cash Flow - каждый понедельник

### 9.2 Report Templates
Возможность сохранять параметры отчетов как шаблоны:
- "Monthly VAT for submission"
- "End of Term Fees Summary"
- "Quarterly P&L for Board"

### 9.3 Comparative Reports
Отчеты с сравнением периодов:
- P&L: Current month vs Previous month vs Same month last year
- Collection rate: Term 1 vs Term 2 vs Term 3

### 9.4 Notes and Annotations
Бухгалтер может добавлять notes к отчетам:
- Например, пояснение почему VAT refundable в этом месяце
- Notes сохраняются с отчетом и видны при следующем просмотре
