import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { DateRangeShortcuts, getDateRangeForPreset } from '../../components/DateRangeShortcuts'
import { downloadReportExcel } from '../../utils/reportExcel'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Input,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

interface ProcurementSummaryRow {
  supplier_name: string
  po_count: number
  total_amount: string
  paid: string
  outstanding: string
  status: string
}

interface OutstandingBreakdown {
  current_0_30: string
  bucket_31_60: string
  bucket_61_plus: string
}

interface ProcurementSummaryData {
  date_from: string
  date_to: string
  rows: ProcurementSummaryRow[]
  total_po_count: number
  total_amount: string
  total_paid: string
  total_outstanding: string
  outstanding_breakdown: OutstandingBreakdown
}

const defaultRange = () => getDateRangeForPreset('this_year')

export const ProcurementSummaryPage = () => {
  const { user } = useAuth()
  const hasAccess = canSeeReports(user)
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<ProcurementSummaryData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendForbidden, setBackendForbidden] = useState(false)

  const runReportForRange = useCallback((from: string, to: string) => {
    if (!hasAccess) return
    if (from !== dateFrom) setDateFrom(from)
    if (to !== dateTo) setDateTo(to)
    setLoading(true)
    setError(null)
    setBackendForbidden(false)
    api
      .get<ApiResponse<ProcurementSummaryData>>('/reports/procurement-summary', {
        params: { date_from: from, date_to: to },
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
  }, [hasAccess, dateFrom, dateTo])

  useEffect(() => {
    if (!hasAccess) return
    const { from, to } = defaultRange()
    const t = window.setTimeout(() => runReportForRange(from, to), 0)
    return () => window.clearTimeout(t)
  }, [hasAccess, user, runReportForRange])

  if (!hasAccess || backendForbidden) {
    return (
      <div>
        <Typography variant="h5" className="mb-4">Procurement Summary</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Procurement Summary</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
              <DateRangeShortcuts
                dateFrom={dateFrom}
                dateTo={dateTo}
                onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }}
                onRun={(from, to) => runReportForRange(from ?? dateFrom, to ?? dateTo)}
              />
            <Input
              label="From"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              containerClassName="w-[180px] min-w-[160px]"
            />
            <Input
              label="To"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              containerClassName="w-[180px] min-w-[160px]"
            />
            <Button variant="contained" onClick={() => runReportForRange(dateFrom, dateTo)}>
              Run report
            </Button>
            <Button
              variant="outlined"
              onClick={() => downloadReportExcel('/reports/procurement-summary', { date_from: dateFrom, date_to: dateTo }, 'procurement-summary.xlsx')}
            >
              Export to Excel
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Spinner size="medium" />
        </div>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {!loading && data && (
        <>
          <Typography variant="body2" color="secondary" className="mb-4">
            Period: {data.date_from} — {data.date_to}
          </Typography>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Supplier</TableHeaderCell>
                  <TableHeaderCell align="right">POs</TableHeaderCell>
                  <TableHeaderCell align="right">Total (KES)</TableHeaderCell>
                  <TableHeaderCell align="right">Paid (KES)</TableHeaderCell>
                  <TableHeaderCell align="right">Outstanding (KES)</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.supplier_name}>
                    <TableCell>{row.supplier_name}</TableCell>
                    <TableCell align="right">{row.po_count}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(row.paid)}</TableCell>
                    <TableCell align="right">{formatMoney(row.outstanding)}</TableCell>
                    <TableCell>{row.status === 'ok' ? 'OK' : 'Partial'}</TableCell>
                  </TableRow>
                ))}
                <TableRow hover={false} className="bg-slate-50">
                  <TableCell className="font-semibold">TOTAL</TableCell>
                  <TableCell align="right" className="font-semibold">{data.total_po_count}</TableCell>
                  <TableCell align="right" className="font-semibold">{formatMoney(data.total_amount)}</TableCell>
                  <TableCell align="right" className="font-semibold">{formatMoney(data.total_paid)}</TableCell>
                  <TableCell align="right" className="font-semibold">{formatMoney(data.total_outstanding)}</TableCell>
                  <TableCell>—</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <Card className="mb-4">
            <CardContent>
              <Typography variant="subtitle2" className="mb-2">Outstanding breakdown (by age)</Typography>
              <Typography variant="body2">
                Current (0–30 days): {formatMoney(data.outstanding_breakdown.current_0_30)} KES
                {' · '}
                31–60 days: {formatMoney(data.outstanding_breakdown.bucket_31_60)} KES
                {' · '}
                61+ days: {formatMoney(data.outstanding_breakdown.bucket_61_plus)} KES
              </Typography>
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select period and run report.</Typography>
      )}
    </div>
  )
}
