import { Download, FileText } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { api } from '../../services/api'
import { downloadAttachment } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'
import { useAuth } from '../../auth/AuthContext'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Tooltip } from '../../components/ui/Tooltip'
import { Spinner } from '../../components/ui/Spinner'

interface PaymentRow {
  id: number
  payment_number: string
  receipt_number: string | null
  student_id: number
  amount: string
  payment_method: string
  payment_date: string
  status: string
  confirmation_attachment_id: number | null
}

export const PaymentReceiptsPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAccountant = user?.role === 'Accountant'
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/payments?${sp.toString()}`
  }, [page, limit, statusFilter, dateFrom, dateTo])

  const { data, loading, error } = useApi<PaginatedResponse<PaymentRow>>(url)
  const payments = data?.items ?? []
  const total = data?.total ?? 0

  const downloadReceiptPdf = async (paymentId: number, receiptNumber: string) => {
    try {
      const res = await api.get(`/payments/${paymentId}/receipt/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `receipt_${receiptNumber || paymentId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Incoming Payments
        </Typography>
        {!isAccountant && (
          <Button variant="contained" onClick={() => navigate('/students')}>
            New payment (via student)
          </Button>
        )}
      </div>

      <div className="flex gap-4 mb-4 flex-wrap items-center">
        <div className="min-w-[140px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="cancelled">Cancelled</option>
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
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Receipt #</TableHeaderCell>
              <TableHeaderCell>Student ID</TableHeaderCell>
              <TableHeaderCell>Method</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="center">File</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDate(row.payment_date)}</TableCell>
                <TableCell>{row.receipt_number || row.payment_number}</TableCell>
                <TableCell>{row.student_id}</TableCell>
                <TableCell>{row.payment_method}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.amount))}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell align="center">
                  <div className="flex gap-2 justify-center">
                    {row.status === 'completed' && (
                      <Tooltip title="Receipt PDF">
                        <button
                          className="p-1 rounded-lg hover:bg-slate-100 transition-colors"
                          onClick={() => downloadReceiptPdf(row.id, row.receipt_number || row.payment_number)}
                        >
                          <FileText className="w-4 h-4 text-slate-600" />
                        </button>
                      </Tooltip>
                    )}
                    {row.confirmation_attachment_id != null && (
                      <Tooltip title="Download attachment">
                        <button
                          className="p-1 rounded-lg hover:bg-slate-100 transition-colors"
                          onClick={() => downloadAttachment(row.confirmation_attachment_id!)}
                        >
                          <Download className="w-4 h-4 text-slate-600" />
                        </button>
                      </Tooltip>
                    )}
                  </div>
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => navigate(`/students/${row.student_id}`)}
                  >
                    View student
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <TableCell colSpan={8} align="center" className="py-8">
                  <Spinner size="medium" />
                </TableCell>
              </TableRow>
            )}
            {!payments.length && !loading && (
              <TableRow>
                <TableCell colSpan={8} align="center" className="py-8">
                  <Typography color="secondary">No payments found</Typography>
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
          rowsPerPageOptions={[25, 50, 100]}
        />
      </div>
    </div>
  )
}
