import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent } from '../../components/ui/Card'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'
import { DateRangeShortcuts, getDateRangeForPreset } from '../../components/DateRangeShortcuts'
import { downloadReportExcel } from '../../utils/reportExcel'

interface DiscountRow {
  reason_id: number | null
  reason_code: string | null
  reason_name: string
  students_count: number
  total_amount: string
  avg_per_student: string | null
  percent_of_revenue: number | null
}

interface DiscountSummary {
  students_count: number
  total_discount_amount: string
  total_revenue: string
  percent_of_revenue: number | null
}

interface DiscountAnalysisData {
  date_from: string
  date_to: string
  rows: DiscountRow[]
  summary: DiscountSummary
}

const defaultRange = () => getDateRangeForPreset('this_year')

export const DiscountAnalysisPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [data, setData] = useState<DiscountAnalysisData | null>(null)
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
      .get<ApiResponse<DiscountAnalysisData>>('/reports/discount-analysis', {
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
        <Typography variant="h5" className="mb-4">Discount Analysis</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Discount Analysis</Typography>

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
              onRun={(from, to) => runReport(from, to)}
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
            <Button variant="contained" onClick={() => runReport()}>Run report</Button>
            <Button
              variant="outlined"
              size="small"
              onClick={() => downloadReportExcel('/reports/discount-analysis', { date_from: dateFrom, date_to: dateTo }, 'discount-analysis.xlsx')}
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

          <Card className="mb-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell><strong>Discount Type</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Students</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Total Amount</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Avg/Student</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>% of Revenue</strong></TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.rows.map((row, idx) => (
                    <TableRow key={row.reason_id ?? idx}>
                      <TableCell>{row.reason_name}</TableCell>
                      <TableCell align="right">{row.students_count}</TableCell>
                      <TableCell align="right">{formatMoney(row.total_amount)}</TableCell>
                      <TableCell align="right">
                        {row.avg_per_student != null ? formatMoney(row.avg_per_student) : '—'}
                      </TableCell>
                      <TableCell align="right">
                        {row.percent_of_revenue != null ? `${row.percent_of_revenue}%` : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" className="mb-2">
                Total: {data.summary.students_count} students, {formatMoney(data.summary.total_discount_amount)} discounts
              </Typography>
              <Typography variant="body2" color="secondary">
                Revenue in period: {formatMoney(data.summary.total_revenue)} · Discounts: {data.summary.percent_of_revenue != null ? `${data.summary.percent_of_revenue}%` : '—'} of revenue
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
