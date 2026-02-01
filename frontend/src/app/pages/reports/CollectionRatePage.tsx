import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Typography,
} from '@mui/material'
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
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Collection Rate Trend</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Collection Rate Trend</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Collection rate % per month (invoiced vs paid in that month).
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <Typography variant="body2">Last</Typography>
            <select
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              style={{ padding: '8px 12px', marginRight: 8 }}
            >
              {[6, 12, 18, 24].map((n) => (
                <option key={n} value={n}>{n} months</option>
              ))}
            </select>
            <Button variant="contained" onClick={runReport}>Run report</Button>
            <Button variant="outlined" size="small" onClick={() => downloadReportExcel('/reports/collection-rate', { months }, 'collection-rate.xlsx')}>Export to Excel</Button>
          </Box>
        </CardContent>
      </Card>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!loading && data && (
        <>
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Collection rate % by month · Average: {data.average_rate_percent != null ? `${data.average_rate_percent}%` : '—'}
                {data.target_rate_percent != null && ` · Target: ${data.target_rate_percent}%`}
              </Typography>
              <Box sx={{ width: '100%', height: 320, mt: 1 }}>
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
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Average rate: {data.average_rate_percent != null ? `${data.average_rate_percent}%` : '—'}
              </Typography>
              {data.target_rate_percent != null && (
                <Typography variant="body2" color="text.secondary">
                  Target: {data.target_rate_percent}%
                </Typography>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Run report to see collection rate trend.</Typography>
      )}
    </Box>
  )
}
