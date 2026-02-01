import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
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
import { DateRangeShortcuts, getDateRangeForPreset } from '../../components/DateRangeShortcuts'
import { downloadReportExcel } from '../../utils/reportExcel'

interface StockMovementRow {
  movement_id: number
  movement_date: string
  movement_type: string
  item_id: number
  item_name: string
  quantity: number
  ref_display: string | null
  created_by_name: string
  balance_after: number
}

interface StockMovementData {
  date_from: string
  date_to: string
  rows: StockMovementRow[]
}

const defaultRange = () => getDateRangeForPreset('this_year')

const movementTypeLabel = (t: string) => {
  const labels: Record<string, string> = {
    receipt: 'Receive',
    issue: 'Issue',
    adjustment: 'Adjustment',
    reserve: 'Reserve',
    unreserve: 'Unreserve',
  }
  return labels[t] ?? t
}

export const StockMovementPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [movementType, setMovementType] = useState<string>('')
  const [data, setData] = useState<StockMovementData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = (overrideFrom?: string, overrideTo?: string) => {
    if (!canSeeReports(user)) return
    const from = overrideFrom ?? dateFrom
    const to = overrideTo ?? dateTo
    setLoading(true)
    setError(null)
    const params: { date_from: string; date_to: string; movement_type?: string } = {
      date_from: from,
      date_to: to,
    }
    if (movementType) params.movement_type = movementType
    api
      .get<ApiResponse<StockMovementData>>('/reports/stock-movement', { params })
      .then((res) => {
        if (res.data?.data) {
          setData(res.data.data)
          setDateFrom(from)
          setDateTo(to)
        }
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
        <Typography variant="h5" sx={{ mb: 2 }}>Stock Movement Report</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Stock Movement Report</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <DateRangeShortcuts dateFrom={dateFrom} dateTo={dateTo} onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }} onRun={(from, to) => runReport(from, to)} />
            <TextField label="From" type="date" size="small" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
            <TextField label="To" type="date" size="small" value={dateTo} onChange={(e) => setDateTo(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Type</InputLabel>
              <Select
                value={movementType}
                label="Type"
                onChange={(e) => setMovementType(e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="receipt">Receive</MenuItem>
                <MenuItem value="issue">Issue</MenuItem>
                <MenuItem value="adjustment">Adjustment</MenuItem>
                <MenuItem value="reserve">Reserve</MenuItem>
                <MenuItem value="unreserve">Unreserve</MenuItem>
              </Select>
            </FormControl>
            <Button variant="contained" onClick={() => runReport()}>Run report</Button>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                const params: Record<string, unknown> = { date_from: dateFrom, date_to: dateTo }
                if (movementType) params.movement_type = movementType
                downloadReportExcel('/reports/stock-movement', params, 'stock-movement.xlsx')
              }}
            >
              Export to Excel
            </Button>
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

          <TableContainer component={Card}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Date</strong></TableCell>
                  <TableCell><strong>Type</strong></TableCell>
                  <TableCell><strong>Item</strong></TableCell>
                  <TableCell align="right"><strong>Qty</strong></TableCell>
                  <TableCell><strong>Ref</strong></TableCell>
                  <TableCell><strong>User</strong></TableCell>
                  <TableCell align="right"><strong>Balance after</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={row.movement_id}>
                    <TableCell>{row.movement_date}</TableCell>
                    <TableCell>{movementTypeLabel(row.movement_type)}</TableCell>
                    <TableCell>{row.item_name}</TableCell>
                    <TableCell align="right">
                      {row.quantity > 0 ? `+${row.quantity}` : row.quantity}
                    </TableCell>
                    <TableCell>{row.ref_display ?? '—'}</TableCell>
                    <TableCell>{row.created_by_name}</TableCell>
                    <TableCell align="right">{row.balance_after}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select period and run report.</Typography>
      )}
    </Box>
  )
}
