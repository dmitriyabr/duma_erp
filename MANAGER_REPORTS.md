# Отчеты и Dashboard для руководства школы

## Назначение

Владелец/директор школы (роли **SuperAdmin** или **Admin**) использует систему для:
- **Мониторинга финансового состояния** школы в реальном времени
- **Контроля оплат** студентов и задолженностей
- **Управления операциями** (закупки, инвентарь, расходы)
- **Принятия решений** на основе данных и аналитики
- **Планирования** бюджета и прогнозирования доходов

**Роли:** Отдельной роли «Manager» нет.
- **Quick Actions** (кнопки быстрых действий над дашбордом): видят **User**, **Admin**, **SuperAdmin** — оставляем для всех, кто ходит на главную.
- **Остальной контент дашборда** (карточки, графики, алерты, лента активности) и **весь раздел Reports**: только **SuperAdmin** и **Admin**.
- Accountant — свои разделы (см. ACCOUNTANT_REPORTS.md); у него отдельное меню без отчётов руководства.

---

## Распределение: что где

| Где | Что |
|-----|-----|
| **Dashboard (главная)** | Сводные карточки, ключевые метрики, 1–2 графика, быстрые действия, алерты, лента активности. Всё, что нужно «с первого взгляда». |
| **Раздел Reports** | Полноценные отчёты с фильтрами, таблицами, экспортом. Каждый отчёт — отдельная страница (или подраздел). |

Ниже детализация по разделам.

---

## 1. Dashboard (главная страница)

*Страница уже есть (/).*
- **Quick Actions** (кнопки над контентом): доступны **User**, **Admin**, **SuperAdmin** — не скрывать для User.
- **Остальные блоки** (Period Selector, карточки, графики, алерты, лента активности): только **SuperAdmin**, **Admin**. Для User под Quick Actions показывать пустое место или краткое приветствие, без сводок и отчётов.

### 1.1 Period Selector
```
┌─────────────────────────────────────────────────────────┐
│  Academic Year:  [2025/2026 ▼]                          │
│  View:          ◉ Current Term  ○ Term 1  ○ Term 2      │
│                 ○ Custom Range: [01/01/26] - [31/01/26] │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Financial Overview (8 карточек)

**Первый ряд - Доходы:**
```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Total Revenue    │ │ This Term        │ │ Collection Rate  │ │ Avg Fee/Student  │
│ 45,300,000 KES  │ │ 15,450,000 KES  │ │ 87%             │ │ 103,000 KES     │
│ This Year       │ │ Term 2 2025/26  │ │ ↑ 5% vs prev    │ │ ↓ 2% vs prev    │
│ ↑ 18% vs prev   │ │ ↑ 12% vs Term 1 │ │ Target: 90%     │ │                 │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
```

**Второй ряд - Расходы и баланс:**
```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Total Expenses   │ │ Procurement      │ │ Employee Claims  │ │ Cash Balance     │
│ 22,100,000 KES  │ │ 18,500,000 KES  │ │ 3,600,000 KES   │ │ 8,200,000 KES   │
│ This Year       │ │ Inventory       │ │ Compensations   │ │ Available       │
│ ↑ 15% vs prev   │ │ ↑ 20% vs prev   │ │ ↑ 10% vs prev   │ │ ↑ 25% vs prev   │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
```

### 1.3 Key Metrics Cards (второстепенные метрики)

```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Student Debts    │ │ Supplier Debts   │ │ Credit Balances  │ │ Pending Claims   │
│ 3,850,000 KES   │ │ 2,150,000 KES   │ │ 680,000 KES     │ │ 450,000 KES     │
│ 92 students     │ │ 15 suppliers    │ │ 45 students     │ │ 12 claims       │
│ 🔴 85+ days:     │ │ 🟡 30+ days:     │ │ Prepayments     │ │ Awaiting        │
│    1,200,000    │ │    850,000      │ │                 │ │ approval        │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
```

### 1.4 Charts & Visualizations

**Revenue vs Expenses Trend (последние 12 месяцев)**
```
Line chart с тремя линиями:
- Blue solid line: Revenue (доходы)
- Red solid line: Expenses (расходы)
- Green dashed line: Net Profit (прибыль)
- Gray shaded area: Break-even zone

