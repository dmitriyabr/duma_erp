import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { ReferencedDataProvider } from './contexts/ReferencedDataContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AppLayout } from './layout/AppLayout'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { UsersPage } from './pages/settings/UsersPage'
import { GradesPage } from './pages/settings/GradesPage'
import { CatalogPage } from './pages/settings/CatalogPage'
import { TransportZonesPage } from './pages/terms/TransportZonesPage'
import { FixedFeesPage } from './pages/terms/FixedFeesPage'
import { TermsListPage } from './pages/terms/TermsListPage'
import { TermFormPage } from './pages/terms/TermFormPage'
import { TermDetailPage } from './pages/terms/TermDetailPage'
import { PaymentPurposesPage } from './pages/settings/PaymentPurposesPage'
import { SchoolPage } from './pages/settings/SchoolPage'
import { PurchaseOrdersListPage } from './pages/procurement/PurchaseOrdersListPage'
import { PurchaseOrderFormPage } from './pages/procurement/PurchaseOrderFormPage'
import { PurchaseOrderDetailPage } from './pages/procurement/PurchaseOrderDetailPage'
import { GRNListPage } from './pages/procurement/GRNListPage'
import { GRNDetailPage } from './pages/procurement/GRNDetailPage'
import { ProcurementPaymentsListPage } from './pages/procurement/ProcurementPaymentsListPage'
import { ProcurementPaymentFormPage } from './pages/procurement/ProcurementPaymentFormPage'
import { ProcurementPaymentDetailPage } from './pages/procurement/ProcurementPaymentDetailPage'
import { StudentsPage } from './pages/students/StudentsPage'
import { CreateStudentPage } from './pages/students/CreateStudentPage'
import { StudentDetailPage } from './pages/students/StudentDetailPage'
import { CreateInvoicePage } from './pages/students/CreateInvoicePage'
import { ReceivePaymentPage } from './pages/students/ReceivePaymentPage'
import { StockPage } from './pages/inventory/StockPage'
import { RestockPage } from './pages/inventory/RestockPage'
import { IssueFormPage } from './pages/inventory/IssueFormPage'
import { MovementsPage } from './pages/inventory/MovementsPage'
import { IssuancesPage } from './pages/inventory/IssuancesPage'
import { ReservationsPage } from './pages/inventory/ReservationsPage'
import { InventoryCountPage } from './pages/inventory/InventoryCountPage'
import { ItemsPage } from './pages/inventory/ItemsPage'
import { ExpenseClaimsListPage } from './pages/compensations/ExpenseClaimsListPage'
import { ExpenseClaimDetailPage } from './pages/compensations/ExpenseClaimDetailPage'
import { NewExpenseClaimPage } from './pages/compensations/NewExpenseClaimPage'
import { PayoutsPage } from './pages/compensations/PayoutsPage'
import { PayoutDetailPage } from './pages/compensations/PayoutDetailPage'
import { AuditTrailPage } from './pages/accountant/AuditTrailPage'
import { AccountantExportPage } from './pages/accountant/AccountantExportPage'
import { BankReconciliationPage } from './pages/accountant/BankReconciliationPage'
import { BankStatementsPage } from './pages/accountant/BankStatementsPage'
import { InvoicesListPage } from './pages/accountant/InvoicesListPage'
import { PaymentReceiptsPage } from './pages/accountant/PaymentReceiptsPage'
import { AttachmentDownloadPage } from './pages/AttachmentDownloadPage'
import { PaymentReceiptDownloadPage } from './pages/PaymentReceiptDownloadPage'
import { AgedReceivablesPage } from './pages/reports/AgedReceivablesPage'
import { BalanceSheetPage } from './pages/reports/BalanceSheetPage'
import { CashFlowPage } from './pages/reports/CashFlowPage'
import { CollectionRatePage } from './pages/reports/CollectionRatePage'
import { DiscountAnalysisPage } from './pages/reports/DiscountAnalysisPage'
import { InventoryValuationPage } from './pages/reports/InventoryValuationPage'
import { LowStockAlertPage } from './pages/reports/LowStockAlertPage'
import { ProcurementSummaryPage } from './pages/reports/ProcurementSummaryPage'
import { ProfitLossPage } from './pages/reports/ProfitLossPage'
import { CompensationSummaryPage } from './pages/reports/CompensationSummaryPage'
import { ExpenseClaimsByCategoryPage } from './pages/reports/ExpenseClaimsByCategoryPage'
import { KpisPage } from './pages/reports/KpisPage'
import { PaymentMethodDistributionPage } from './pages/reports/PaymentMethodDistributionPage'
import { RevenueTrendPage } from './pages/reports/RevenueTrendPage'
import { StockMovementPage } from './pages/reports/StockMovementPage'
import { TermComparisonPage } from './pages/reports/TermComparisonPage'
import { StudentFeesPage } from './pages/reports/StudentFeesPage'
import { ReportsSectionLayout } from './pages/reports/ReportsSectionLayout'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) {
    return null
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

const SuperAdminOnly: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== 'SuperAdmin') return <Navigate to="/access-denied" replace />
  return <>{children}</>
}

