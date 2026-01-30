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
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'

interface PaymentRow {
  id: number
  payment_number: string
  po_id: number | null
  payee_name: string | null
  payment_date: string
  amount: number
  payment_method: string
  status: string
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'posted', label: 'Posted' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const ProcurementPaymentsListPage = () => {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [poIdFilter, setPoIdFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (poIdFilter.trim()) params.po_id = Number(poIdFilter)
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo

    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/procurement/payments?${sp.toString()}`
  }, [page, limit, statusFilter, poIdFilter, dateFrom, dateTo])

  const { data, loading, error } = useApi<PaginatedResponse<PaymentRow>>(url)

  const payments = data?.items || []
  const total = data?.total || 0

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Procurement payments
        </Typography>
        <Button variant="contained" onClick={() => navigate('/procurement/payments/new')}>
          New payment
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="PO ID"
          value={poIdFilter}
          onChange={(event) => setPoIdFilter(event.target.value)}
          size="small"
          type="number"
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
            <TableCell>Payment Number</TableCell>
            <TableCell>PO ID</TableCell>
            <TableCell>Payee</TableCell>
            <TableCell>Date</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell>Method</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {payments.map((payment) => (
            <TableRow key={payment.id}>
              <TableCell>{payment.payment_number}</TableCell>
              <TableCell>{payment.po_id ?? '—'}</TableCell>
              <TableCell>{payment.payee_name ?? '—'}</TableCell>
              <TableCell>{formatDate(payment.payment_date)}</TableCell>
              <TableCell align="right">{formatMoney(payment.amount)}</TableCell>
              <TableCell>{payment.payment_method}</TableCell>
              <TableCell>
                <Chip
                  size="small"
                  label={payment.status}
                  color={payment.status === 'posted' ? 'success' : 'default'}
                />
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => navigate(`/procurement/payments/${payment.id}`)}>
                  View
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {loading ? (
            <TableRow>
              <TableCell colSpan={8} align="center">
                Loading…
              </TableCell>
            </TableRow>
          ) : null}
          {!payments.length && !loading ? (
            <TableRow>
              <TableCell colSpan={8} align="center">
                No payments found
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