Y-axis: Amount (KES)
X-axis: Months (Feb 2025 - Jan 2026)
```

**Collection Rate by Term (текущий год)**
```
Bar chart:
- Term 1: 92% (Green) - 12,500,000 / 13,500,000
- Term 2: 87% (Yellow) - 15,450,000 / 17,800,000
- Term 3: -- (Gray) - Not started

Target line: 90% (dashed red line)
```

**Revenue Breakdown (Pie Chart)**
```
School Fees: 32,000,000 KES (71%)
Transport: 8,500,000 KES (19%)
Uniforms: 3,200,000 KES (7%)
Other: 1,600,000 KES (3%)
```

**Student Enrollment Trend (Line Chart)**
```
Shows student count over 3 years:
- 2023/2024: 280 students
- 2024/2025: 315 students
- 2025/2026: 350 students (current)
Growth rate: +11% year-over-year
```

### 1.5 Quick Actions

```
┌─────────────────────────────────────────────────────────┐
│ Quick Actions:                                           │
│ [🧾 Claim Expense]  [💳 Receive Student Payment]        │
│ [👕 Issue Item From Stock]  [✅ Issue Reserved Item]     │
│ [👤 Admit New Student]  [🛒 Sell Items To Student]       │
│ [🚚 Track Order Items]  [📦 Receive Order Items]         │
└─────────────────────────────────────────────────────────┘
```

### 1.6 Alerts & Notifications

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Alerts & Warnings                                     │
├─────────────────────────────────────────────────────────┤
│ 🔴 URGENT | 15 students with debts > 90 days            │
│    Total: 1,200,000 KES | [View Details]                │
├─────────────────────────────────────────────────────────┤
│ 🟡 WARNING | Low stock alert: 3 items below minimum     │
│    School Shirts, Notebooks, Pens | [View Inventory]    │
├─────────────────────────────────────────────────────────┤
│ 🔵 INFO | 12 expense claims pending approval            │
│    Total: 450,000 KES | [Review Claims]                 │
└─────────────────────────────────────────────────────────┘
```

### 1.7 Recent Activity Feed

```
┌─────────────────────────────────────────────────────────┐
│ Recent Activity (Last 24 Hours)                          │
├─────────────────────────────────────────────────────────┤
│ 🟢 Today 14:30  | Payment received: 125,000 KES         │
│                  5 students paid school fees            │
│ 🔵 Today 11:15  | Purchase Order created: PO-2026-0156  │
│                  Stationery supplies - 85,000 KES       │
│ 🟡 Today 09:00  | Expense Claim submitted: CLM-2026-089 │
│                  Travel expenses - 15,000 KES           │
│ 🟢 Yesterday    | Invoice batch created: 45 invoices    │
│                  Term 2 school fees issued              │
│                                                          │
│ [View All Activity →]                                    │
└─────────────────────────────────────────────────────────┘
```

**Итог по Dashboard:** На главной — только сводка и быстрый доступ. Полные таблицы и детальные отчёты живут в разделе **Reports**; Quick Actions ведут на соответствующие страницы отчётов или разделов (Aged Receivables, Student Fees Report, Inventory, Approve Claims).

---

## 2. Раздел Reports (меню и страницы)

*В сайдбаре один пункт **Reports** с подпунктами. Доступ: SuperAdmin, Admin. Каждый подпункт — отдельная страница с параметрами, кнопкой «Сформировать», таблицами/графиками и экспортом (PDF/Excel).*

**Структура меню Reports:**

| Подраздел | Отчёты (страницы) |
|-----------|--------------------|
| **Financial** | Profit & Loss, Cash Flow, Balance Sheet |
| **Students** | Fees Summary by Term, Aged Receivables, Collection Rate Trend, Discount Analysis, Top Debtors |
| **Procurement & Inventory** | Procurement Summary, Inventory Valuation, Low Stock Alert, Stock Movement Report |
| **Compensations** | Compensation Summary, Expense Claims by Category |
| **Analytics** | Revenue per Student Trend, Payment Method Distribution, Term-over-Term Comparison, KPIs & Metrics |

Ниже — описание каждого отчёта (содержимое страниц раздела Reports).

---

## 3. Financial Reports (страницы в разделе Reports)

### 3.1 Profit & Loss Statement

