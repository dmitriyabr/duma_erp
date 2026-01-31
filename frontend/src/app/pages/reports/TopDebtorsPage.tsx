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
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatDate, formatMoney } from '../../utils/format'

interface TopDebtorRow {
  student_id: number
  student_name: string
  grade_name: string
  total_debt: string
  invoice_count: number
  oldest_due_date: string | null
}

interface TopDebtorsData {
  as_at_date: string
  limit: number
  rows: TopDebtorRow[]
  total_debt: string
}

const defaultAsAt = () => new Date().toISOString().slice(0, 10)

export const TopDebtorsPage = () => {
  const { user } = useAuth()
  const [asAtDate, setAsAtDate] = useState(defaultAsAt)
  const [limit, setLimit] = useState(20)
  const [data, setData] = useState<TopDebtorsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<TopDebtorsData>>('/reports/top-debtors', {
        params: { as_at_date: asAtDate, limit },
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
        <Typography variant="h5" sx={{ mb: 2 }}>Top Debtors</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Top Debtors</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Students with highest outstanding debt (as at date).
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <TextField
              label="As at date"
              type="date"
              size="small"
              value={asAtDate}
              onChange={(e) => setAsAtDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <Typography variant="body2">Top</Typography>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              style={{ padding: '8px 12px', marginRight: 8 }}
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <Typography variant="body2">students</Typography>
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
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            As at {data.as_at_date} · Total debt (top {data.rows.length}): {formatMoney(data.total_debt)}
          </Typography>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Student</strong></TableCell>
                  <TableCell><strong>Grade</strong></TableCell>
                  <TableCell align="right"><strong>Total Debt</strong></TableCell>
                  <TableCell align="right"><strong>Invoices</strong></TableCell>
                  <TableCell><strong>Oldest Due</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.student_id}>
                    <TableCell>{row.student_name}</TableCell>
                    <TableCell>{row.grade_name}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_debt)}</TableCell>
                    <TableCell align="right">{row.invoice_count}</TableCell>
                    <TableCell>
                      {row.oldest_due_date ? formatDate(row.oldest_due_date) : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select date and run report.</Typography>
      )}
    </Box>
  )
}
