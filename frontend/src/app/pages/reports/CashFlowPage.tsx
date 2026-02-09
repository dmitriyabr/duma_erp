import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { DateRangeShortcuts, getDateRangeForPreset } from '../../components/DateRangeShortcuts'
import { downloadReportExcel } from '../../utils/reportExcel'
import { formatMoney } from '../../utils/format'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components/ui/Table'

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

export const CashFlowPage = () => {
  const { user } = useAuth()
  const hasAccess = canSeeReports(user)
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<CashFlowData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendForbidden, setBackendForbidden] = useState(false)

  const runReportForRange = useCallback((from: string, to: string) => {
    if (!hasAccess) return
    setDateFrom(from)
    setDateTo(to)
    setLoading(true)
    setError(null)
    setBackendForbidden(false)
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
        }
      })
      .catch((err) => {
        if (err.response?.status === 403) setBackendForbidden(true)
        else setError(err.response?.data?.detail ?? 'Failed to load report')
      })
      .finally(() => setLoading(false))
  }, [hasAccess])

  useEffect(() => {
    if (!hasAccess) return
    const { from, to } = defaultRange()
    const t = window.setTimeout(() => runReportForRange(from, to), 0)
    return () => window.clearTimeout(t)
  }, [hasAccess, user, runReportForRange])

  if (!hasAccess || backendForbidden) {
    return (
      <div>
        <Typography variant="h5" className="mb-4">Cash Flow</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Cash Flow</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <DateRangeShortcuts
              dateFrom={dateFrom}
              dateTo={dateTo}
              onRangeChange={(from, to) => {
                setDateFrom(from)
                setDateTo(to)
              }}
              onRun={(from, to) => runReportForRange(from ?? dateFrom, to ?? dateTo)}
            />
            <div className="min-w-[160px]">
              <Input
                label="From"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="min-w-[160px]">
              <Input
                label="To"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
            <Button variant="contained" onClick={() => runReportForRange(dateFrom, dateTo)}>Run report</Button>
            <Button
              variant="outlined"
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
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Spinner size="large" />
        </div>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {!loading && data && (
        <>
          <Typography variant="body2" color="secondary" className="mb-4">
            Period: {data.date_from} — {data.date_to}
          </Typography>

          <div className="flex flex-wrap gap-4 mb-6">
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Opening balance</Typography>
                <Typography variant="h6">{formatMoney(data.opening_balance)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Total inflows</Typography>
                <Typography variant="h6">{formatMoney(data.total_inflows)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Total outflows</Typography>
                <Typography variant="h6">{formatMoney(data.total_outflows)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Net cash flow</Typography>
                <Typography variant="h6">{formatMoney(data.net_cash_flow)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Closing balance</Typography>
                <Typography variant="h6">{formatMoney(data.closing_balance)}</Typography>
              </CardContent>
            </Card>
          </div>

          {(() => {
            const months = data.months ?? []
            const hasMonthly = months.length > 0
            const cols = hasMonthly ? months.length + 2 : 2

            const moneyCell = (value: string | undefined) => (
              <TableCell align="right">{formatMoney(value ?? null)}</TableCell>
            )

            const num = (value: string | undefined): number | null => {
              if (!value) return null
              const cleaned = value.replace(/,/g, '').trim()
              const n = Number.parseFloat(cleaned)
              return Number.isNaN(n) ? null : n
            }

            const netMonthly: Record<string, string> = {}
            if (hasMonthly) {
              for (const m of months) {
                const inflow = num(data.total_inflows_monthly?.[m]) ?? 0
                const outflow = num(data.total_outflows_monthly?.[m]) ?? 0
                netMonthly[m] = (inflow - outflow).toFixed(2)
              }
            }

            const SectionRow = ({ label }: { label: string }) => (
              <TableRow hover={false} className="bg-slate-100">
                <td colSpan={cols} className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-700">
                  {label}
                </td>
              </TableRow>
            )

            return (
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-6">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Line</TableHeaderCell>
                      {hasMonthly && months.map((m) => (
                        <TableHeaderCell key={m} align="right">{m}</TableHeaderCell>
                      ))}
                      <TableHeaderCell align="right">Total (KES)</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Opening balance</TableCell>
                      {hasMonthly && months.map((m) => (
                        <TableCell key={`opening-${m}`} align="right">—</TableCell>
                      ))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.opening_balance)}</TableCell>
                    </TableRow>

                    <SectionRow label="Inflows" />
                    {data.inflow_lines.map((line) => (
                      <TableRow key={`in-${line.label}`}>
                        <TableCell>{line.label}</TableCell>
                        {hasMonthly && months.map((m) => moneyCell(line.monthly?.[m]))}
                        <TableCell align="right">{formatMoney(line.amount)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Total inflows</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.total_inflows_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.total_inflows)}</TableCell>
                    </TableRow>

                    <SectionRow label="Outflows" />
                    {data.outflow_lines.map((line) => (
                      <TableRow key={`out-${line.label}`}>
                        <TableCell>{line.label}</TableCell>
                        {hasMonthly && months.map((m) => moneyCell(line.monthly?.[m]))}
                        <TableCell align="right">{formatMoney(line.amount)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Total outflows</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.total_outflows_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.total_outflows)}</TableCell>
                    </TableRow>

                    <TableRow hover={false} className="bg-slate-200">
                      <TableCell className="font-semibold uppercase tracking-wider text-slate-700">Net cash flow</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(netMonthly[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.net_cash_flow)}</TableCell>
                    </TableRow>

                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Closing balance</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.closing_balance_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.closing_balance)}</TableCell>
                    </TableRow>

                    {!data.inflow_lines.length && !data.outflow_lines.length && (
                      <TableRow>
                        <td colSpan={cols} className="px-4 py-6 text-center">
                          <Typography color="secondary">No lines</Typography>
                        </td>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            )
          })()}

        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select period and run report.</Typography>
      )}
    </div>
  )
}