**Параметры:**
- Period: Custom date range или по триместрам
- Group by: Month / Quarter / Year
- Compare with: Previous period / Same period last year

**Структура:**
```
REVENUE (Доходы)
├─ Student Fees
│  ├─ School Fee: 32,000,000 KES
│  ├─ Transport Fee: 8,500,000 KES
│  ├─ Admission Fee: 2,800,000 KES
│  └─ Other Fees: 1,200,000 KES
├─ Uniform Sales: 3,200,000 KES
└─ Gross Revenue: 47,700,000 KES

LESS: Discounts & Adjustments
└─ Student Discounts: -2,400,000 KES

NET REVENUE: 45,300,000 KES

EXPENSES (Расходы)
├─ Procurement (Inventory)
│  ├─ Uniforms: 12,000,000 KES
│  ├─ Stationery: 3,500,000 KES
│  ├─ Food Supplies: 2,800,000 KES
│  └─ Other: 200,000 KES
│  Total: 18,500,000 KES
│
├─ Employee Compensations: 3,600,000 KES
│
└─ Total Expenses: 22,100,000 KES

NET PROFIT: 23,200,000 KES
Profit Margin: 51.2%
```

**Actions:**
- [📥 Export PDF] [📊 Export Excel] [📧 Email]
- [📈 Compare with Previous Year]
- [📝 Add Notes]

### 3.2 Cash Flow Report

**Параметры:**
- Period: Custom date range (from/to)
- Breakdown: Monthly (если диапазон больше 1 месяца)
- Payment Method (optional): фильтр по способу оплаты входящих student payments (например `mpesa`, `bank_transfer`)

**Структура:**
```
OPENING BALANCE: 5,800,000 KES (as at 01 Jan 2026)

CASH INFLOWS (Поступления)
├─ Student Payments
│  ├─ School Fee: 14,200,000 KES
│  ├─ Transport: 9,800,000 KES
│  ├─ Other Fees: 1,700,000 KES
│  └─ Unallocated / Credit: 300,000 KES
│  Total: 26,000,000 KES
│
└─ Other Income: (optional / future)

TOTAL INFLOWS: 26,000,000 KES

CASH OUTFLOWS (Выплаты)
├─ Supplier Payments: 18,500,000 KES
├─ Employee Compensations: 3,600,000 KES
└─ Other Expenses: (optional / future)

TOTAL OUTFLOWS: 23,600,000 KES

NET CASH FLOW: +2,400,000 KES

CLOSING BALANCE: 8,200,000 KES (as at 31 Jan 2026)
```

**Примечание (важно):** Разбивка inflows по категориям делается по тому, куда платеж был
аллоцирован **в этот же день** (по `invoice_type`). Остаток показывается как
`Unallocated / Credit`, чтобы сумма строк всегда сходилась с общей суммой денег,
полученных за период.

**Visual:**
- Waterfall chart показывающий движение денег
- Line chart: Daily cash balance trend

### 3.3 Balance Sheet (упрощенный)

**На дату:**
```
ASSETS (Активы)
├─ Current Assets
│  ├─ Cash on Hand: 8,200,000 KES
│  ├─ Accounts Receivable (Student Debts): 3,850,000 KES
│  └─ Inventory at Cost: 4,500,000 KES
└─ Total Assets: 16,550,000 KES

LIABILITIES (Обязательства)
├─ Current Liabilities
│  ├─ Accounts Payable (Supplier Debts): 2,150,000 KES
│  ├─ Student Credit Balances: 680,000 KES
│  └─ Employee Payable (Pending Claims): 450,000 KES
└─ Total Liabilities: 3,280,000 KES

NET EQUITY: 13,270,000 KES

Debt-to-Asset Ratio: 19.8%
Current Ratio: 5.05 (healthy)
```

## 4. Student Reports (страницы в разделе Reports)

### 4.1 Student Fees Summary by Term

**Параметры:**
- Term: Term 1 / Term 2 / Term 3
- Class/Grade: All / Grade 6 / Grade 7 / etc.
- Payment Status: All / Fully Paid / Partially Paid / Unpaid

