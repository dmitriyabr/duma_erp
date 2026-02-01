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
import { downloadReportExcel } from '../../utils/reportExcel'

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
  profit_margin_percent_monthly?: Record<string, number>
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

  const runReport = (overrideFrom?: string, overrideTo?: string) => {
    if (!canSeeReports(user)) return
    const from = overrideFrom ?? dateFrom
    const to = overrideTo ?? dateTo
    setLoading(true)
    setError(null)
    const fromD = new Date(from)
    const toD = new Date(to)
    const multiMonth = fromD.getFullYear() !== toD.getFullYear() ||
      fromD.getMonth() !== toD.getMonth()
    api
      .get<ApiResponse<ProfitLossData>>('/reports/profit-loss', {
        params: {
          date_from: from,
          date_to: to,
          ...(multiMonth ? { breakdown: 'monthly' } : {}),
        },
      })
      .then((res) => {
        if (res.data?.data) {
          setData(res.data.data)
          setDateFrom(from)
          setDateTo(to)
        }
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
              onRun={(from, to) => runReport(from, to)}
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
            <Button variant="contained" onClick={() => runReport()}>Run report</Button>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                const from = dateFrom
                const to = dateTo
                const fromD = new Date(from)
                const toD = new Date(to)
                const multiMonth = fromD.getFullYear() !== toD.getFullYear() || fromD.getMonth() !== toD.getMonth()
                downloadReportExcel('/reports/profit-loss', {
                  date_from: from,
                  date_to: to,
                  ...(multiMonth ? { breakdown: 'monthly' } : {}),
                }, 'profit-loss.xlsx')
              }}
            >
              Export to Excel
            </Button>
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

          <TableContainer component={Card}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Line</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{monthLabel(mo)}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>Total (KES)</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>Amount (KES)</TableCell>
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ fontWeight: 600, py: 0.5 }}>
                    REVENUE
                  </TableCell>
                </TableRow>
                {data.revenue_lines.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell sx={{ pl: 3 }}>{row.label}</TableCell>
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Gross Revenue</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.gross_revenue_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.gross_revenue)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.gross_revenue)}</TableCell>
                  )}
                </TableRow>
                <TableRow>
                  <TableCell sx={{ pl: 3 }}>Less: Discounts</TableCell>
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Net Revenue</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.net_revenue_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.net_revenue)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.net_revenue)}</TableCell>
                  )}
                </TableRow>

                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ fontWeight: 600, py: 0.5 }}>
                    EXPENSES
                  </TableCell>
                </TableRow>
                {data.expense_lines.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell sx={{ pl: 3 }}>{row.label}</TableCell>
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Total Expenses</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_expenses_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_expenses)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_expenses)}</TableCell>
                  )}
                </TableRow>

                <TableRow sx={{ bgcolor: 'action.selected', borderTop: 2, borderColor: 'divider' }}>
                  <TableCell sx={{ fontWeight: 700 }}>NET PROFIT</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_profit_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_profit)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_profit)}</TableCell>
                  )}
                </TableRow>
                {(data.profit_margin_percent != null || (data.months && data.months.length > 0 && data.profit_margin_percent_monthly)) && (
                  <TableRow>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>Profit margin (%)</TableCell>
                    {data.months && data.months.length > 0 && data.profit_margin_percent_monthly ? (
                      <>
                        {data.months.map((mo) => (
                          <TableCell key={mo} align="right" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                            {data.profit_margin_percent_monthly?.[mo] != null ? `${data.profit_margin_percent_monthly?.[mo]}%` : '—'}
                          </TableCell>
                        ))}
                        <TableCell align="right" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                          {data.profit_margin_percent != null ? `${data.profit_margin_percent}%` : '—'}
                        </TableCell>
                      </>
                    ) : (
                      <TableCell colSpan={2} sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                        {data.profit_margin_percent != null ? `Profit margin: ${data.profit_margin_percent}%` : '—'}
                      </TableCell>
                    )}
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select period and run report.</Typography>
      )}
    </Box>
  )
}
