import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

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
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Purchase orders
        </Typography>
        <Button variant="contained" onClick={() => navigate('/procurement/orders/new')}>
          New order
        </Button>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, boxShadow: 1 }}>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Pending Goods Received
          </Typography>
          <Typography variant="h6">{pendingGrnCount}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Total supplier debt
          </Typography>
          <Typography variant="h6" color={totalDebt > 0 ? 'error' : 'inherit'}>
            {formatMoney(totalDebt)}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="Supplier"
          value={supplierFilter}
          onChange={(event) => setSupplierFilter(event.target.value)}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            {statusOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label="Date from"
          type="date"
          value={dateFrom}
          onChange={(event) => setDateFrom(event.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          label="Date to"
          type="date"
          value={dateTo}
          onChange={(event) => setDateTo(event.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>PO Number</TableCell>
            <TableCell>Supplier</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Order date</TableCell>
            <TableCell align="right">Expected total</TableCell>
            <TableCell align="right">Received</TableCell>
            <TableCell align="right">Paid</TableCell>
            <TableCell align="right">Debt</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => navigate(`/procurement/orders/${order.id}`)}>
                  View
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!orders.length && !loading ? (
            <TableRow>
              <TableCell colSpan={9} align="center">
                No purchase orders found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
      />
    </Box>
  )
}