**Таблица:**
```
Class    | Students | Total Invoiced | Total Paid  | Balance    | Rate
─────────────────────────────────────────────────────────────────────
Grade 6  | 45       | 4,500,000     | 4,200,000  | 300,000   | 93%
Grade 7  | 52       | 6,240,000     | 5,100,000  | 1,140,000 | 82%
Grade 8  | 48       | 6,720,000     | 6,300,000  | 420,000   | 94%
─────────────────────────────────────────────────────────────────────
TOTAL    | 145      | 17,460,000    | 15,600,000 | 1,860,000 | 89%
```

**Drill-down:** Клик на класс → список студентов с деталями

### 4.2 Aged Receivables (Дебиторская задолженность)

**Параметры:**
- As at date
- Include credit balances: Yes/No

**Структура:**
```
Student        | Total  | Current (0-30) | 31-60 | 61-90 | 90+   | Last Payment
────────────────────────────────────────────────────────────────────────────────
John Doe       | 85,000 | 70,000         | 10,000| 5,000 | 0     | 15 Jan 2026
Jane Smith     | 150,000| 0              | 50,000| 50,000| 50,000| 01 Nov 2025
Bob Johnson    | 45,000 | 45,000         | 0     | 0     | 0     | 28 Jan 2026
────────────────────────────────────────────────────────────────────────────────
TOTALS         |3,850,000|2,050,000      |900,000|450,000|450,000|

Summary:
- 🟢 Current (0-30 days): 2,050,000 KES (53%) — не просрочено или до 30 дней просрочки
- 🟡 31-60 days: 900,000 KES (23%)
- 🟠 61-90 days: 450,000 KES (12%)
- 🔴 90+ days: 450,000 KES (12%) ← URGENT ACTION NEEDED
```

**Actions:**
- [📧 Send Reminders to 90+ Days]
- [📊 Export for Follow-up]
- [🔍 View Payment History]

### 4.3 Collection Rate Trend

**Visual: Line Chart**
```
Shows collection rate % over last 12 months:
- Jan 2025: 85%
- Feb 2025: 88%
- Mar 2025: 92%
- ...
- Dec 2025: 90%
- Jan 2026: 87%

Target: 90% (red dashed line)
Average: 88.5%
```

### 4.4 Discount Analysis

**Параметры:**
- Period
- Discount Type: All / Sibling / Staff Child / Scholarship / etc.

**Таблица:**
```
Discount Type      | Students | Total Amount | Avg/Student | % of Revenue
─────────────────────────────────────────────────────────────────────────
Sibling Discount   | 35       | 1,400,000   | 40,000      | 3.1%
Staff Child        | 8        | 800,000     | 100,000     | 1.8%
Scholarship        | 5        | 200,000     | 40,000      | 0.4%
─────────────────────────────────────────────────────────────────────────
TOTAL              | 48       | 2,400,000   | 50,000      | 5.3%
```

**Insight:** "Discounts represent 5.3% of gross revenue. This is within target range (< 8%)."

## 5. Procurement & Inventory Reports (страницы в разделе Reports)

### 5.1 Procurement Summary

**Параметры:**
- Period
- Supplier (optional)
- Category (optional)

**Таблица:**
```
Supplier        | POs | Total Amount | Paid      | Outstanding | Status
────────────────────────────────────────────────────────────────────────
ABC Uniforms    | 8   | 12,500,000  | 11,000,000| 1,500,000   | 🟡
XYZ Stationery  | 5   | 3,800,000   | 3,800,000 | 0           | 🟢
Food Supplies   | 12  | 2,800,000   | 2,200,000 | 600,000     | 🟡
────────────────────────────────────────────────────────────────────────
TOTAL           | 25  | 19,100,000  | 17,000,000| 2,100,000   |

Outstanding Breakdown:
- Current (0-30 days): 1,500,000 KES
- 31-60 days: 600,000 KES
- 61+ days: 0 KES
```

### 5.2 Inventory Valuation

**As at date:**
```
Category        | Items | Quantity | Unit Cost | Total Value | Turnover
─────────────────────────────────────────────────────────────────────────
Uniforms        | 15    | 450      | 1,200     | 540,000     | 2.5x/yr
Stationery      | 45    | 2,500    | 50        | 125,000     | 4.0x/yr
Books           | 120   | 3,800    | 350       | 1,330,000   | 1.2x/yr
Food Supplies   | 80    | 1,200    | 200       | 240,000     | 12x/yr
─────────────────────────────────────────────────────────────────────────
TOTAL           | 260   | 7,950    |           | 2,235,000   |
```

