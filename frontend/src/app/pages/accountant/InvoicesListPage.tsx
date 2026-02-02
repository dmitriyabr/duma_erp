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
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

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
    <div>
      <Typography variant="h4" className="mb-4">
        Students Invoices
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap items-center">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Search (invoice #, student)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Invoice number or student name"
          />
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
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
              <TableHeaderCell>Invoice #</TableHeaderCell>
              <TableHeaderCell>Student</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Total</TableHeaderCell>
              <TableHeaderCell align="right">Paid</TableHeaderCell>
              <TableHeaderCell align="right">Due</TableHeaderCell>
              <TableHeaderCell>Issue date</TableHeaderCell>
              <TableHeaderCell>Due date</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {invoices.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell>{invoice.invoice_number}</TableCell>
                <TableCell>{invoice.student_name ?? '—'}</TableCell>
                <TableCell>{invoice.invoice_type}</TableCell>
                <TableCell>{invoice.status}</TableCell>
                <TableCell align="right">{formatMoney(invoice.total)}</TableCell>
                <TableCell align="right">{formatMoney(invoice.paid_total)}</TableCell>
                <TableCell align="right">{formatMoney(invoice.amount_due)}</TableCell>
                <TableCell>{invoice.issue_date ? formatDate(invoice.issue_date) : '—'}</TableCell>
                <TableCell>{invoice.due_date ? formatDate(invoice.due_date) : '—'}</TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => navigate(`/students/${invoice.student_id}`)}>
                    View student
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <TableCell colSpan={10} align="center" className="py-8">
                  <Spinner size="medium" />
                </TableCell>
              </TableRow>
            )}
            {!invoices.length && !loading && (
              <TableRow>
                <TableCell colSpan={10} align="center" className="py-8">
                  <Typography color="secondary">No invoices found</Typography>
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
