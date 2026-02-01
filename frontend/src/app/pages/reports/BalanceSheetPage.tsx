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

interface AssetLine {
  label: string
  amount: string
  monthly?: Record<string, string>
}

interface LiabilityLine {
  label: string
  amount: string
  monthly?: Record<string, string>
}

interface BalanceSheetData {
  as_at_date: string
  asset_lines: AssetLine[]
  total_assets: string
  liability_lines: LiabilityLine[]
  total_liabilities: string
  net_equity: string
  debt_to_asset_percent: number | null
  current_ratio: number | null
  months?: string[]
  total_assets_monthly?: Record<string, string>
  total_liabilities_monthly?: Record<string, string>
  net_equity_monthly?: Record<string, string>
  debt_to_asset_percent_monthly?: Record<string, number>
  current_ratio_monthly?: Record<string, number>
}

const defaultRange = () => getDateRangeForPreset('this_year')
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function monthLabel(yyyyMm: string): string {
  const [y, m] = yyyyMm.split('-').map(Number)
  return `${MONTH_NAMES[m - 1]} ${y}`
}

export const BalanceSheetPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<BalanceSheetData | null>(null)
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
    const params: Record<string, string> = {
      as_at_date: to,
      date_from: from,
      date_to: to,
    }
    if (multiMonth) params.breakdown = 'monthly'
    api
      .get<ApiResponse<BalanceSheetData>>('/reports/balance-sheet', {
        params,
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
        <Typography variant="h5" sx={{ mb: 2 }}>Balance Sheet</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Balance Sheet</Typography>

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
            <TextField label="To (as at)" type="date" size="small" value={dateTo} onChange={(e) => setDateTo(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
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
                downloadReportExcel('/reports/balance-sheet', {
                  as_at_date: to,
                  date_from: from,
                  date_to: to,
                  ...(multiMonth ? { breakdown: 'monthly' } : {}),
                }, 'balance-sheet.xlsx')
              }}
            >
              Export to Excel
            </Button>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Multi-month range shows columns per month (as at end of each month).
          </Typography>
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
            As at {data.as_at_date}
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
                    ASSETS
                  </TableCell>
                </TableRow>
                {data.asset_lines.map((row) => (
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Total Assets</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_assets_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_assets)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_assets)}</TableCell>
                  )}
                </TableRow>
                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ fontWeight: 600, py: 0.5 }}>
                    LIABILITIES
                  </TableCell>
                </TableRow>
                {data.liability_lines.map((row) => (
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
                  <TableCell sx={{ pl: 3, fontWeight: 600 }}>Total Liabilities</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_liabilities_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_liabilities)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatMoney(data.total_liabilities)}</TableCell>
                  )}
                </TableRow>
                <TableRow sx={{ bgcolor: 'action.selected', borderTop: 2, borderColor: 'divider' }}>
                  <TableCell sx={{ fontWeight: 700 }}>NET EQUITY</TableCell>
                  {data.months && data.months.length > 0 ? (
                    <>
                      {data.months.map((mo) => (
                        <TableCell key={mo} align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_equity_monthly?.[mo] ?? '0')}</TableCell>
                      ))}
                      <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_equity)}</TableCell>
                    </>
                  ) : (
                    <TableCell align="right" sx={{ fontWeight: 700 }}>{formatMoney(data.net_equity)}</TableCell>
                  )}
                </TableRow>
                {(data.debt_to_asset_percent != null || data.current_ratio != null || (data.months && data.months.length > 0 && (data.debt_to_asset_percent_monthly || data.current_ratio_monthly))) && (
                  <>
                    {data.months && data.months.length > 0 && data.debt_to_asset_percent_monthly ? (
                      <TableRow>
                        <TableCell sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>Debt-to-asset (%)</TableCell>
                        {data.months.map((mo) => (
                          <TableCell key={mo} align="right" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                            {data.debt_to_asset_percent_monthly?.[mo] != null ? `${data.debt_to_asset_percent_monthly[mo]}%` : '—'}
                          </TableCell>
                        ))}
                        <TableCell align="right" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                          {data.debt_to_asset_percent != null ? `${data.debt_to_asset_percent}%` : '—'}
                        </TableCell>
                      </TableRow>
                    ) : (
                      data.debt_to_asset_percent != null && (
                        <TableRow>
                          <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                            Debt-to-asset ratio: {data.debt_to_asset_percent}%
                          </TableCell>
                        </TableRow>
                      )
                    )}
                    {data.months && data.months.length > 0 && data.current_ratio_monthly ? (
                      <TableRow>
                        <TableCell sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>Current ratio</TableCell>
                        {data.months.map((mo) => (
                          <TableCell key={mo} align="right" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                            {data.current_ratio_monthly?.[mo] != null ? data.current_ratio_monthly[mo] : '—'}
                          </TableCell>
                        ))}
                        <TableCell align="right" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                          {data.current_ratio != null ? data.current_ratio : '—'}
                        </TableCell>
                      </TableRow>
                    ) : (
                      data.current_ratio != null && (
                        <TableRow>
                          <TableCell colSpan={data.months && data.months.length > 0 ? (data.months.length + 2) : 2} sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                            Current ratio: {data.current_ratio}
                          </TableCell>
                        </TableRow>
                      )
                    )}
                  </>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select date and run report.</Typography>
      )}
    </Box>
  )
}
