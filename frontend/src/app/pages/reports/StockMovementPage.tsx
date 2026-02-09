import { useCallback, useEffect, useState } from 'react'
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
  const hasAccess = canSeeReports(user)
  const [dateFrom, setDateFrom] = useState(() => defaultRange().from)
  const [dateTo, setDateTo] = useState(() => defaultRange().to)
  const [movementType, setMovementType] = useState<string>('')
  const [data, setData] = useState<StockMovementData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendForbidden, setBackendForbidden] = useState(false)

  const runReportForRange = useCallback((from: string, to: string) => {
    if (!hasAccess) return
    if (from !== dateFrom) setDateFrom(from)
    if (to !== dateTo) setDateTo(to)
    setLoading(true)
    setError(null)
    setBackendForbidden(false)
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
        }
      })
      .catch((err) => {
        if (err.response?.status === 403) setBackendForbidden(true)
        else setError(err.response?.data?.detail ?? 'Failed to load report')
      })
      .finally(() => setLoading(false))
  }, [hasAccess, dateFrom, dateTo, movementType])

  useEffect(() => {
    if (!hasAccess) return
    const { from, to } = defaultRange()
    const t = window.setTimeout(() => runReportForRange(from, to), 0)
    return () => window.clearTimeout(t)
  }, [hasAccess, user, runReportForRange])

  if (!hasAccess || backendForbidden) {
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
          <div className="flex flex-wrap items-center gap-4">
            <DateRangeShortcuts
              dateFrom={dateFrom}
              dateTo={dateTo}
              onRangeChange={(from, to) => { setDateFrom(from); setDateTo(to) }}
              onRun={(from, to) => runReportForRange(from ?? dateFrom, to ?? dateTo)}
            />
            <Input
              label="From"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <Input
              label="To"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
            <Select
              value={movementType}
              onChange={(e) => setMovementType(e.target.value)}
              label="Type"
              containerClassName="w-[220px] min-w-[180px]"
            >
              <option value="">All</option>
              <option value="receipt">Receive</option>
              <option value="issue">Issue</option>
              <option value="adjustment">Adjustment</option>
              <option value="reserve">Reserve</option>
              <option value="unreserve">Unreserve</option>
            </Select>
            <Button variant="contained" onClick={() => runReportForRange(dateFrom, dateTo)} className="self-end">
              Run report
            </Button>
            <Button
              variant="outlined"
              onClick={() => {
                const params: Record<string, unknown> = { date_from: dateFrom, date_to: dateTo }
                if (movementType) params.movement_type = movementType
                downloadReportExcel('/reports/stock-movement', params, 'stock-movement.xlsx')
              }}
              className="self-end"
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

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Date</TableHeaderCell>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>Item</TableHeaderCell>
                  <TableHeaderCell align="right">Qty</TableHeaderCell>
                  <TableHeaderCell>Ref</TableHeaderCell>
                  <TableHeaderCell>User</TableHeaderCell>
                  <TableHeaderCell align="right">Balance after</TableHeaderCell>
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
          </div>
        </>
      )}

      {!loading && !data && !error && hasAccess && (
        <Typography color="secondary">Select period and run report.</Typography>
      )}
    </div>
  )
}
