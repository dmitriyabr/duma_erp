import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'

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
          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Month</strong></TableCell>
                  <TableCell align="right"><strong>Invoiced (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Paid (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Rate %</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.year_month}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_invoiced)}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_paid)}</TableCell>
                    <TableCell align="right">
                      {row.rate_percent != null ? `${row.rate_percent}%` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

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
