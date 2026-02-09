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

interface PaymentMethodDistributionRow {
  payment_method: string
  label: string
  amount: string
  percent_of_total: number | null
}

interface PaymentMethodDistributionData {
  date_from: string
  date_to: string
  rows: PaymentMethodDistributionRow[]
  total_amount: string
}

const defaultRange = () => getDateRangeForPreset('this_year')

export const PaymentMethodDistributionPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<PaymentMethodDistributionData | null>(null)
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
      .get<ApiResponse<PaymentMethodDistributionData>>('/reports/payment-method-distribution', {
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
        <Typography variant="h5" className="mb-4">Payment Method Distribution</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Payment Method Distribution</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <DateRangeShortcuts dateFrom={dateFrom} dateTo={dateTo} onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }} onRun={(from, to) => runReport(from, to)} />
            <Input label="From" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" />
            <Input label="To" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" />
            <Button variant="contained" onClick={() => runReport()}>Run report</Button>
            <Button variant="outlined" onClick={() => downloadReportExcel('/reports/payment-method-distribution', { date_from: dateFrom, date_to: dateTo }, 'payment-method-distribution.xlsx')}>Export to Excel</Button>
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
            Period: {data.date_from} — {data.date_to}. Total: {formatMoney(data.total_amount)} KES
          </Typography>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Method</TableHeaderCell>
                  <TableHeaderCell align="right">Amount (KES)</TableHeaderCell>
                  <TableHeaderCell align="right">% of total</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.payment_method}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    <TableCell align="right">
                      {row.percent_of_total != null ? `${row.percent_of_total}%` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select period and run report.</Typography>
      )}
    </div>
  )
}
