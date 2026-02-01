import {
  Alert,
  Box,
  Card,
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

interface LowStockAlertRow {
  item_id: number
  item_name: string
  sku_code: string
  current: number
  min_level: number
  status: string
  suggested_order: number | null
}

interface LowStockAlertData {
  rows: LowStockAlertRow[]
  total_low_count: number
}

const statusLabel = (s: string) => {
  if (s === 'out') return 'Out of stock'
  if (s === 'low') return 'Low'
  return 'OK'
}

export const LowStockAlertPage = () => {
  const { user } = useAuth()
  const [data, setData] = useState<LowStockAlertData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const loadReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<LowStockAlertData>>('/reports/low-stock-alert')
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
    if (canSeeReports(user)) loadReport()
    else setForbidden(true)
  }, [user])

  if (forbidden) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Low Stock Alert</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Low Stock Alert</Typography>
      {data != null && data.total_low_count > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {data.total_low_count} item(s) at or below minimum level.
        </Alert>
      )}

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!loading && data && (
        <TableContainer component={Card}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell><strong>Item</strong></TableCell>
                <TableCell><strong>SKU</strong></TableCell>
                <TableCell align="right"><strong>Current</strong></TableCell>
                <TableCell align="right"><strong>Min level</strong></TableCell>
                <TableCell><strong>Status</strong></TableCell>
                <TableCell align="right"><strong>Suggested order</strong></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.rows.map((row) => (
                <TableRow key={row.item_id}>
                  <TableCell>{row.item_name}</TableCell>
                  <TableCell>{row.sku_code}</TableCell>
                  <TableCell align="right">{row.current}</TableCell>
                  <TableCell align="right">{row.min_level}</TableCell>
                  <TableCell>{statusLabel(row.status)}</TableCell>
                  <TableCell align="right">
                    {row.suggested_order != null ? row.suggested_order : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Loading…</Typography>
      )}
    </Box>
  )
}
