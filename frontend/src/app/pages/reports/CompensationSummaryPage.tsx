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

interface CompensationSummaryRow {
  employee_id: number
  employee_name: string
  claims_count: number
  total_amount: string
  approved_amount: string
  paid_amount: string
  pending_amount: string
}

interface CompensationSummaryTotals {
  total_claims: number
  total_amount: string
  total_approved: string
  total_paid: string
  total_pending: string
  pending_approval_count: number
  pending_approval_amount: string
  approved_unpaid_count: number
  approved_unpaid_amount: string
}

interface CompensationSummaryData {
  date_from: string
  date_to: string
  rows: CompensationSummaryRow[]
  summary: CompensationSummaryTotals
}

const defaultRange = () => getDateRangeForPreset('this_year')

export const CompensationSummaryPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<CompensationSummaryData | null>(null)
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
      .get<ApiResponse<CompensationSummaryData>>('/reports/compensation-summary', {
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
        <Typography variant="h5" className="mb-4">Compensation Summary</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Compensation Summary</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <DateRangeShortcuts dateFrom={dateFrom} dateTo={dateTo} onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }} onRun={(from, to) => runReport(from, to)} />
            <Input label="From" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" />
            <Input label="To" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" />
            <Button variant="contained" onClick={() => runReport()}>Run report</Button>
            <Button variant="outlined" size="small" onClick={() => downloadReportExcel('/reports/compensation-summary', { date_from: dateFrom, date_to: dateTo }, 'compensation-summary.xlsx')}>Export to Excel</Button>
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
                  <TableHeaderCell><strong>Employee</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Claims</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Total (KES)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Approved (KES)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Paid (KES)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Pending (KES)</strong></TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.employee_id}>
                    <TableCell>{row.employee_name}</TableCell>
                    <TableCell align="right">{row.claims_count}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(row.approved_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(row.paid_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(row.pending_amount)}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell><strong>TOTAL</strong></TableCell>
                  <TableCell align="right"><strong>{data.summary.total_claims}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.summary.total_amount)}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.summary.total_approved)}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.summary.total_paid)}</strong></TableCell>
                  <TableCell align="right"><strong>{formatMoney(data.summary.total_pending)}</strong></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Card>

          <Card className="mb-4">
            <CardContent>
              <Typography variant="subtitle2" className="mb-2">Summary</Typography>
              <Typography variant="body2">
                Pending Approval: {data.summary.pending_approval_count} claims, {formatMoney(data.summary.pending_approval_amount)} KES
              </Typography>
              <Typography variant="body2">
                Approved but Unpaid: {data.summary.approved_unpaid_count} claims, {formatMoney(data.summary.approved_unpaid_amount)} KES
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
