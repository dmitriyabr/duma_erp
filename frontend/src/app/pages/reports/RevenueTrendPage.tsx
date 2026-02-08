import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { downloadReportExcel } from '../../utils/reportExcel'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Select,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

interface RevenueTrendRow {
  year: number
  label: string
  total_revenue: string
  students_count: number
  avg_revenue_per_student: string | null
}

interface RevenueTrendData {
  rows: RevenueTrendRow[]
  growth_percent: number | null
  years_included: number
}

export const RevenueTrendPage = () => {
  const { user } = useAuth()
  const [years, setYears] = useState(3)
  const [data, setData] = useState<RevenueTrendData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<RevenueTrendData>>('/reports/revenue-trend', {
        params: { years },
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
      <div>
        <Typography variant="h5" className="mb-4">Revenue per Student Trend</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Revenue per Student Trend</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <Select
              value={years}
              onChange={(e) => setYears(Number(e.target.value))}
              label="Years"
              className="min-w-[120px]"
            >
              {[1, 2, 3, 4, 5, 10].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </Select>
            <Button variant="contained" onClick={runReport}>Run report</Button>
            <Button variant="outlined" size="small" onClick={() => downloadReportExcel('/reports/revenue-trend', { years }, 'revenue-trend.xlsx')}>Export to Excel</Button>
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
          {data.growth_percent != null && (
            <Typography variant="body2" color="secondary" className="mb-4">
              Growth over period: {data.growth_percent > 0 ? '+' : ''}{data.growth_percent}%
            </Typography>
          )}

          <Card>
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell><strong>Year</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Total revenue (KES)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Students (paid)</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Avg per student (KES)</strong></TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.year}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_revenue)}</TableCell>
                    <TableCell align="right">{row.students_count}</TableCell>
                    <TableCell align="right">
                      {row.avg_revenue_per_student != null
                        ? formatMoney(row.avg_revenue_per_student)
                        : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select years and run report.</Typography>
      )}
    </div>
  )
}
