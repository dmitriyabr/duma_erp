import { Download, FileText } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { api } from '../../services/api'
import { downloadAttachment } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'
import { formatStudentNumberShort } from '../../utils/studentNumber'
import { useAuth } from '../../auth/AuthContext'
import { canCancelPayment, canManageStudents } from '../../utils/permissions'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Tooltip } from '../../components/ui/Tooltip'
import { Spinner } from '../../components/ui/Spinner'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'

interface PaymentRow {
  id: number
  payment_number: string
  receipt_number: string | null
  student_id: number
  student_name: string | null
  student_number: string | null
  billing_account_id?: number | null
  billing_account_name?: string | null
  billing_account_number?: string | null
  amount: string
  payment_method: string
  payment_date: string
  reference: string | null
  status: string
  confirmation_attachment_id: number | null
  refunded_amount?: string | number | null
  refundable_amount?: string | number | null
  refund_status?: string | null
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'completed', label: 'Completed' },
  { value: 'pending', label: 'Pending' },
  { value: 'cancelled', label: 'Cancelled' },
]

const methodOptions = [
  { value: 'all', label: 'All methods' },
  { value: 'mpesa', label: 'M-Pesa' },
  { value: 'bank_transfer', label: 'Bank transfer' },
]

export const PaymentReceiptsPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = canManageStudents(user)
  const canRefund = canCancelPayment(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [methodFilter, setMethodFilter] = useState<string>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [search, setSearch] = useState('')
  const [refundDialogPayment, setRefundDialogPayment] = useState<PaymentRow | null>(null)
  const [refundForm, setRefundForm] = useState({
    amount: '',
    refund_date: new Date().toISOString().slice(0, 10),
    reason: '',
    notes: '',
  })
  const debouncedSearch = useDebouncedValue(search, 300)
  const refundPaymentMutation = useApiMutation()

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (methodFilter !== 'all') params.payment_method = methodFilter
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim()
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/payments?${sp.toString()}`
  }, [page, limit, statusFilter, methodFilter, dateFrom, dateTo, debouncedSearch])

  const { data, loading, error, refetch } = useApi<PaginatedResponse<PaymentRow>>(url)
  const payments = data?.items ?? []
  const total = data?.total ?? 0

  const getRefundableAmount = (payment: PaymentRow | null | undefined) =>
    Number(payment?.refundable_amount ?? payment?.amount ?? 0)

  const getPaymentStatusLabel = (payment: PaymentRow) => {
    if (payment.refund_status === 'full') return 'completed / refunded'
    if (payment.refund_status === 'partial') return 'completed / partially refunded'
    return payment.status
  }

  const openRefundDialog = (payment: PaymentRow) => {
    setRefundDialogPayment(payment)
    setRefundForm({
      amount: String(getRefundableAmount(payment)),
      refund_date: new Date().toISOString().slice(0, 10),
      reason: '',
      notes: '',
    })
  }

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

  const submitRefund = async () => {
    if (!refundDialogPayment) return
    const result = await refundPaymentMutation.execute(() =>
      api.post(`/payments/${refundDialogPayment.id}/refunds`, {
        amount: Number(refundForm.amount),
        refund_date: refundForm.refund_date,
        reason: refundForm.reason.trim(),
        notes: refundForm.notes.trim() || null,
      })
    )
    if (result) {
      setRefundDialogPayment(null)
      refetch()
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Student payments
        </Typography>
        {canManage && (
          <Button variant="contained" onClick={() => navigate('/payments/new')}>
            Record payment
          </Button>
        )}
      </div>

      <Typography variant="body2" color="secondary" className="mb-4">
        All payment transactions received from students in one list.
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap items-center">
        <div className="flex-1 min-w-[220px]">
          <Input
            label="Search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(0)
            }}
            placeholder="Payment #, receipt, reference, student"
          />
        </div>
        <div className="min-w-[140px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(0)
            }}
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Method"
            value={methodFilter}
            onChange={(e) => {
              setMethodFilter(e.target.value)
              setPage(0)
            }}
          >
            {methodOptions.map((option) => (
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
            onChange={(e) => {
              setDateFrom(e.target.value)
              setPage(0)
            }}
          />
        </div>
        <div className="min-w-[160px]">
          <Input
            label="Date to"
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value)
              setPage(0)
            }}
          />
        </div>
      </div>

      {(error || refundPaymentMutation.error) && (
        <Alert severity="error" className="mb-4">
          {error || refundPaymentMutation.error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Payment #</TableHeaderCell>
              <TableHeaderCell>Receipt #</TableHeaderCell>
              <TableHeaderCell>Student</TableHeaderCell>
              <TableHeaderCell>Billing account</TableHeaderCell>
              <TableHeaderCell>Reference</TableHeaderCell>
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
                <TableCell className="font-mono text-xs">{row.payment_number}</TableCell>
                <TableCell>{row.receipt_number || '—'}</TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span>{row.student_name || `Student ID ${row.student_id}`}</span>
                    <span className="text-xs text-slate-500">
                      {row.student_number
                        ? `#${formatStudentNumberShort(row.student_number)}`
                        : `ID ${row.student_id}`}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span>{row.billing_account_name ?? '—'}</span>
                    <span className="text-xs text-slate-500">{row.billing_account_number ?? '—'}</span>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs">{row.reference || '—'}</TableCell>
                <TableCell>{row.payment_method}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.amount))}</TableCell>
                <TableCell>{getPaymentStatusLabel(row)}</TableCell>
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
                  <div className="flex gap-2 justify-end">
                    {canRefund && row.status === 'completed' && getRefundableAmount(row) > 0 && (
                      <Button
                        size="small"
                        variant="outlined"
                        color="error"
                        onClick={() => openRefundDialog(row)}
                      >
                        Refund
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => navigate(`/students/${row.student_id}?tab=payments`)}
                    >
                      View student
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={11} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!payments.length && !loading && (
              <TableRow>
                <td colSpan={11} className="px-4 py-8 text-center">
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
          rowsPerPageOptions={[25, 50, 100]}
        />
      </div>

      <Dialog open={Boolean(refundDialogPayment)} onClose={() => setRefundDialogPayment(null)} maxWidth="sm">
        <DialogCloseButton onClose={() => setRefundDialogPayment(null)} />
        <DialogTitle>Refund payment</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Typography variant="body2">
              Payment: {refundDialogPayment?.payment_number ?? '—'}
            </Typography>
            <Typography variant="body2">
              Refundable amount: {formatMoney(getRefundableAmount(refundDialogPayment))}
            </Typography>
            <Input
              label="Amount"
              type="number"
              value={refundForm.amount}
              onChange={(e) => setRefundForm((current) => ({ ...current, amount: e.target.value }))}
            />
            <Input
              label="Refund date"
              type="date"
              value={refundForm.refund_date}
              onChange={(e) => setRefundForm((current) => ({ ...current, refund_date: e.target.value }))}
            />
            <Input
              label="Reason"
              value={refundForm.reason}
              onChange={(e) => setRefundForm((current) => ({ ...current, reason: e.target.value }))}
            />
            <Input
              label="Notes"
              value={refundForm.notes}
              onChange={(e) => setRefundForm((current) => ({ ...current, notes: e.target.value }))}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setRefundDialogPayment(null)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={submitRefund}
            disabled={refundPaymentMutation.loading}
          >
            {refundPaymentMutation.loading ? <Spinner size="small" /> : 'Refund'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
