import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { DateRangeShortcuts, getDateRangeForPreset } from '../../components/DateRangeShortcuts'
import { downloadReportExcel } from '../../utils/reportExcel'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Input,
  Select,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

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
      <div>
        <Typography variant="h5" className="mb-4">Stock Movement Report</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Stock Movement Report</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <DateRangeShortcuts dateFrom={dateFrom} dateTo={dateTo} onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }} onRun={(from, to) => runReport(from, to)} />
            <Input label="From" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" />
            <Input label="To" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" />
            <Select
              value={movementType}
              onChange={(e) => setMovementType(e.target.value)}
              label="Type"
              className="min-w-[140px]"
            >
              <option value="">All</option>
              <option value="receipt">Receive</option>
              <option value="issue">Issue</option>
              <option value="adjustment">Adjustment</option>
              <option value="reserve">Reserve</option>
              <option value="unreserve">Unreserve</option>
            </Select>
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
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Spinner size="medium" />
        </div>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {!loading && data && (
        <>
          <Typography variant="body2" color="secondary" className="mb-4">
            Period: {data.date_from} — {data.date_to}
          </Typography>

          <Card>
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell><strong>Date</strong></TableHeaderCell>
                  <TableHeaderCell><strong>Type</strong></TableHeaderCell>
                  <TableHeaderCell><strong>Item</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Qty</strong></TableHeaderCell>
                  <TableHeaderCell><strong>Ref</strong></TableHeaderCell>
                  <TableHeaderCell><strong>User</strong></TableHeaderCell>
                  <TableHeaderCell align="right"><strong>Balance after</strong></TableHeaderCell>
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
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select period and run report.</Typography>
      )}
    </div>
  )
}
