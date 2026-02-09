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

export const BalanceSheetPage = () => {
  const { user } = useAuth()
  const hasAccess = canSeeReports(user)
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<BalanceSheetData | null>(null)
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
        <Typography variant="h5" className="mb-4">Balance Sheet</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Balance Sheet</Typography>

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
                label="To (as at)"
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
          </div>
          <Typography variant="caption" color="secondary" className="block mt-2">
            Multi-month range shows columns per month (as at end of each month).
          </Typography>
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
            As at {data.as_at_date}
          </Typography>

          <div className="flex flex-wrap gap-4 mb-6">
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Total assets</Typography>
                <Typography variant="h6">{formatMoney(data.total_assets)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Total liabilities</Typography>
                <Typography variant="h6">{formatMoney(data.total_liabilities)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Net equity</Typography>
                <Typography variant="h6">{formatMoney(data.net_equity)}</Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Debt to asset</Typography>
                <Typography variant="h6">
                  {data.debt_to_asset_percent != null ? `${data.debt_to_asset_percent}%` : '—'}
                </Typography>
              </CardContent>
            </Card>
            <Card className="min-w-[220px]">
              <CardContent>
                <Typography variant="body2" color="secondary">Current ratio</Typography>
                <Typography variant="h6">
                  {data.current_ratio != null ? String(data.current_ratio) : '—'}
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

            const ratioCell = (value: number | undefined) => (
              <TableCell align="right">{value != null ? String(value) : '—'}</TableCell>
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
                    <SectionRow label="Assets" />
                    {data.asset_lines.map((line) => (
                      <TableRow key={`asset-${line.label}`}>
                        <TableCell>{line.label}</TableCell>
                        {hasMonthly && months.map((m) => moneyCell(line.monthly?.[m]))}
                        <TableCell align="right">{formatMoney(line.amount)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Total assets</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.total_assets_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.total_assets)}</TableCell>
                    </TableRow>

                    <SectionRow label="Liabilities" />
                    {data.liability_lines.map((line) => (
                      <TableRow key={`liab-${line.label}`}>
                        <TableCell>{line.label}</TableCell>
                        {hasMonthly && months.map((m) => moneyCell(line.monthly?.[m]))}
                        <TableCell align="right">{formatMoney(line.amount)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow hover={false} className="bg-slate-50">
                      <TableCell className="font-semibold">Total liabilities</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.total_liabilities_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.total_liabilities)}</TableCell>
                    </TableRow>

                    <TableRow hover={false} className="bg-slate-200">
                      <TableCell className="font-semibold uppercase tracking-wider text-slate-700">Net equity</TableCell>
                      {hasMonthly && months.map((m) => moneyCell(data.net_equity_monthly?.[m]))}
                      <TableCell align="right" className="font-semibold">{formatMoney(data.net_equity)}</TableCell>
                    </TableRow>

                    <TableRow hover={false}>
                      <TableCell className="text-slate-600">Debt-to-asset (%)</TableCell>
                      {hasMonthly && months.map((m) => percentCell(data.debt_to_asset_percent_monthly?.[m]))}
                      <TableCell align="right">{data.debt_to_asset_percent != null ? `${data.debt_to_asset_percent}%` : '—'}</TableCell>
                    </TableRow>
                    <TableRow hover={false}>
                      <TableCell className="text-slate-600">Current ratio</TableCell>
                      {hasMonthly && months.map((m) => ratioCell(data.current_ratio_monthly?.[m]))}
                      <TableCell align="right">{data.current_ratio != null ? String(data.current_ratio) : '—'}</TableCell>
                    </TableRow>

                    {!data.asset_lines.length && !data.liability_lines.length && (
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
        <Typography color="secondary">Select date and run report.</Typography>
      )}
    </div>
  )
}