### 5.3 Low Stock Alert

```
Item              | Current | Min Level | Status | Action
──────────────────────────────────────────────────────────
School Shirt (M)  | 12      | 20        | 🔴     | Order 50
Notebooks A4      | 35      | 50        | 🟡     | Order 100
Pens (blue)       | 150     | 100       | 🟢     | OK
──────────────────────────────────────────────────────────
```

### 5.4 Stock Movement Report

**Параметры:**
- Period
- Movement Type: All / Receive / Issue / Adjust / WriteOff

**Таблица:**
```
Date       | Type   | Item          | Qty | Ref#        | User  | Balance
─────────────────────────────────────────────────────────────────────────
28 Jan 26  | Receive| School Shirt  | +50 | GRN-2026-45 | Admin | 62
27 Jan 26  | Issue  | School Shirt  | -15 | REQ-2026-89 | User2 | 12
25 Jan 26  | Issue  | Notebooks     | -100| REQ-2026-87 | User1 | 35
```

## 6. Employee Compensation Reports (страницы в разделе Reports)

### 6.1 Compensation Summary

**Параметры:**
- Period
- Status: All / Pending / Approved / Paid

**Таблица:**
```
Employee       | Claims | Total Amount | Approved  | Paid     | Pending
─────────────────────────────────────────────────────────────────────────
James Teacher  | 5      | 85,000      | 85,000    | 70,000   | 15,000
Mary Admin     | 3      | 45,000      | 45,000    | 45,000   | 0
John Driver    | 8      | 120,000     | 100,000   | 80,000   | 20,000
─────────────────────────────────────────────────────────────────────────
TOTAL          | 16     | 250,000     | 230,000   | 195,000  | 35,000

Pending Approval: 2 claims, 20,000 KES
Approved but Unpaid: 4 claims, 35,000 KES
```

### 6.2 Expense Claims by Category

**Visual: Pie Chart**
```
Travel: 120,000 KES (48%)
Meals: 50,000 KES (20%)
Procurement (employee paid): 60,000 KES (24%)
Other: 20,000 KES (8%)
```

## 7. Operational Analytics (страницы в разделе Reports)

### 7.1 Revenue per Student (Trend)

**Visual: Line Chart**
```
Shows average revenue per student over 3 years:
- 2023/2024: 95,000 KES
- 2024/2025: 101,000 KES
- 2025/2026: 103,000 KES (YTD)

Growth: +8.4% over 3 years
```

### 7.2 Payment Method Distribution

**Visual: Bar Chart**
```
M-Pesa: 12,500,000 KES (49%)
Bank Transfer: 8,800,000 KES (34%)
Cash: 3,200,000 KES (12%)
Cheque: 1,200,000 KES (5%)

Insight: "M-Pesa is the most popular payment method. Consider offering M-Pesa discount."
```

### 7.3 Term-over-Term Comparison

**Таблица:**
```
Metric              | Term 1      | Term 2      | Change
──────────────────────────────────────────────────────────
Students Enrolled   | 340         | 350         | +10 (+3%)
Total Invoiced      | 13,500,000  | 17,800,000  | +32%
Total Collected     | 12,420,000  | 15,486,000  | +25%
Collection Rate     | 92%         | 87%         | -5%
Avg Fee/Student     | 39,700      | 50,900      | +28%
Discounts Given     | 800,000     | 1,200,000   | +50%
```

**Insight:** "Collection rate dropped 5%. Follow up with parents on outstanding payments."

### 7.4 Top 10 Debtors

```
Student         | Class | Total Debt | Days Overdue | Last Contact
────────────────────────────────────────────────────────────────────
Jane Smith      | Gr 8  | 150,000    | 95          | 15 Jan 2026
Bob Wilson      | Gr 7  | 125,000    | 87          | Never
Alice Brown     | Gr 6  | 95,000     | 105         | 10 Dec 2025
...
────────────────────────────────────────────────────────────────────
TOTAL (Top 10)  |       | 850,000    |             |
```

**Actions:**
- [📧 Send Bulk Reminder]
- [☎️ Mark for Phone Call]
- [📄 Generate Demand Letter]

## 8. Alerts & Automation

### 8.1 Automated Alerts (Email/SMS/In-App)

