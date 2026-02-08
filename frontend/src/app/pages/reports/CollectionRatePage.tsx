import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Card, CardContent } from '../../components/ui/Card'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { downloadReportExcel } from '../../utils/reportExcel'

interface MonthRow {
  year_month: string
  label: string
  total_invoiced: string
  total_paid: string
  rate_percent: number | null
}

interface CollectionRateData {
  rows: MonthRow[]
  average_rate_percent: number | null
  target_rate_percent: number | null
}

export const CollectionRatePage = () => {
  const { user } = useAuth()
  const [data, setData] = useState<CollectionRateData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [months, setMonths] = useState(12)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<CollectionRateData>>('/reports/collection-rate', {
        params: { months },
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
        <Typography variant="h5" className="mb-4">Collection Rate Trend</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Collection Rate Trend</Typography>
      <Typography variant="body2" color="secondary" className="mb-4">
        Collection rate % per month (invoiced vs paid in that month).
      </Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <Typography variant="body2">Last</Typography>
            <div className="min-w-[140px]">
              <Select
                value={String(months)}
                onChange={(e) => setMonths(Number(e.target.value))}
              >
                {[6, 12, 18, 24].map((n) => (
                  <option key={n} value={n}>{n} months</option>
                ))}
              </Select>
            </div>
            <Button variant="contained" onClick={runReport}>Run report</Button>
            <Button variant="outlined" size="small" onClick={() => downloadReportExcel('/reports/collection-rate', { months }, 'collection-rate.xlsx')}>
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
          <Card className="mb-4">
            <CardContent>
              <Typography variant="subtitle2" color="secondary" className="mb-2">
                Collection rate % by month · Average: {data.average_rate_percent != null ? `${data.average_rate_percent}%` : '—'}
                {data.target_rate_percent != null && ` · Target: ${data.target_rate_percent}%`}
              </Typography>
              <div className="w-full h-80 mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={data.rows.map((r) => ({
                      ...r,
                      rate: r.rate_percent ?? 0,
                    }))}
                    margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 12 }}
                      tickFormatter={(v) => `${v}%`}
                    />
                    <Tooltip
                      formatter={(value: number | undefined) => (value != null ? `${value}%` : '—')}
                      labelFormatter={(label) => `Month: ${label}`}
                    />
                    <Legend />
                    {data.target_rate_percent != null && (
                      <ReferenceLine
                        y={data.target_rate_percent}
                        stroke="#d32f2f"
                        strokeDasharray="4 4"
                        label={{ value: 'Target', position: 'right', fontSize: 11 }}
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="rate"
                      name="Collection rate %"
                      stroke="#1976d2"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" className="mb-2">
                Average rate: {data.average_rate_percent != null ? `${data.average_rate_percent}%` : '—'}
              </Typography>
              {data.target_rate_percent != null && (
                <Typography variant="body2" color="secondary">
                  Target: {data.target_rate_percent}%
                </Typography>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Run report to see collection rate trend.</Typography>
      )}
    </div>
  )
}
