import { useEffect, useState } from 'react'
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
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<ProcurementSummaryData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = (overrideFrom?: string, overrideTo?: string) => {
    if (!canSeeReports(user)) return
    const from = overrideFrom ?? dateFrom
    const to = overrideTo ?? dateTo
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<ProcurementSummaryData>>('/reports/procurement-summary', {
        params: { date_from: from, date_to: to },
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
          <div className="flex flex-wrap gap-4 items-center">
            <DateRangeShortcuts dateFrom={dateFrom} dateTo={dateTo} onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }} onRun={(from, to) => runReport(from, to)} />
            <Input label="From" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" />
            <Input label="To" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" />
            <Button variant="contained" onClick={() => runReport()}>Run report</Button>
            <Button variant="outlined" size="small" onClick={() => downloadReportExcel('/reports/procurement-summary', { date_from: dateFrom, date_to: dateTo }, 'procurement-summary.xlsx')}>Export to Excel</Button>
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

          <Card className="mb-4">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell><strong>Supplier</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>POs</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Total (KES)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Paid (KES)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Outstanding (KES)</strong></TableHeaderCell>
                  <TableHeaderCell><strong>Status</strong></TableHeaderCell>
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
                <TableRow>
                  <TableCell><strong>TOTAL</strong></TableCell>
                  <TableCell align="right"><strong>{data.total_po_count}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.total_amount)}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.total_paid)}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.total_outstanding)}</strong></TableCell>
                  <TableCell>—</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Card>

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
