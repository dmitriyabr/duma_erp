# Отчеты и Dashboard для менеджера школы

## Назначение

Менеджер школы (владелец, директор) использует систему для:
- **Мониторинга финансового состояния** школы в реальном времени
- **Контроля оплат** студентов и задолженностей
- **Управления операциями** (закупки, инвентарь, расходы)
- **Принятия решений** на основе данных и аналитики
- **Планирования** бюджета и прогнозирования доходов

## Основные роли пользователей

| Роль | Доступ |
|------|--------|
| **SuperAdmin** | Полный доступ ко всем модулям и отчетам |
| **Admin** | CRUD операции, просмотр отчетов, без права отменять платежи |
| **User** | Создание собственных claims/requests, просмотр своих данных |
| **Accountant** | Read-only, экспорт данных, PDF документов |
| **Manager** | Read-only к операциям, полный доступ к отчетам и аналитике |

## 1. Dashboard (главная страница для менеджера)

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
│ [💰 View Outstanding Debts]  [📊 Student Fees Report]   │
│ [📦 Check Inventory Levels]  [✅ Approve Claims]        │
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

## 2. Financial Reports

### 2.1 Profit & Loss Statement

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

### 2.2 Cash Flow Report

**Параметры:**
- Period: Daily / Weekly / Monthly
- Payment Method: All / Cash / M-Pesa / Bank / Cheque

**Структура:**
```
OPENING BALANCE: 5,800,000 KES (as at 01 Jan 2026)

CASH INFLOWS (Поступления)
├─ Student Payments
│  ├─ Cash: 3,200,000 KES
│  ├─ M-Pesa: 8,500,000 KES
│  ├─ Bank Transfer: 12,800,000 KES
│  └─ Cheque: 1,200,000 KES
│  Total: 25,700,000 KES
│
└─ Other Income: 300,000 KES

TOTAL INFLOWS: 26,000,000 KES

CASH OUTFLOWS (Выплаты)
├─ Supplier Payments: 18,500,000 KES
├─ Employee Compensations: 3,600,000 KES
└─ Other Expenses: 1,500,000 KES

TOTAL OUTFLOWS: 23,600,000 KES

NET CASH FLOW: +2,400,000 KES

CLOSING BALANCE: 8,200,000 KES (as at 31 Jan 2026)
```

**Visual:**
- Waterfall chart показывающий движение денег
- Line chart: Daily cash balance trend

### 2.3 Balance Sheet (упрощенный)

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

## 3. Student Reports

### 3.1 Student Fees Summary by Term

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

### 3.2 Aged Receivables (Дебиторская задолженность)

**Параметры:**
- As at date
- Include credit balances: Yes/No

**Структура:**
```
Student        | Total  | Current | 1-30  | 31-60 | 61-90 | 90+   | Last Payment
────────────────────────────────────────────────────────────────────────────────
John Doe       | 85,000 | 50,000  | 20,000| 10,000| 5,000 | 0     | 15 Jan 2026
Jane Smith     | 150,000| 0       | 0     | 50,000| 50,000| 50,000| 01 Nov 2025
Bob Johnson    | 45,000 | 45,000  | 0     | 0     | 0     | 0     | 28 Jan 2026
────────────────────────────────────────────────────────────────────────────────
TOTALS         |3,850,000|1,200,000|850,000|900,000|450,000|450,000|

Summary:
- 🟢 Current (0-30 days): 2,050,000 KES (53%)
- 🟡 31-60 days: 900,000 KES (23%)
- 🟠 61-90 days: 450,000 KES (12%)
- 🔴 90+ days: 450,000 KES (12%) ← URGENT ACTION NEEDED
```

**Actions:**
- [📧 Send Reminders to 90+ Days]
- [📊 Export for Follow-up]
- [🔍 View Payment History]

### 3.3 Collection Rate Trend

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

### 3.4 Discount Analysis

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

## 4. Procurement & Inventory Reports

### 4.1 Procurement Summary

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

### 4.2 Inventory Valuation

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

### 4.3 Low Stock Alert

```
Item              | Current | Min Level | Status | Action
──────────────────────────────────────────────────────────
School Shirt (M)  | 12      | 20        | 🔴     | Order 50
Notebooks A4      | 35      | 50        | 🟡     | Order 100
Pens (blue)       | 150     | 100       | 🟢     | OK
──────────────────────────────────────────────────────────
```

### 4.4 Stock Movement Report

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

## 5. Employee Compensation Reports

### 5.1 Compensation Summary

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

### 5.2 Expense Claims by Category

**Visual: Pie Chart**
```
Travel: 120,000 KES (48%)
Meals: 50,000 KES (20%)
Procurement (employee paid): 60,000 KES (24%)
Other: 20,000 KES (8%)
```

## 6. Operational Analytics

### 6.1 Revenue per Student (Trend)

**Visual: Line Chart**
```
Shows average revenue per student over 3 years:
- 2023/2024: 95,000 KES
- 2024/2025: 101,000 KES
- 2025/2026: 103,000 KES (YTD)

Growth: +8.4% over 3 years
```

### 6.2 Payment Method Distribution

**Visual: Bar Chart**
```
M-Pesa: 12,500,000 KES (49%)
Bank Transfer: 8,800,000 KES (34%)
Cash: 3,200,000 KES (12%)
Cheque: 1,200,000 KES (5%)

Insight: "M-Pesa is the most popular payment method. Consider offering M-Pesa discount."
```

### 6.3 Term-over-Term Comparison

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

### 6.4 Top 10 Debtors

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

## 7. Alerts & Automation

### 7.1 Automated Alerts (Email/SMS/In-App)

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

### 7.2 Scheduled Reports (Auto-delivery)

