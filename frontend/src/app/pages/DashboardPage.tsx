import {
  UserPlus,
  CreditCard,
  ShoppingCart,
  Truck,
  Package,
  Receipt,
  Shirt,
  CheckCircle,
} from 'lucide-react'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { isAccountant, canSeeDashboardSummary } from '../utils/permissions'
import { api } from '../services/api'
import type { ApiResponse } from '../types/api'
import { formatMoney } from '../utils/format'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Typography } from '../components/ui/Typography'
import { Spinner } from '../components/ui/Spinner'
import { Alert } from '../components/ui/Alert'

const quickActions: Array<{
  label: string
  path: string
  state?: Record<string, unknown>
  icon: React.ReactNode
}> = [
  { label: 'Claim Expense', path: '/compensations/claims/new', icon: <Receipt className="w-5 h-5" /> },
  { label: 'Receive Student Payment', path: '/payments/new', icon: <CreditCard className="w-5 h-5" /> },
  { label: 'Issue Item From Stock', path: '/inventory/issue', icon: <Shirt className="w-5 h-5" /> },
  { label: 'Issue Reserved Item', path: '/inventory/reservations', icon: <CheckCircle className="w-5 h-5" /> },
  { label: 'Admit New Student', path: '/students/new', icon: <UserPlus className="w-5 h-5" /> },
  { label: 'Sell Items To Student', path: '/billing/invoices/new', icon: <ShoppingCart className="w-5 h-5" /> },
  { label: 'Track Order Items', path: '/procurement/orders/new', icon: <Truck className="w-5 h-5" /> },
  { label: 'Receive Order Items', path: '/procurement/orders', icon: <Package className="w-5 h-5" /> },
]

interface DashboardData {
  active_students_count: number
  total_revenue_this_year: string
  this_term_revenue: string
  this_term_invoiced: string
  collection_rate_percent: number | null
  total_expenses_this_year: string
  procurement_total_this_year: string
  employee_compensations_this_year: string
  cash_balance: string
  student_debts_total: string
  student_debts_count: number
  supplier_debt: string
  credit_balances_total: string
  pending_claims_count: number
  pending_claims_amount: string
  pending_grn_count: number
  active_term_display_name: string | null
  current_year: number
}

export const DashboardPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const showQuickActions = !isAccountant(user)
  const showSummary = canSeeDashboardSummary(user)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!showSummary) return
    let cancelled = false
    // Avoid calling setState synchronously within an effect body (react-hooks/set-state-in-effect).
    // We only need to show loading and clear previous error before the request.
    queueMicrotask(() => {
      if (!cancelled) {
        setLoading(true)
        setError(null)
      }
    })
    api
      .get<ApiResponse<DashboardData>>('/dashboard')
      .then((res) => {
        if (!cancelled && res.data?.data) setDashboard(res.data.data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.message ?? 'Failed to load dashboard')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [showSummary])

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Dashboard
      </Typography>

      {showQuickActions && (
        <div className="mb-8">
          <Typography variant="subtitle1" className="mb-4" color="secondary">
            Quick Actions
          </Typography>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {quickActions.map((action) => (
              <Button
                key={action.label}
                variant="contained"
                size="large"
                fullWidth
                onClick={() => navigate(action.path, action.state ? { state: action.state } : undefined)}
                className="justify-start gap-2 py-6 px-4 text-base font-semibold shadow-sm hover:shadow-md"
              >
                {action.icon}
                {action.label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {showSummary && (
        <>
          <Typography variant="subtitle1" className="mb-4" color="secondary">
            Overview
          </Typography>
          {loading && (
            <div className="flex justify-center py-8">
              <Spinner size="large" />
            </div>
          )}
          {error && (
            <Alert severity="error" className="mb-4">
              {error}
            </Alert>
          )}
          {!loading && dashboard && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Active Students
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {dashboard.active_students_count}
                  </Typography>
                  <button
                    onClick={() => navigate('/students')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View list
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    This Term Revenue
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {formatMoney(dashboard.this_term_revenue)}
                  </Typography>
                  {dashboard.active_term_display_name && (
                    <Typography variant="caption" color="secondary" className="block mt-1">
                      {dashboard.active_term_display_name}
                    </Typography>
                  )}
                  <button
                    onClick={() => navigate('/reports/students/student-fees')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View report
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Collection Rate
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {dashboard.collection_rate_percent != null ? `${dashboard.collection_rate_percent}%` : '—'}
                  </Typography>
                  <button
                    onClick={() => navigate('/reports/students/collection-rate')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View report
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Expenses (This Year)
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {formatMoney(dashboard.total_expenses_this_year)}
                  </Typography>
                  <button
                    onClick={() => navigate('/reports/profit-loss')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View report
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Student Debts
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {formatMoney(dashboard.student_debts_total)}
                  </Typography>
                  <Typography variant="caption" color="secondary" className="block mt-1">
                    {dashboard.student_debts_count} students
                  </Typography>
                  <button
                    onClick={() => navigate('/reports/students/aged-receivables')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View report
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Supplier Debt
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {formatMoney(dashboard.supplier_debt)}
                  </Typography>
                  <button
                    onClick={() => navigate('/procurement/orders')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View orders
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Credit Balances
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {formatMoney(dashboard.credit_balances_total)}
                  </Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Pending Claims
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {formatMoney(dashboard.pending_claims_amount)}
                  </Typography>
                  <Typography variant="caption" color="secondary" className="block mt-1">
                    {dashboard.pending_claims_count} claims
                  </Typography>
                  <button
                    onClick={() => navigate('/compensations/claims')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    Review claims
                  </button>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="secondary">
                    Pending GRN
                  </Typography>
                  <Typography variant="h6" className="mt-2">
                    {dashboard.pending_grn_count}
                  </Typography>
                  <button
                    onClick={() => navigate('/procurement/grn')}
                    className="mt-2 text-xs text-primary hover:underline"
                  >
                    View GRN
                  </button>
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}

      {!showSummary && showQuickActions && (
        <>
          <Typography variant="subtitle1" className="mb-4" color="secondary">
            Overview
          </Typography>
          <Typography variant="body2" color="secondary">
            Summary and reports are available to Admin and SuperAdmin.
          </Typography>
        </>
      )}
    </div>
  )
}
