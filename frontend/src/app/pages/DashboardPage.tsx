import {
  Box,
  Button,
  Card,
  CardContent,
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
import { useAuth } from '../auth/AuthContext'
import { isAccountant } from '../utils/permissions'

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

const metrics = [
  { label: 'Active Students', value: '—' },
  { label: 'Outstanding Invoices', value: '—' },
  { label: 'Payments (This Month)', value: '—' },
  { label: 'Stock Alerts', value: '—' },
]

export const DashboardPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const showQuickActions = !isAccountant(user)

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

      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'text.secondary' }}>
        Overview
      </Typography>
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
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                {metric.label}
              </Typography>
              <Typography variant="h5" sx={{ mt: 1 }}>
                {metric.value}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  )
}
