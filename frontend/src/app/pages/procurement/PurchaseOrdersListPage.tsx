import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Card, CardContent } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'

interface PORow {
  id: number
  po_number: string
  supplier_name: string
  status: string
  order_date: string
  expected_total: number
  received_value: number
  paid_total: number
  debt_amount: number
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'ordered', label: 'Ordered' },
  { value: 'partially_received', label: 'Partially Received' },
  { value: 'received', label: 'Received' },
  { value: 'closed', label: 'Closed' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const PurchaseOrdersListPage = () => {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [supplierFilter, setSupplierFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const requestParams = useMemo(() => {
    const params: Record<string, string | number> = {
      page: page + 1,
      limit,
    }
    if (statusFilter !== 'all') {
      params.status = statusFilter
    }
    if (supplierFilter.trim()) {
      params.supplier_name = supplierFilter.trim()
    }
    if (dateFrom) {
      params.date_from = dateFrom
    }
    if (dateTo) {
      params.date_to = dateTo
    }
    return params
  }, [page, limit, statusFilter, supplierFilter, dateFrom, dateTo])

  const { data: ordersData, loading, error } = useApi<PaginatedResponse<PORow>>(
    '/procurement/purchase-orders',
    { params: requestParams },
    [requestParams]
  )

  const { data: dashboardData } = useApi<{ total_supplier_debt: number; pending_grn_count: number }>(
    '/procurement/dashboard'
  )

  const orders = ordersData?.items || []
  const total = ordersData?.total || 0
  const pendingGrnCount = dashboardData?.pending_grn_count || 0
  const totalDebt = dashboardData?.total_supplier_debt || 0

  const statusColor = (status: string) => {
    if (status === 'received' || status === 'closed') return 'success'
    if (status === 'cancelled') return 'default'
    if (status === 'ordered' || status === 'partially_received') return 'warning'
    return 'info'
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Purchase orders
        </Typography>
        <Button variant="contained" onClick={() => navigate('/procurement/orders/new')}>
          New order
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <Card>
          <CardContent>
            <Typography variant="subtitle2" color="secondary">
              Pending Goods Received
            </Typography>
            <Typography variant="h6" className="mt-1">{pendingGrnCount}</Typography>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <Typography variant="subtitle2" color="secondary">
              Total supplier debt
            </Typography>
            <Typography variant="h6" className={totalDebt > 0 ? 'text-error mt-1' : 'mt-1'}>
              {formatMoney(totalDebt)}
            </Typography>
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Supplier"
            value={supplierFilter}
            onChange={(e) => setSupplierFilter(e.target.value)}
            placeholder="Supplier name"
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[160px]">
          <Input
            label="Date from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div className="min-w-[160px]">
          <Input
            label="Date to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>PO Number</TableHeaderCell>
              <TableHeaderCell>Supplier</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Order date</TableHeaderCell>
              <TableHeaderCell align="right">Expected total</TableHeaderCell>
              <TableHeaderCell align="right">Received</TableHeaderCell>
              <TableHeaderCell align="right">Paid</TableHeaderCell>
              <TableHeaderCell align="right">Debt</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orders.map((order) => (
              <TableRow key={order.id}>
                <TableCell>{order.po_number}</TableCell>
                <TableCell>{order.supplier_name}</TableCell>
                <TableCell>
                  <Chip size="small" label={order.status} color={statusColor(order.status)} />
                </TableCell>
                <TableCell>{formatDate(order.order_date)}</TableCell>
                <TableCell align="right">{formatMoney(order.expected_total)}</TableCell>
                <TableCell align="right">{formatMoney(order.received_value)}</TableCell>
                <TableCell align="right">{formatMoney(order.paid_total)}</TableCell>
                <TableCell align="right">{formatMoney(order.debt_amount)}</TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => navigate(`/procurement/orders/${order.id}`)}>
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <TableCell colSpan={9} align="center" className="py-8">
                  <Spinner size="medium" />
                </TableCell>
              </TableRow>
            )}
            {!orders.length && !loading && (
              <TableRow>
                <TableCell colSpan={9} align="center" className="py-8">
                  <Typography color="secondary">No purchase orders found</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(newLimit) => {
            setLimit(newLimit)
            setPage(0)
          }}
        />
      </div>
    </div>
  )
}
