import {
  Alert,
  Box,
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
import { useSearchParams } from 'react-router-dom'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { formatDate, formatMoney } from '../../utils/format'

interface AgedRow {
  student_id: number
  student_name: string
  total: string
  current: string  // 0-30 days (not yet due + up to 30 days overdue)
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
  last_payment_date: string | null
}

interface Summary {
  total: string
  current: string
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
}

interface AgedReceivablesData {
  as_at_date: string
  rows: AgedRow[]
  summary: Summary
}

export const AgedReceivablesPage = () => {
  const [searchParams] = useSearchParams()
  const asAtParam = searchParams.get('as_at_date') ?? undefined
  const [data, setData] = useState<AgedReceivablesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setForbidden(false)
    const params = asAtParam ? { as_at_date: asAtParam } : {}
    api
      .get<ApiResponse<AgedReceivablesData>>('/reports/aged-receivables', { params })
      .then((res) => {
        if (!cancelled && res.data?.data) setData(res.data.data)
      })
      .catch((err) => {
        if (!cancelled) {
          if (err.response?.status === 403) setForbidden(true)
          else setError(err.response?.data?.message ?? 'Failed to load report')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [asAtParam])

  if (forbidden) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Aged Receivables</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Aged Receivables</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Student debts by aging (as at {data ? formatDate(data.as_at_date) : '—'}).
      </Typography>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
      )}

      {!loading && data && (
        <>
          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Student</strong></TableCell>
                  <TableCell align="right"><strong>Total</strong></TableCell>
                  <TableCell align="right"><strong>Current (0-30 days)</strong></TableCell>
                  <TableCell align="right"><strong>31-60 days</strong></TableCell>
                  <TableCell align="right"><strong>61-90 days</strong></TableCell>
                  <TableCell align="right"><strong>90+ days</strong></TableCell>
                  <TableCell><strong>Last Payment</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.student_id}>
                    <TableCell>{row.student_name}</TableCell>
                    <TableCell align="right">{formatMoney(row.total)}</TableCell>
                    <TableCell align="right">{formatMoney(row.current)}</TableCell>
                    <TableCell align="right">{formatMoney(row.bucket_31_60)}</TableCell>
                    <TableCell align="right">{formatMoney(row.bucket_61_90)}</TableCell>
                    <TableCell align="right">{formatMoney(row.bucket_90_plus)}</TableCell>
                    <TableCell>{row.last_payment_date ? formatDate(row.last_payment_date) : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Summary</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Typography variant="body2"><strong>Total:</strong> {formatMoney(data.summary.total)}</Typography>
                <Typography variant="body2"><strong>Current (0-30 days):</strong> {formatMoney(data.summary.current)}</Typography>
                <Typography variant="body2"><strong>31-60 days:</strong> {formatMoney(data.summary.bucket_31_60)}</Typography>
                <Typography variant="body2"><strong>61-90 days:</strong> {formatMoney(data.summary.bucket_61_90)}</Typography>
                <Typography variant="body2" color="error.main"><strong>90+ days:</strong> {formatMoney(data.summary.bucket_90_plus)}</Typography>
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && (
        <Typography color="text.secondary">No data.</Typography>
      )}
    </Box>
  )
}
