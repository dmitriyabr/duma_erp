import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'

interface RevenueLine {
  label: string
  amount: string
}

interface ExpenseLine {
  label: string
  amount: string
}

interface ProfitLossData {
  date_from: string
  date_to: string
  revenue_lines: RevenueLine[]
  gross_revenue: string
  total_discounts: string
  net_revenue: string
  expense_lines: ExpenseLine[]
  total_expenses: string
  net_profit: string
  profit_margin_percent: number | null
}

const defaultDateFrom = () => {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}
const defaultDateTo = () => new Date().toISOString().slice(0, 10)

export const ProfitLossPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [data, setData] = useState<ProfitLossData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<ProfitLossData>>('/reports/profit-loss', {
        params: { date_from: dateFrom, date_to: dateTo },
      })
      .then((res) => {
        if (res.data?.data) setData(res.data.data)
      })
      .catch((err) => {
        if (err.response?.status === 403) setForbidden(true)
        else setError(err.response?.data?.detail ?? 'Failed to load report')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (canSeeReports(user)) runReport()
    else setForbidden(true)
  }, [user])

  if (forbidden) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Profit & Loss</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Profit & Loss</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <TextField
              label="From"
              type="date"
              size="small"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 160 }}
            />
            <TextField
              label="To"
              type="date"
              size="small"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 160 }}
            />
            <Button variant="contained" onClick={runReport}>Run report</Button>
          </Box>
        </CardContent>
      </Card>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!loading && data && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Period: {data.date_from} — {data.date_to}
          </Typography>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Revenue</strong></TableCell>
                  <TableCell align="right"><strong>Amount (KES)</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.revenue_lines.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell><strong>Gross Revenue</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.gross_revenue)}</strong></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Less: Discounts</TableCell>
                  <TableCell align="right">-{formatMoney(data.total_discounts)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><strong>Net Revenue</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.net_revenue)}</strong></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Expenses</strong></TableCell>
                  <TableCell align="right"><strong>Amount (KES)</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.expense_lines.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell><strong>Total Expenses</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.total_expenses)}</strong></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom><strong>Net Profit</strong>: {formatMoney(data.net_profit)}</Typography>
              {data.profit_margin_percent != null && (
                <Typography variant="body2" color="text.secondary">
                  Profit margin: {data.profit_margin_percent}%
                </Typography>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select period and run report.</Typography>
      )}
    </Box>
  )
}
