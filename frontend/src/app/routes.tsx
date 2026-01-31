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
import { IssueFormPage } from './pages/inventory/IssueFormPage'
import { MovementsPage } from './pages/inventory/MovementsPage'
import { IssuancesPage } from './pages/inventory/IssuancesPage'
import { ReservationsPage } from './pages/inventory/ReservationsPage'
import { InventoryCountPage } from './pages/inventory/InventoryCountPage'
import { ItemsPage } from './pages/inventory/ItemsPage'
import { ExpenseClaimsListPage } from './pages/compensations/ExpenseClaimsListPage'
import { ExpenseClaimDetailPage } from './pages/compensations/ExpenseClaimDetailPage'
import { PayoutsPage } from './pages/compensations/PayoutsPage'
import { PayoutDetailPage } from './pages/compensations/PayoutDetailPage'
import { AuditTrailPage } from './pages/accountant/AuditTrailPage'
import { AccountantExportPage } from './pages/accountant/AccountantExportPage'
import { InvoicesListPage } from './pages/accountant/InvoicesListPage'
import { PaymentReceiptsPage } from './pages/accountant/PaymentReceiptsPage'
import { AttachmentDownloadPage } from './pages/AttachmentDownloadPage'
import { PaymentReceiptDownloadPage } from './pages/PaymentReceiptDownloadPage'
import { AgedReceivablesPage } from './pages/reports/AgedReceivablesPage'
import { StudentFeesPage } from './pages/reports/StudentFeesPage'

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
          <Route path="billing/invoices" element={<InvoicesListPage />} />
          <Route path="billing/invoices/new" element={<CreateInvoicePage />} />
          <Route path="billing/payments" element={<PlaceholderPage title="Payments" />} />
          <Route path="billing/allocations" element={<PlaceholderPage title="Allocations" />} />
          <Route path="billing/statement" element={<PlaceholderPage title="Statement" />} />
          <Route path="billing/discounts" element={<PlaceholderPage title="Discounts" />} />
          <Route path="inventory" element={<PlaceholderPage title="Warehouse" />} />
          <Route path="inventory/items" element={<ItemsPage />} />
          <Route path="inventory/stock" element={<StockPage />} />
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
          <Route path="compensations/claims/:claimId" element={<ExpenseClaimDetailPage />} />
          <Route path="compensations/payouts" element={<PayoutsPage />} />
          <Route path="compensations/payouts/:payoutId" element={<PayoutDetailPage />} />
          <Route path="reports" element={<PlaceholderPage title="Reports" />} />
          <Route path="reports/aged-receivables" element={<AgedReceivablesPage />} />
          <Route path="reports/student-fees" element={<StudentFeesPage />} />
          <Route path="audit" element={<AuditTrailPage />} />
          <Route path="payments/new" element={<ReceivePaymentPage />} />
          <Route path="payments" element={<PaymentReceiptsPage />} />
          <Route path="accountant/export" element={<AccountantExportPage />} />
          <Route path="accountant/documents" element={<PlaceholderPage title="Documents" />} />
          <Route path="settings" element={<PlaceholderPage title="Settings" />} />
          <Route path="settings/users" element={<UsersPage />} />
          <Route path="settings/grades" element={<GradesPage />} />
          <Route path="settings/school" element={<SchoolPage />} />
          <Route path="settings/transport-zones" element={<TransportZonesPage />} />
          <Route path="settings/payment-purposes" element={<PaymentPurposesPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
