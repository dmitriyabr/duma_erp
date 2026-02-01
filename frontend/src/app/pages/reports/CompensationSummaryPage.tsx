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
import { formatMoney } from '../../utils/format'

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

const defaultDateFrom = () => {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}
const defaultDateTo = () => new Date().toISOString().slice(0, 10)

export const CompensationSummaryPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [data, setData] = useState<CompensationSummaryData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<CompensationSummaryData>>('/reports/compensation-summary', {
        params: { date_from: dateFrom, date_to: dateTo },
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
        <Typography variant="h5" sx={{ mb: 2 }}>Compensation Summary</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Compensation Summary</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <TextField
              label="From"
              type="date"
              size="small"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 160 }}
            />
            <TextField
              label="To"
              type="date"
              size="small"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 160 }}
            />
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
            Period: {data.date_from} — {data.date_to}
          </Typography>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Employee</strong></TableCell>
                  <TableCell align="right"><strong>Claims</strong></TableCell>
                  <TableCell align="right"><strong>Total (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Approved (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Paid (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Pending (KES)</strong></TableCell>
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
          </TableContainer>

          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Summary</Typography>
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
        <Typography color="text.secondary">Select period and run report.</Typography>
      )}
    </Box>
  )
}