**Daily:**
- Summary of payments received today
- Low stock items alert
- Pending approvals reminder

**Weekly:**
- Collection rate update
- Top 10 debtors list
- Expense claims pending approval

**Monthly:**
- Month-end financial summary (Revenue, Expenses, Profit)
- Student enrollment changes
- Procurement spending summary

**Custom Triggers:**
- Student debt > 100,000 KES
- Supplier payment overdue > 60 days
- Inventory item out of stock
- Large payment received (> 500,000 KES)

### 8.2 Scheduled Reports (Auto-delivery)

**Admin/SuperAdmin может настроить:**
- Daily: Cash flow summary (Email at 6 PM)
- Weekly: Student debts aging report (Email Monday 9 AM)
- Monthly: P&L statement (Email on 1st of month)
- End of Term: Full financial review (PDF report)

## 9. User Interface: Dashboard + Reports

*Общее меню для SuperAdmin/Admin. Dashboard — главная страница; Reports — один пункт в сайдбаре с подменю.*

### 9.1 Навигация (левый сайдбар)

```
📊 Dashboard          ← главная: карточки, графики, Quick Actions, алерты, лента активности

📋 Reports            ← один пункт меню, при раскрытии:
   ├─ Financial
   │  ├─ Profit & Loss
   │  ├─ Cash Flow
   │  └─ Balance Sheet
   ├─ Students
   │  ├─ Fees Summary by Term
   │  ├─ Aged Receivables
   │  ├─ Collection Rate Trend
   │  ├─ Discount Analysis
   │  └─ Top Debtors
   ├─ Procurement & Inventory
   │  ├─ Procurement Summary
   │  ├─ Inventory Valuation
   │  ├─ Low Stock Alert
   │  └─ Stock Movement Report
   ├─ Compensations
   │  ├─ Compensation Summary
   │  └─ Expense Claims by Category
   └─ Analytics
      ├─ Revenue per Student Trend
      ├─ Payment Method Distribution
      ├─ Term-over-Term Comparison
      └─ KPIs & Metrics

… остальные пункты меню (Students, Billing, Warehouse, Procurement, Compensations, Settings — **SuperAdmin only**)
```

Quick Actions на Dashboard видны **User**, **Admin**, **SuperAdmin** и ведут на основные операционные действия (claims, payments, issuing stock, procurement).

### 9.2 Report Page Layout

```
┌─────────────────────────────────────────────────────────┐
│ ← Back to Reports                                        │
│                                                          │
│ 📊 Profit & Loss Statement                              │
│                                                          │
│ ┌──────────────────────────────────────────────────┐   │
│ │ Parameters:                                       │   │
│ │ Period: ◉ This Term  ○ This Year  ○ Custom       │   │
│ │ Compare: ☑ Previous Period  ☐ Same Period LY     │   │
│ │ [Generate Report]                                 │   │
│ └──────────────────────────────────────────────────┘   │
│                                                          │
│ ┌──────────────────────────────────────────────────┐   │
│ │ Actions:                                          │   │
│ │ [📥 PDF] [📊 Excel] [📧 Email] [📌 Save Template]│   │
│ └──────────────────────────────────────────────────┘   │
│                                                          │
│ ┌──────────────────────────────────────────────────┐   │
│ │        REPORT CONTENT                             │   │
│ │        (table, charts, graphs)                    │   │
│ │                                                    │   │
│ │  💡 Insights:                                     │   │
│ │  "Revenue increased 12% vs previous term"         │   │
│ │  "Profit margin is healthy at 51%"                │   │
│ │  "⚠️ Expenses up 15% - review procurement"        │   │
│ └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 9.3 Mobile Responsiveness

**Mobile view priorities:**
1. Key metrics cards (scrollable)
2. Alerts (top priority)
3. Quick actions
4. Simplified charts (touch-friendly)
5. Collapsed navigation (hamburger menu)

## 10. KPIs & Targets

*Могут отображаться на Dashboard (карточки/таблица) и/или отдельной страницей Reports → Analytics → KPIs & Metrics.*

### 10.1 Financial KPIs

| KPI | Current | Target | Status |
|-----|---------|--------|--------|
| Collection Rate | 87% | 90% | 🟡 Below Target |
| Profit Margin | 51% | 45% | 🟢 Above Target |
| Revenue per Student | 103,000 | 100,000 | 🟢 Above Target |
| Discount % of Revenue | 5.3% | < 8% | 🟢 Within Target |
| Cash Balance | 8.2M | > 5M | 🟢 Healthy |
| Debt-to-Asset Ratio | 19.8% | < 30% | 🟢 Good |

### 10.2 Operational KPIs

| KPI | Current | Target | Status |
|-----|---------|--------|--------|
| Student Enrollment | 350 | 400 | 🟡 87.5% |
| Retention Rate | 95% | > 90% | 🟢 Excellent |
| Avg Collection Days | 25 | < 30 | 🟢 Good |
| Stock Turnover | 3.2x/yr | > 3x | 🟢 Efficient |
| Claims Approval Time | 5 days | < 7 days | 🟢 Fast |

## 11. Технические требования

*Доступ к API дашборда и отчётов: SuperAdmin, Admin (проверка роли в middleware).*

### 11.1 API Endpoints

```
# Dashboard (главная страница)
GET /api/v1/dashboard?period=current_term
# Возвращает: карточки (revenue, expenses, collection rate, …), ключевые метрики, данные для 1–2 графиков, алерты, последнюю активность.