**Manager can schedule:**
- Daily: Cash flow summary (Email at 6 PM)
- Weekly: Student debts aging report (Email Monday 9 AM)
- Monthly: P&L statement (Email on 1st of month)
- End of Term: Full financial review (PDF report)

## 8. User Interface for Manager

### 8.1 Navigation (левый сайдбар)

```
📊 Dashboard

📈 Financial Reports
   ├─ Profit & Loss
   ├─ Cash Flow
   ├─ Balance Sheet
   └─ Revenue Analysis

👨‍🎓 Student Reports
   ├─ Fees Summary
   ├─ Aged Receivables
   ├─ Collection Rate
   ├─ Discount Analysis
   └─ Top Debtors

📦 Procurement & Inventory
   ├─ Procurement Summary
   ├─ Inventory Valuation
   ├─ Stock Movements
   └─ Low Stock Alerts

💼 Employee Compensations
   ├─ Claims Summary
   ├─ Expense Analysis
   └─ Pending Approvals

📉 Analytics
   ├─ Revenue Trends
   ├─ Payment Methods
   ├─ Term Comparisons
   └─ KPIs & Metrics

⚙️ Settings
   ├─ Report Templates
   ├─ Scheduled Reports
   ├─ Alert Preferences
   └─ My Profile
```

### 8.2 Report Page Layout

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

### 8.3 Mobile Responsiveness

**Mobile view priorities:**
1. Key metrics cards (scrollable)
2. Alerts (top priority)
3. Quick actions
4. Simplified charts (touch-friendly)
5. Collapsed navigation (hamburger menu)

## 9. KPIs & Targets

### 9.1 Financial KPIs

| KPI | Current | Target | Status |
|-----|---------|--------|--------|
| Collection Rate | 87% | 90% | 🟡 Below Target |
| Profit Margin | 51% | 45% | 🟢 Above Target |
| Revenue per Student | 103,000 | 100,000 | 🟢 Above Target |
| Discount % of Revenue | 5.3% | < 8% | 🟢 Within Target |
| Cash Balance | 8.2M | > 5M | 🟢 Healthy |
| Debt-to-Asset Ratio | 19.8% | < 30% | 🟢 Good |

### 9.2 Operational KPIs

| KPI | Current | Target | Status |
|-----|---------|--------|--------|
| Student Enrollment | 350 | 400 | 🟡 87.5% |
| Retention Rate | 95% | > 90% | 🟢 Excellent |
| Avg Collection Days | 25 | < 30 | 🟢 Good |
| Stock Turnover | 3.2x/yr | > 3x | 🟢 Efficient |
| Claims Approval Time | 5 days | < 7 days | 🟢 Fast |

## 10. Технические требования

### 10.1 API Endpoints

```
# Dashboard
GET /api/v1/manager/dashboard?period=current_term

# Financial Reports
GET /api/v1/manager/reports/profit-loss?start_date=...&end_date=...&format=pdf
GET /api/v1/manager/reports/cash-flow?period=...&format=excel
GET /api/v1/manager/reports/balance-sheet?as_at_date=...

# Student Reports
GET /api/v1/manager/reports/student-fees?term_id=...&format=excel
GET /api/v1/manager/reports/aged-receivables?as_at_date=...
GET /api/v1/manager/reports/collection-rate?period=...

# Procurement Reports
GET /api/v1/manager/reports/procurement-summary?start_date=...&end_date=...
GET /api/v1/manager/reports/inventory-valuation?as_at_date=...

# Analytics
GET /api/v1/manager/analytics/revenue-trend?period=...
GET /api/v1/manager/analytics/kpis?period=...
```

### 10.2 Real-time Updates (WebSocket)

```
ws://api/manager/live-updates

Events:
- payment_received
- invoice_created
- claim_submitted
- stock_low
- alert_triggered
```

### 10.3 Performance

- Dashboard должен загружаться < 2 секунды
- Кэширование данных на 5 минут (refresh button для manual update)
- Lazy loading для charts
- Background jobs для тяжелых отчетов (> 1000 records)

### 10.4 Export Formats

- **PDF**: Для печати и архивирования
- **Excel**: Для дальнейшего анализа
- **CSV**: Для импорта в другие системы
- **Email**: Direct send with attachments

## 11. Фичи "Nice to Have"

### 11.1 Forecasting (Прогнозирование)

**Revenue Forecast:**
- Основано на enrollment trend и collection rate
- Прогноз на следующий триместр/год
- Confidence intervals (optimistic/pessimistic/realistic)

**Cash Flow Forecast:**
- Прогноз баланса на 3-6 месяцев
- Warning if projected balance < threshold

### 11.2 Budget Management

**Set Budgets:**
- Procurement budget: 20M KES/year
- Employee expenses: 4M KES/year
- Other: 2M KES/year

**Track vs Budget:**
- Visual progress bars
- Alerts when 80% of budget used
- Variance analysis (actual vs budget)

### 11.3 Custom Reports Builder

Менеджер может создать custom отчет:
- Выбрать entities (Invoice, Payment, etc.)
- Добавить filters
- Выбрать columns
- Добавить grouping/totals
- Preview и save as template

### 11.4 Benchmarking

Сравнение с "industry averages" (if data available):
- Average fee per student in region
- Collection rate benchmark
- Profit margin benchmark
- Expense ratios

### 11.5 AI Insights (Future)

**Automated insights:**
- "Collection rate dropped 5% this term. Main reason: 15 students with debts > 90 days. Suggested action: Send reminders."
- "Procurement spending up 20%. Largest increase: Uniforms (+35%). Consider bulk discount negotiation."
- "Top 3 payment methods by volume: M-Pesa (49%), Bank (34%), Cash (12%). Consider promoting M-Pesa for faster processing."
