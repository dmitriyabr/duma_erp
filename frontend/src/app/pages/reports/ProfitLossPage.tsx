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
import { DateRangeShortcuts, getDateRangeForPreset } from '../../components/DateRangeShortcuts'

interface RevenueLine {
  label: string
  amount: string
  monthly?: Record<string, string>
}

interface ExpenseLine {
  label: string
  amount: string
  monthly?: Record<string, string>
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
  months?: string[]
  gross_revenue_monthly?: Record<string, string>
  total_discounts_monthly?: Record<string, string>
  net_revenue_monthly?: Record<string, string>
  total_expenses_monthly?: Record<string, string>
  net_profit_monthly?: Record<string, string>
}

const defaultRange = () => getDateRangeForPreset('this_year')

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function monthLabel(yyyyMm: string): string {
  const [y, m] = yyyyMm.split('-').map(Number)
  return `${MONTH_NAMES[m - 1]} ${y}`
}

export const ProfitLossPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<ProfitLossData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    const fromD = new Date(dateFrom)
    const toD = new Date(dateTo)
    const multiMonth = fromD.getFullYear() !== toD.getFullYear() ||
      fromD.getMonth() !== toD.getMonth()
    api
      .get<ApiResponse<ProfitLossData>>('/reports/profit-loss', {
        params: {
          date_from: dateFrom,
          date_to: dateTo,
          ...(multiMonth ? { breakdown: 'monthly' } : {}),
        },
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
            <DateRangeShortcuts
              dateFrom={dateFrom}
              dateTo={dateTo}
              onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }}
              onRun={runReport}
            />
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
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{monthLabel(mo)}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>Total (KES)</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>Amount (KES)</strong></TableCell>
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {data.revenue_lines.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell>{row.label}</TableCell>
                    {data.months && data.months.length > 0 ? (
                      <>
                        {data.months.map((mo) => (
                          <TableCell key={mo} align="right">{formatMoney(row.monthly?.[mo] ?? '0')}</TableCell>
                        ))}
                        <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                      </>
                    ) : (
                      <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    )}
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell><strong>Gross Revenue</strong></TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{formatMoney(data.gross_revenue_monthly?.[mo] ?? '0')}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>{formatMoney(data.gross_revenue)}</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>{formatMoney(data.gross_revenue)}</strong></TableCell>
                  )}
                </TableRow>
                <TableRow>
                  <TableCell>Less: Discounts</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right">-{formatMoney(data.total_discounts_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right">-{formatMoney(data.total_discounts)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right">-{formatMoney(data.total_discounts)}</TableCell>
                  )}
                </TableRow>
                <TableRow>
                  <TableCell><strong>Net Revenue</strong></TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{formatMoney(data.net_revenue_monthly?.[mo] ?? '0')}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>{formatMoney(data.net_revenue)}</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>{formatMoney(data.net_revenue)}</strong></TableCell>
                  )}
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Expenses</strong></TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{monthLabel(mo)}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>Total (KES)</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>Amount (KES)</strong></TableCell>
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {data.expense_lines.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell>{row.label}</TableCell>
                    {data.months && data.months.length > 0 ? (
                      <>
                        {data.months.map((mo) => (
                          <TableCell key={mo} align="right">{formatMoney(row.monthly?.[mo] ?? '0')}</TableCell>
                        ))}
                        <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                      </>
                    ) : (
                      <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    )}
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell><strong>Total Expenses</strong></TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{formatMoney(data.total_expenses_monthly?.[mo] ?? '0')}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>{formatMoney(data.total_expenses)}</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>{formatMoney(data.total_expenses)}</strong></TableCell>
                  )}
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
