import { Download } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../auth/AuthContext'
import { formatDate, formatMoney } from '../../utils/format'
import { downloadAttachment } from '../../utils/attachments'
import { isAccountant } from '../../utils/permissions'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Tooltip } from '../../components/ui/Tooltip'
import { Spinner } from '../../components/ui/Spinner'

interface PaymentRow {
  id: number
  payment_number: string
  po_id: number | null
  payee_name: string | null
  payment_date: string
  amount: number
  payment_method: string
  status: string
  proof_attachment_id: number | null
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'posted', label: 'Posted' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const ProcurementPaymentsListPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const readOnly = isAccountant(user)
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
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Procurement payments
        </Typography>
        {!readOnly && (
          <Button variant="contained" onClick={() => navigate('/procurement/payments/new')}>
            New payment
          </Button>
        )}
      </div>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="min-w-[120px]">
          <Input
            label="PO ID"
            type="number"
            value={poIdFilter}
            onChange={(e) => setPoIdFilter(e.target.value)}
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
              <TableHeaderCell>Payment Number</TableHeaderCell>
              <TableHeaderCell>PO ID</TableHeaderCell>
              <TableHeaderCell>Payee</TableHeaderCell>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell>Method</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="center">File</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
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
                <TableCell align="center">
                  {payment.proof_attachment_id != null && (
                    <Tooltip title="Download attachment">
                      <button
                        className="p-1 rounded-lg hover:bg-slate-100 transition-colors"
                        onClick={() => downloadAttachment(payment.proof_attachment_id!)}
                      >
                        <Download className="w-4 h-4 text-slate-600" />
                      </button>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => navigate(`/procurement/payments/${payment.id}`)}>
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={9} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!payments.length && !loading && (
              <TableRow>
                <td colSpan={9} className="px-4 py-8 text-center">
                  <Typography color="secondary">No payments found</Typography>
                </td>
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
