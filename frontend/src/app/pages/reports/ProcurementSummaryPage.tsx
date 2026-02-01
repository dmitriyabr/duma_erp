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

const defaultDateFrom = () => {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}
const defaultDateTo = () => new Date().toISOString().slice(0, 10)

export const ProcurementSummaryPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [data, setData] = useState<ProcurementSummaryData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<ProcurementSummaryData>>('/reports/procurement-summary', {
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
        <Typography variant="h5" sx={{ mb: 2 }}>Procurement Summary</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Procurement Summary</Typography>

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
                  <TableCell><strong>Supplier</strong></TableCell>
                  <TableCell align="right"><strong>POs</strong></TableCell>
                  <TableCell align="right"><strong>Total (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Paid (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Outstanding (KES)</strong></TableCell>
                  <TableCell><strong>Status</strong></TableCell>
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
                  <TableCell />
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Outstanding breakdown (by age)</Typography>
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
        <Typography color="text.secondary">Select period and run report.</Typography>
      )}
    </Box>
  )
}
