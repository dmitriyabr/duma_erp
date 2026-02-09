import { useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { downloadReportExcel } from '../../utils/reportExcel'
import { useApi } from '../../hooks/useApi'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Input,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

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
  const hasAccess = canSeeReports(user)
  const [asAtDate, setAsAtDate] = useState(defaultAsAt)
  const [requestedAsAtDate, setRequestedAsAtDate] = useState(defaultAsAt)

  const options = useMemo(
    () => ({ params: { as_at_date: requestedAsAtDate } }),
    [requestedAsAtDate]
  )
  const { data, loading, error, refetch } = useApi<InventoryValuationData>(
    hasAccess ? '/reports/inventory-valuation' : null,
    options
  )

  if (!hasAccess) {
    return (
      <div>
        <Typography variant="h5" className="mb-4">Inventory Valuation</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Inventory Valuation</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <Input
              label="As at date"
              type="date"
              value={asAtDate}
              onChange={(e) => setAsAtDate(e.target.value)}
              className="w-40"
            />
            <Button
              variant="contained"
              onClick={async () => {
                setRequestedAsAtDate(asAtDate)
                // if date didn't change, still allow manual refresh
                if (asAtDate === requestedAsAtDate) {
                  await refetch()
                }
              }}
            >
              Run report
            </Button>
            <Button variant="outlined" onClick={() => downloadReportExcel('/reports/inventory-valuation', { as_at_date: asAtDate }, 'inventory-valuation.xlsx')}>Export to Excel</Button>
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
            As at: {data.as_at_date}
          </Typography>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Category</TableHeaderCell>
                  <TableHeaderCell align="right">Items</TableHeaderCell>
                  <TableHeaderCell align="right">Quantity</TableHeaderCell>
                  <TableHeaderCell align="right">Unit cost avg (KES)</TableHeaderCell>
                  <TableHeaderCell align="right">Total value (KES)</TableHeaderCell>
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
                <TableRow hover={false} className="bg-slate-50">
                  <TableCell className="font-semibold">TOTAL</TableCell>
                  <TableCell align="right" className="font-semibold">{data.total_items}</TableCell>
                  <TableCell align="right" className="font-semibold">{data.total_quantity}</TableCell>
                  <TableCell>—</TableCell>
                  <TableCell align="right" className="font-semibold">{formatMoney(data.total_value)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select date and run report.</Typography>
      )}
    </div>
  )
}
