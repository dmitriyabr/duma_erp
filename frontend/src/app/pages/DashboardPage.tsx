import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Link,
  Typography,
} from '@mui/material'
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import PaymentIcon from '@mui/icons-material/Payment'
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import InventoryIcon from '@mui/icons-material/Inventory'
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong'
import CheckroomIcon from '@mui/icons-material/Checkroom'
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { isAccountant, canSeeDashboardSummary } from '../utils/permissions'
import { api } from '../services/api'
import type { ApiResponse } from '../types/api'
import { formatMoney } from '../utils/format'

const quickActions: Array<{
  label: string
  path: string
  state?: Record<string, unknown>
  icon: React.ReactNode
}> = [
  { label: 'Admit New Student', path: '/students/new', icon: <PersonAddIcon /> },
  { label: 'Sell Items To Student', path: '/billing/invoices/new', icon: <ShoppingCartIcon /> },
  { label: 'Receive Student Payment', path: '/payments/new', icon: <PaymentIcon /> },
  { label: 'Track Order Items', path: '/procurement/orders/new', icon: <LocalShippingIcon /> },
  { label: 'Receive Order Items', path: '/procurement/orders', icon: <InventoryIcon /> },
  { label: 'Track Payment', path: '/procurement/payments/new', icon: <ReceiptLongIcon /> },
  { label: 'Issue Item From Stock', path: '/inventory/issue', icon: <CheckroomIcon /> },
  { label: 'Issue Reserved Item', path: '/inventory/reservations', icon: <AssignmentTurnedInIcon /> },
]

interface DashboardData {
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
    setLoading(true)
    setError(null)
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
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Dashboard
      </Typography>

      {showQuickActions && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'text.secondary' }}>
            Quick Actions
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
                lg: 'repeat(4, 1fr)',
              },
              gap: 2,
            }}
          >
            {quickActions.map((action) => (
              <Button
                key={action.label}
                variant="contained"
                size="large"
                fullWidth
                onClick={() => navigate(action.path, action.state ? { state: action.state } : undefined)}
                startIcon={action.icon}
                sx={{
                  py: 2.5,
                  px: 2,
                  justifyContent: 'flex-start',
                  textTransform: 'none',
                  fontSize: '1rem',
                  fontWeight: 600,
                  boxShadow: 1,
                  '&:hover': { boxShadow: 3 },
                }}
              >
                {action.label}
              </Button>
            ))}
          </Box>
        </Box>
      )}

      {showSummary && (
        <>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'text.secondary' }}>
            Overview
          </Typography>
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          )}
          {error && (
            <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>
          )}
          {!loading && dashboard && (
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  sm: 'repeat(2, 1fr)',
                  md: 'repeat(4, 1fr)',
                },
                gap: 2,
              }}
            >
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Revenue (This Year)</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.total_revenue_this_year)}</Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">This Term Revenue</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.this_term_revenue)}</Typography>
                  {dashboard.active_term_display_name && (
                    <Typography variant="caption" display="block" color="text.secondary">{dashboard.active_term_display_name}</Typography>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Collection Rate</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>
                    {dashboard.collection_rate_percent != null ? `${dashboard.collection_rate_percent}%` : '—'}
                  </Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Expenses (This Year)</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.total_expenses_this_year)}</Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Student Debts</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.student_debts_total)}</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">{dashboard.student_debts_count} students</Typography>
                  <Link
                    component="button"
                    variant="body2"
                    onClick={() => navigate('/reports/aged-receivables')}
                    sx={{ mt: 1, fontSize: '0.75rem' }}
                  >
                    View report
                  </Link>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Supplier Debt</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.supplier_debt)}</Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Credit Balances</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.credit_balances_total)}</Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Pending Claims</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{formatMoney(dashboard.pending_claims_amount)}</Typography>
                  <Typography variant="caption" color="text.secondary">{dashboard.pending_claims_count} claims</Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary">Pending GRN</Typography>
                  <Typography variant="h6" sx={{ mt: 1 }}>{dashboard.pending_grn_count}</Typography>
                </CardContent>
              </Card>
            </Box>
          )}
        </>
      )}

      {!showSummary && showQuickActions && (
        <>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'text.secondary' }}>
            Overview
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Summary and reports are available to Admin and SuperAdmin.
          </Typography>
        </>
      )}
    </Box>
  )
}
