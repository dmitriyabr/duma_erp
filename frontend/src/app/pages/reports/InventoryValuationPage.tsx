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

interface InventoryValuationRow {
  category_id: number
  category_name: string
  items_count: number
  quantity: number
  unit_cost_avg: string | null
  total_value: string
  turnover: number | null
}

interface InventoryValuationData {
  as_at_date: string
  rows: InventoryValuationRow[]
  total_items: number
  total_quantity: number
  total_value: string
}

const defaultAsAt = () => new Date().toISOString().slice(0, 10)

export const InventoryValuationPage = () => {
  const { user } = useAuth()
  const [asAtDate, setAsAtDate] = useState(defaultAsAt)
  const [data, setData] = useState<InventoryValuationData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<InventoryValuationData>>('/reports/inventory-valuation', {
        params: { as_at_date: asAtDate },
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
        <Typography variant="h5" sx={{ mb: 2 }}>Inventory Valuation</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Inventory Valuation</Typography>

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
            As at: {data.as_at_date}
          </Typography>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Category</strong></TableCell>
                  <TableCell align="right"><strong>Items</strong></TableCell>
                  <TableCell align="right"><strong>Quantity</strong></TableCell>
                  <TableCell align="right"><strong>Unit cost avg (KES)</strong></TableCell>
                  <TableCell align="right"><strong>Total value (KES)</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.category_id}>
                    <TableCell>{row.category_name}</TableCell>
                    <TableCell align="right">{row.items_count}</TableCell>
                    <TableCell align="right">{row.quantity}</TableCell>
                    <TableCell align="right">
                      {row.unit_cost_avg != null ? formatMoney(row.unit_cost_avg) : '—'}
                    </TableCell>
                    <TableCell align="right">{formatMoney(row.total_value)}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell><strong>TOTAL</strong></TableCell>
                  <TableCell align="right"><strong>{data.total_items}</strong></TableCell>
                  <TableCell align="right"><strong>{data.total_quantity}</strong></TableCell>
                  <TableCell />
                  <TableCell align="right"><strong>{formatMoney(data.total_value)}</strong></TableCell>
                </TableRow>
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
