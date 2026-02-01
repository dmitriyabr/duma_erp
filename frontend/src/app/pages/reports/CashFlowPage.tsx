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

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    const fromD = new Date(dateFrom)
    const toD = new Date(dateTo)
    const multiMonth = fromD.getFullYear() !== toD.getFullYear() || fromD.getMonth() !== toD.getMonth()
    api
      .get<ApiResponse<CashFlowData>>('/reports/cash-flow', {
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
              onRun={runReport}
            />
            <TextField label="From" type="date" size="small" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
            <TextField label="To" type="date" size="small" value={dateTo} onChange={(e) => setDateTo(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
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

          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Opening balance (as at {data.date_from})</Typography>
              <Typography variant="h6">{formatMoney(data.opening_balance)}</Typography>
            </CardContent>
          </Card>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Cash Inflows</strong></TableCell>
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
                {data.inflow_lines.map((row) => (
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
                  <TableCell><strong>Total Inflows</strong></TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{formatMoney(data.total_inflows_monthly?.[mo] ?? '0')}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>{formatMoney(data.total_inflows)}</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>{formatMoney(data.total_inflows)}</strong></TableCell>
                  )}
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Cash Outflows</strong></TableCell>
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
                {data.outflow_lines.map((row) => (
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
                  <TableCell><strong>Total Outflows</strong></TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right"><strong>{formatMoney(data.total_outflows_monthly?.[mo] ?? '0')}</strong></TableCell>
                      ))}
                      <TableCell align="right"><strong>{formatMoney(data.total_outflows)}</strong></TableCell>
                    </>
                  ) : (
                    <TableCell align="right"><strong>{formatMoney(data.total_outflows)}</strong></TableCell>
                  )}
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          {data.months && data.months.length > 0 && data.closing_balance_monthly && (
            <TableContainer component={Card} sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell><strong>Closing balance (end of month)</strong></TableCell>
                    {data.months.map((mo) => (
                      <TableCell key={mo} align="right"><strong>{monthLabel(mo)}</strong></TableCell>
                    ))}
                    <TableCell align="right"><strong>Final</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>Balance</TableCell>
                    {data.months.map((mo) => (
                      <TableCell key={mo} align="right">{formatMoney(data.closing_balance_monthly?.[mo] ?? '0')}</TableCell>
                    ))}
                    <TableCell align="right"><strong>{formatMoney(data.closing_balance)}</strong></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          )}
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom><strong>Net cash flow</strong>: {formatMoney(data.net_cash_flow)}</Typography>
              <Typography variant="subtitle2" gutterBottom><strong>Closing balance</strong> (as at {data.date_to}): {formatMoney(data.closing_balance)}</Typography>
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
