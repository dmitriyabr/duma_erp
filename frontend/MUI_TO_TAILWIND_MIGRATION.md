# Миграция с MUI на Tailwind CSS

## Обзор

Полная миграция фронтенда с Material-UI на Tailwind CSS и простые React компоненты.

## Текущее состояние (актуально)

- MUI **полностью удалён** (импорты/ThemeProvider/CssBaseline/зависимости)
- UI построен на Tailwind CSS + кастомных компонентах (`src/app/components/ui`)

## Цели миграции

1. Убрать все зависимости от MUI
2. Использовать Tailwind CSS для стилизации
3. Создать простые, переиспользуемые компоненты
4. Сохранить текущий дизайн и функциональность
5. Улучшить производительность (меньше bundle size)

## План миграции

### Этап 1: Настройка инфраструктуры ✅
- [x] Установить Tailwind CSS
- [x] Настроить конфигурацию Tailwind
- [x] Создать базовую структуру компонентов
- [x] Настроить систему иконок (lucide-react)

### Этап 2: Базовые компоненты ✅
- [x] Button
- [x] Input / TextField
- [x] Select
- [x] Card
- [x] Typography
- [x] Chip / Badge
- [x] Alert
- [x] Checkbox
- [x] Radio
- [x] Switch

### Этап 3: Сложные компоненты ✅
- [x] Dialog / Modal
- [x] Table (с пагинацией)
- [x] Tabs
- [x] Menu / Dropdown
- [x] Drawer / Sidebar
- [x] Tooltip
- [x] Loading / Spinner

### Этап 4: Layout компоненты ✅
- [x] AppLayout
- [x] SidebarNav
- [x] TopBar

### Этап 5: Страницы (по приоритету) 🚧
- [x] LoginPage
- [x] DashboardPage
- [x] NotFoundPage
- [x] AccessDeniedPage
- [x] PlaceholderPage
- [x] AttachmentDownloadPage
- [x] PaymentReceiptDownloadPage
- [x] StudentsPage
- [x] GradesPage
- [x] PaymentPurposesPage
- [x] TransportZonesPage
- [x] FixedFeesPage
- [x] MovementsPage
- [x] IssuancesPage
- [x] GRNListPage
- [x] PurchaseOrdersListPage
- [x] ProcurementPaymentsListPage
- [x] ExpenseClaimsListPage
- [x] InvoicesListPage
- [x] PaymentReceiptsPage
- [x] AuditTrailPage
- [x] AccountantExportPage
- [x] AgedReceivablesPage
- [x] TermsListPage
- [x] UsersPage
- [x] CollectionRatePage
- [x] DiscountAnalysisPage
- [x] StudentFeesPage
- [x] CashFlowPage
- [x] ProfitLossPage
- [x] BalanceSheetPage
- [x] SchoolPage
- [x] ItemsPage
- [x] PayoutsPage
- [x] GRNDetailPage
- [x] PayoutDetailPage
- [x] ExpenseClaimDetailPage
- [x] ProcurementPaymentDetailPage
- [x] InventoryCountPage
- [x] ReservationsPage
- [x] PurchaseOrderDetailPage
- [x] TermDetailPage
- [x] StockPage
- [x] IssueFormPage
- [x] TermFormPage
- [x] StudentHeader
- [x] OverviewTab
- [x] PaymentsTab
- [x] ItemsToIssueTab
- [x] StatementTab
- [x] InvoicesTab
- [x] StudentDetailPage
- [x] ReceivePaymentPage
- [x] CreateStudentPage
- [x] CreateInvoicePage
- [x] CatalogPage
- [x] PurchaseOrderFormPage
- [x] ProcurementPaymentFormPage
- [x] ErrorBoundary
- [x] **Все страницы и компоненты мигрированы! (60/60)**
- [x] **MUI зависимости удалены из package.json**
- [x] **Файл theme.ts удален**

### Этап 6: Финальная очистка
- [x] Удалить все импорты MUI из оставшихся файлов
- [x] Удалить theme.ts
- [x] Удалить MUI зависимости из package.json
- [x] Обновить App.tsx (убрать ThemeProvider, CssBaseline)

## Цветовая палитра (из theme.ts)

```javascript
primary: '#6366f1' (indigo)
secondary: '#64748b' (slate)
success: '#10b981' (emerald)
warning: '#f59e0b' (amber)
error: '#ef4444' (red)
info: '#3b82f6' (blue)
background: '#f8fafc'
text.primary: '#1e293b'
text.secondary: '#64748b'
```

## Структура компонентов

```
src/app/components/
  ui/
    Button.tsx
    Input.tsx
    Select.tsx
    Card.tsx
    Dialog.tsx
    Table.tsx
    ...
```

## Примечания

- Использовать `lucide-react` для иконок вместо @mui/icons-material
- Сохранить все текущие стили и поведение
- Обеспечить accessibility (ARIA атрибуты)
- Поддержать responsive дизайн

