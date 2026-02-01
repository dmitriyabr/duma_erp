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

interface InflowLine {
  label: string
  amount: string
  monthly?: Record<string, string>
}

interface OutflowLine {
  label: string
  amount: string
  monthly?: Record<string, string>
}

interface CashFlowData {
  date_from: string
  date_to: string
  opening_balance: string
  inflow_lines: InflowLine[]
  total_inflows: string
  outflow_lines: OutflowLine[]
  total_outflows: string
  net_cash_flow: string
  closing_balance: string
  months?: string[]
  total_inflows_monthly?: Record<string, string>
  total_outflows_monthly?: Record<string, string>
  closing_balance_monthly?: Record<string, string>
}

const defaultRange = () => getDateRangeForPreset('this_year')
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function monthLabel(yyyyMm: string): string {
  const [y, m] = yyyyMm.split('-').map(Number)
  return `${MONTH_NAMES[m - 1]} ${y}`
}

export const CashFlowPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<CashFlowData | null>(null)
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
    const multiMonth = fromD.getFullYear() !== toD.getFullYear() || fromD.getMonth() !== toD.getMonth()
    api
      .get<ApiResponse<CashFlowData>>('/reports/cash-flow', {
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
        <Typography variant="h5" sx={{ mb: 2 }}>Cash Flow</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Cash Flow</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <DateRangeShortcuts
              dateFrom={dateFrom}
              dateTo={dateTo}
              onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }}
              onRun={(from, to) => runReport(from, to)}
            />
            <TextField label="From" type="date" size="small" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
            <TextField label="To" type="date" size="small" value={dateTo} onChange={(e) => setDateTo(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
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
                downloadReportExcel('/reports/cash-flow', {
                  date_from: from,
                  date_to: to,
                  ...(multiMonth ? { breakdown: 'monthly' } : {}),
                }, 'cash-flow.xlsx')
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
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Opening balance (as at {data.date_from})</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right">—</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.opening_balance)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.opening_balance)}</TableCell>
                  )}
                </TableRow>
                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ fontWeight: 600, py: 0.5 }}>
                    CASH INFLOWS
                  </TableCell>
                </TableRow>
                {data.inflow_lines.map((row) => (
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Total Inflows</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_inflows_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_inflows)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_inflows)}</TableCell>
                  )}
                </TableRow>
                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ fontWeight: 600, py: 0.5 }}>
                    CASH OUTFLOWS
                  </TableCell>
                </TableRow>
                {data.outflow_lines.map((row) => (
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Total Outflows</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_outflows_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_outflows)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_outflows)}</TableCell>
                  )}
                </TableRow>
                {data.months && data.months.length > 0 && data.closing_balance_monthly && (
                  <TableRow>
                    <TableCell sx={{ pl: 3 }}>Closing balance (end of month)</TableCell>
                    {data.months.map((mo) => (
                      <TableCell key={mo} align="right">{formatMoney(data.closing_balance_monthly?.[mo] ?? '0')}</TableCell>
                    ))}
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.closing_balance)}</TableCell>
                  </TableRow>
                )}
                <TableRow sx={{ bgcolor: 'action.selected', borderTop: 2, borderColor: 'divider' }}>
                  <TableCell sx={{ fontWeight: 700 }}>Net cash flow</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right">—</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_cash_flow)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_cash_flow)}</TableCell>
                  )}
                </TableRow>
                <TableRow sx={{ borderTop: 1, borderColor: 'divider' }}>
                  <TableCell sx={{ fontWeight: 700 }}>Closing balance (as at {data.date_to})</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right">—</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.closing_balance)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.closing_balance)}</TableCell>
                  )}
                </TableRow>
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