const AdminOnly: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== 'SuperAdmin' && user.role !== 'Admin') return <Navigate to="/access-denied" replace />
  return <>{children}</>
}

export const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/access-denied" element={<AccessDeniedPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ErrorBoundary>
                <ReferencedDataProvider>
                  <AppLayout />
                </ReferencedDataProvider>
              </ErrorBoundary>
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="attachment/:id/download" element={<AttachmentDownloadPage />} />
          <Route path="payment/:id/receipt" element={<PaymentReceiptDownloadPage />} />
          <Route path="students" element={<StudentsPage />} />
          <Route path="students/new" element={<CreateStudentPage />} />
          <Route path="students/:studentId" element={<StudentDetailPage />} />
          <Route path="students/:studentId/invoices/new" element={<CreateInvoicePage />} />
          <Route path="billing" element={<PlaceholderPage title="Billing" />} />
          <Route path="billing/terms" element={<TermsListPage />} />
          <Route path="billing/terms/new" element={<TermFormPage />} />
          <Route path="billing/terms/:termId" element={<TermDetailPage />} />
          <Route path="billing/terms/:termId/edit" element={<TermFormPage />} />
          <Route path="billing/fixed-fees" element={<FixedFeesPage />} />
          <Route path="billing/catalog" element={<CatalogPage />} />
          <Route path="billing/catalog/items" element={<CatalogPage />} />
          <Route path="billing/catalog/categories" element={<CatalogPage />} />
          <Route path="billing/catalog/variants" element={<CatalogPage />} />
          <Route path="billing/invoices" element={<InvoicesListPage />} />
          <Route path="billing/invoices/new" element={<CreateInvoicePage />} />
          <Route path="billing/payments" element={<PlaceholderPage title="Payments" />} />
          <Route path="billing/allocations" element={<PlaceholderPage title="Allocations" />} />
          <Route path="billing/statement" element={<PlaceholderPage title="Statement" />} />
          <Route path="billing/discounts" element={<PlaceholderPage title="Discounts" />} />
          <Route path="inventory" element={<PlaceholderPage title="Warehouse" />} />
          <Route path="inventory/items" element={<ItemsPage />} />
          <Route path="inventory/stock" element={<StockPage />} />
          <Route path="inventory/restock" element={<RestockPage />} />
          <Route path="inventory/reorder" element={<Navigate to="/inventory/restock" replace />} />
          <Route path="inventory/issue" element={<IssueFormPage />} />
          <Route path="inventory/movements" element={<MovementsPage />} />
          <Route path="inventory/issuances" element={<IssuancesPage />} />
          <Route path="inventory/reservations" element={<ReservationsPage />} />
          <Route
            path="inventory/inventory-count"
            element={<InventoryCountPage />}
          />
          <Route path="procurement" element={<PlaceholderPage title="Procurement" />} />
          <Route path="procurement/orders" element={<PurchaseOrdersListPage />} />
          <Route path="procurement/orders/new" element={<PurchaseOrderFormPage />} />
          <Route path="procurement/orders/:orderId" element={<PurchaseOrderDetailPage />} />
          <Route path="procurement/orders/:orderId/edit" element={<PurchaseOrderFormPage />} />
          <Route path="procurement/grn" element={<GRNListPage />} />
          <Route path="procurement/grn/:grnId" element={<GRNDetailPage />} />
          <Route path="procurement/payments" element={<ProcurementPaymentsListPage />} />
          <Route path="procurement/payments/new" element={<ProcurementPaymentFormPage />} />
          <Route path="procurement/payments/:paymentId" element={<ProcurementPaymentDetailPage />} />
          <Route path="compensations" element={<PlaceholderPage title="Compensations" />} />
          <Route path="compensations/claims" element={<ExpenseClaimsListPage />} />
          <Route path="compensations/claims/new" element={<NewExpenseClaimPage />} />
          <Route path="compensations/claims/:claimId" element={<ExpenseClaimDetailPage />} />
          <Route path="compensations/payouts" element={<PayoutsPage />} />
          <Route path="compensations/payouts/:payoutId" element={<PayoutDetailPage />} />
          <Route path="reports">
            <Route index element={<Navigate to="financial/profit-loss" replace />} />
            <Route path="financial" element={<ReportsSectionLayout basePath="/reports/financial" tabs={[{ path: 'profit-loss', label: 'Profit & Loss' }, { path: 'cash-flow', label: 'Cash Flow' }, { path: 'balance-sheet', label: 'Balance Sheet' }]} />}>
              <Route index element={<Navigate to="profit-loss" replace />} />
              <Route path="profit-loss" element={<ProfitLossPage />} />
              <Route path="cash-flow" element={<CashFlowPage />} />
              <Route path="balance-sheet" element={<BalanceSheetPage />} />
            </Route>
            <Route path="students" element={<ReportsSectionLayout basePath="/reports/students" tabs={[{ path: 'aged-receivables', label: 'Students Debt' }, { path: 'student-fees', label: 'Student Fees by Term' }, { path: 'collection-rate', label: 'Collection Rate Trend' }, { path: 'discount-analysis', label: 'Discount Analysis' }]} />}>
              <Route index element={<Navigate to="aged-receivables" replace />} />
              <Route path="aged-receivables" element={<AgedReceivablesPage />} />
              <Route path="student-fees" element={<StudentFeesPage />} />
              <Route path="collection-rate" element={<CollectionRatePage />} />
              <Route path="discount-analysis" element={<DiscountAnalysisPage />} />
            </Route>
            <Route path="procurement" element={<ReportsSectionLayout basePath="/reports/procurement" tabs={[{ path: 'summary', label: 'Procurement Summary' }, { path: 'inventory-valuation', label: 'Inventory Valuation' }, { path: 'low-stock-alert', label: 'Low Stock Alert' }, { path: 'stock-movement', label: 'Stock Movement' }]} />}>
              <Route index element={<Navigate to="summary" replace />} />
              <Route path="summary" element={<ProcurementSummaryPage />} />
              <Route path="inventory-valuation" element={<InventoryValuationPage />} />
              <Route path="low-stock-alert" element={<LowStockAlertPage />} />
              <Route path="stock-movement" element={<StockMovementPage />} />
            </Route>
            <Route path="compensations" element={<ReportsSectionLayout basePath="/reports/compensations" tabs={[{ path: 'summary', label: 'Compensation Summary' }, { path: 'by-category', label: 'Expense Claims by Category' }]} />}>
              <Route index element={<Navigate to="summary" replace />} />
              <Route path="summary" element={<CompensationSummaryPage />} />
              <Route path="by-category" element={<ExpenseClaimsByCategoryPage />} />
            </Route>
            <Route path="analytics" element={<ReportsSectionLayout basePath="/reports/analytics" tabs={[{ path: 'revenue-trend', label: 'Revenue per Student' }, { path: 'payment-method', label: 'Payment Method Distribution' }, { path: 'term-comparison', label: 'Term Comparison' }, { path: 'kpis', label: 'KPIs & Metrics' }]} />}>
              <Route index element={<Navigate to="revenue-trend" replace />} />
              <Route path="revenue-trend" element={<RevenueTrendPage />} />
              <Route path="payment-method" element={<PaymentMethodDistributionPage />} />
              <Route path="term-comparison" element={<TermComparisonPage />} />
              <Route path="kpis" element={<KpisPage />} />
            </Route>
          </Route>
          <Route
            path="audit"
            element={
              <AdminOnly>
                <AuditTrailPage />
              </AdminOnly>
            }
          />
          <Route path="payments/new" element={<ReceivePaymentPage />} />
          <Route path="payments" element={<PaymentReceiptsPage />} />
          <Route path="accountant/export" element={<AccountantExportPage />} />
          <Route path="accountant/bank-statements" element={<BankStatementsPage />} />
          <Route path="bank-reconciliation" element={<BankReconciliationPage />} />
          <Route path="accountant/documents" element={<PlaceholderPage title="Documents" />} />
          <Route path="settings" element={<PlaceholderPage title="Settings" />} />
          <Route
            path="settings/users"
            element={
              <SuperAdminOnly>
                <UsersPage />
              </SuperAdminOnly>
            }
          />
          <Route
            path="settings/grades"
            element={
              <SuperAdminOnly>
                <GradesPage />
              </SuperAdminOnly>
            }
          />
          <Route
            path="settings/school"
            element={
              <SuperAdminOnly>
                <SchoolPage />
              </SuperAdminOnly>
            }
          />
          <Route
            path="settings/transport-zones"
            element={
              <SuperAdminOnly>
                <TransportZonesPage />
              </SuperAdminOnly>
            }
          />
          <Route
            path="settings/payment-purposes"
            element={
              <SuperAdminOnly>
                <PaymentPurposesPage />
              </SuperAdminOnly>
            }
          />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
