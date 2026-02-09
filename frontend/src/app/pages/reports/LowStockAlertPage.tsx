import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { downloadReportExcel } from '../../utils/reportExcel'
import {
  Alert,
  Button,
  Card,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

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
      <div>
        <Typography variant="h5" className="mb-4">Low Stock Alert</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <Typography variant="h5">Low Stock Alert</Typography>
        <Button variant="outlined" onClick={() => downloadReportExcel('/reports/low-stock-alert', {}, 'low-stock-alert.xlsx')}>Export to Excel</Button>
      </div>
      {data != null && data.total_low_count > 0 && (
        <Alert severity="info" className="mb-4">
          {data.total_low_count} item(s) at or below minimum level.
        </Alert>
      )}

      {loading && (
        <div className="flex justify-center py-8">
          <Spinner size="medium" />
        </div>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {!loading && data && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Item</TableHeaderCell>
                <TableHeaderCell>SKU</TableHeaderCell>
                <TableHeaderCell align="right">Current</TableHeaderCell>
                <TableHeaderCell align="right">Min level</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Suggested order</TableHeaderCell>
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
        </div>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Loading…</Typography>
      )}
    </div>
  )
}
