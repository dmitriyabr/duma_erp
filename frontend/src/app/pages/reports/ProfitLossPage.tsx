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


export const ProfitLossPage = () => {
  const { user } = useAuth()
  const hasAccess = canSeeReports(user)
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<ProfitLossData | null>(null)
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
        <Typography variant="h5" className="mb-4">Profit & Loss</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Profit & Loss</Typography>

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
                downloadReportExcel('/reports/profit-loss', {
                  date_from: from,
                  date_to: to,
                  ...(multiMonth ? { breakdown: 'monthly' } : {}),
                }, 'profit-loss.xlsx')
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
                <Typography variant="body2" color="secondary">Gross revenue</Typography>
                <Typography variant="h6">{formatMoney(data.gross_revenue)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Discounts</Typography>
                <Typography variant="h6">{formatMoney(data.total_discounts)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Net revenue</Typography>
                <Typography variant="h6">{formatMoney(data.net_revenue)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Total expenses</Typography>
                <Typography variant="h6">{formatMoney(data.total_expenses)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Net profit</Typography>
                <Typography variant="h6">{formatMoney(data.net_profit)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Profit margin</Typography>
                <Typography variant="h6">
                  {data.profit_margin_percent != null ? `${data.profit_margin_percent}%` : '—'}
                </Typography>
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

            const percentCell = (value: number | undefined) => (
              <TableCell align="right">{value != null ? `${value}%` : '—'}</TableCell>
            )

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
                    <SectionRow label="Revenue" />
                    {data.revenue_lines.map((line) => (
                      <TableRow key={`rev-${line.label}`}>
                        <TableCell>{line.label}</TableCell>
                        {hasMonthly && months.map((m) => moneyCell(line.monthly?.[m]))}
                        <TableCell align="right">{formatMoney(line.amount)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Gross revenue</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.gross_revenue_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.gross_revenue)}</TableCell>
                    </TableRow>
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Discounts</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.total_discounts_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.total_discounts)}</TableCell>
                    </TableRow>
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Net revenue</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.net_revenue_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.net_revenue)}</TableCell>
                    </TableRow>

                    <SectionRow label="Expenses" />
                    {data.expense_lines.map((line) => (
                      <TableRow key={`exp-${line.label}`}>
                        <TableCell>{line.label}</TableCell>
                        {hasMonthly && months.map((m) => moneyCell(line.monthly?.[m]))}
                        <TableCell align="right">{formatMoney(line.amount)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Total expenses</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.total_expenses_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.total_expenses)}</TableCell>
                    </TableRow>

                    <TableRow hover={false} className="bg-slate-200">
                      <TableCell className="font-semibold uppercase tracking-wider text-slate-700">Net profit</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.net_profit_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.net_profit)}</TableCell>
                    </TableRow>
                    <TableRow hover={false}>
                      <TableCell className="text-slate-600">Profit margin (%)</TableCell>
                      {hasMonthly && months.map((m) => percentCell(data.profit_margin_percent_monthly?.[m]))}
                      <TableCell align="right">{data.profit_margin_percent != null ? `${data.profit_margin_percent}%` : '—'}</TableCell>
                    </TableRow>

                    {!data.revenue_lines.length && !data.expense_lines.length && (
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
