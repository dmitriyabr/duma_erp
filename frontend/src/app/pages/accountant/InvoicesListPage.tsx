import {
  Alert,
  Box,
  Button,
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

interface InvoiceRow {
  id: number
  invoice_number: string
  student_id: number
  student_name: string | null
  invoice_type: string
  status: string
  total: number
  paid_total: number
  amount_due: number
  issue_date: string | null
  due_date: string | null
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'issued', label: 'Issued' },
  { value: 'partially_paid', label: 'Partially Paid' },
  { value: 'paid', label: 'Paid' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const InvoicesListPage = () => {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [search, setSearch] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (search.trim()) params.search = search.trim()
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/invoices?${sp.toString()}`
  }, [page, limit, statusFilter, search])

  const { data, loading, error } = useApi<PaginatedResponse<InvoiceRow>>(url)
  const invoices = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Students Invoices
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          label="Search (invoice #, student)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="small"
          sx={{ minWidth: 200 }}
        />
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {statusOptions.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Invoice #</TableCell>
            <TableCell>Student</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Issue date</TableCell>
            <TableCell>Due date</TableCell>
            <TableCell align="right">Total</TableCell>
            <TableCell align="right">Paid</TableCell>
            <TableCell align="right">Due</TableCell>
            <TableCell>Status</TableCell>
            <TableCell></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={10}>Loading…</TableCell>
            </TableRow>
          ) : (
            invoices.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.invoice_number}</TableCell>
                <TableCell>{row.student_name ?? row.student_id}</TableCell>
                <TableCell>{row.invoice_type}</TableCell>
                <TableCell>{row.issue_date ? formatDate(row.issue_date) : '—'}</TableCell>
                <TableCell>{row.due_date ? formatDate(row.due_date) : '—'}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.total))}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.paid_total))}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.amount_due))}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell>
                  <Button size="small" onClick={() => navigate(`/students/${row.student_id}`)}>
                    View student
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={limit}
        onRowsPerPageChange={(e) => {
          setLimit(Number(e.target.value))
          setPage(0)
        }}
        rowsPerPageOptions={[25, 50, 100]}
      />
    </Box>
  )
}