# Отчёты (раздел Reports) — единый префикс /api/v1/reports/ или по ресурсам
GET /api/v1/reports/profit-loss?date_from=...&date_to=...&breakdown=monthly&format=xlsx
GET /api/v1/reports/cash-flow?date_from=...&date_to=...&payment_method=mpesa&breakdown=monthly&format=xlsx
GET /api/v1/reports/balance-sheet?as_at_date=...

GET /api/v1/reports/student-fees?term_id=...&format=excel
GET /api/v1/reports/aged-receivables?as_at_date=...
GET /api/v1/reports/collection-rate?period=...

GET /api/v1/reports/procurement-summary?start_date=...&end_date=...
GET /api/v1/reports/inventory-valuation?as_at_date=...

GET /api/v1/reports/analytics/revenue-trend?period=...
GET /api/v1/reports/analytics/kpis?period=...
```

### 11.2 Real-time Updates (WebSocket) — опционально

```
ws://api/dashboard/live-updates   (или /api/reports/live-updates)

Events: payment_received, invoice_created, claim_submitted, stock_low, alert_triggered
```

### 11.3 Performance

- Dashboard должен загружаться < 2 секунды
- Кэширование данных на 5 минут (refresh button для manual update)
- Lazy loading для charts
- Background jobs для тяжелых отчетов (> 1000 records)

### 11.4 Export Formats

- **PDF**: Для печати и архивирования
- **Excel**: Для дальнейшего анализа
- **CSV**: Для импорта в другие системы
- **Email**: Direct send with attachments

## 12. Фичи "Nice to Have"

### 12.1 Forecasting (Прогнозирование)

**Revenue Forecast:**
- Основано на enrollment trend и collection rate
- Прогноз на следующий триместр/год
- Confidence intervals (optimistic/pessimistic/realistic)

**Cash Flow Forecast:**
- Прогноз баланса на 3-6 месяцев
- Warning if projected balance < threshold

### 12.2 Budget Management

**Set Budgets:**
- Procurement budget: 20M KES/year
- Employee expenses: 4M KES/year
- Other: 2M KES/year

**Track vs Budget:**
- Visual progress bars
- Alerts when 80% of budget used
- Variance analysis (actual vs budget)

### 12.3 Custom Reports Builder

Admin/SuperAdmin может создать custom отчёт:
- Выбрать entities (Invoice, Payment, etc.)
- Добавить filters
- Выбрать columns
- Добавить grouping/totals
- Preview и save as template

### 12.4 Benchmarking

Сравнение с "industry averages" (if data available):
- Average fee per student in region
- Collection rate benchmark
- Profit margin benchmark
- Expense ratios

### 12.5 AI Insights (Future)

**Automated insights:**
- "Collection rate dropped 5% this term. Main reason: 15 students with debts > 90 days. Suggested action: Send reminders."
- "Procurement spending up 20%. Largest increase: Uniforms (+35%). Consider bulk discount negotiation."
- "Top 3 payment methods by volume: M-Pesa (49%), Bank (34%), Cash (12%). Consider promoting M-Pesa for faster processing."
