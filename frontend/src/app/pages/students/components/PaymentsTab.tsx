import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText } from 'lucide-react'
import { useAuth } from '../../../auth/AuthContext'
import { INVOICE_LIST_LIMIT, PAYMENTS_LIST_LIMIT } from '../../../constants/pagination'
import { useApi, useApiMutation } from '../../../hooks/useApi'
import { api, unwrapResponse } from '../../../services/api'
import { canCancelPayment } from '../../../utils/permissions'
import { formatDate, formatMoney } from '../../../utils/format'
import { openAttachmentInNewTab } from '../../../utils/attachments'
import type {
  ApiResponse,
  InvoiceDetail,
  InvoiceLine,
  InvoiceSummary,
  PaginatedResponse,
  PaymentResponse,
} from '../types'
import { parseNumber } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Button } from '../../../components/ui/Button'
import { Input } from '../../../components/ui/Input'
import { Select } from '../../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../../components/ui/Dialog'
import { Spinner } from '../../../components/ui/Spinner'

interface PaymentsTabProps {
  studentId: number
  onError: (message: string) => void
  onBalanceChange: () => void
  onAllocationResult: (message: string) => void
  /** When provided, use instead of own fetch — avoids duplicate GET /invoices from parent (StudentDetailPage). */
  initialInvoices?: InvoiceSummary[] | null
  invoicesLoading?: boolean
}

export const PaymentsTab = ({
  studentId,
  onError,
  onBalanceChange,
  onAllocationResult: _onAllocationResult,
  initialInvoices,
  invoicesLoading: _invoicesLoading,
}: PaymentsTabProps) => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [selectedPayment, setSelectedPayment] = useState<PaymentResponse | null>(null)
  const [allocationDialogOpen, setAllocationDialogOpen] = useState(false)
  const [allocationForm, setAllocationForm] = useState({
    invoice_id: '',
    invoice_line_id: '',
    amount: '',
  })
  const [allocationLines, setAllocationLines] = useState<InvoiceLine[]>([])
  const [downloadingReceiptId, setDownloadingReceiptId] = useState<number | null>(null)

  const paymentsApi = useApi<PaginatedResponse<PaymentResponse>>('/payments', {
    params: { student_id: studentId, limit: PAYMENTS_LIST_LIMIT, page: 1 },
  }, [studentId])
  const invoicesApi = useApi<PaginatedResponse<InvoiceSummary>>(
    initialInvoices === undefined ? '/invoices' : null,
    initialInvoices === undefined
      ? { params: { student_id: studentId, limit: INVOICE_LIST_LIMIT, page: 1 } }
      : undefined,
    initialInvoices === undefined ? [studentId] : []
  )
  const allocationMutation = useApiMutation<unknown>()
  const cancelPaymentMutation = useApiMutation<unknown>()

  const payments = paymentsApi.data?.items ?? []
  const invoices = initialInvoices !== undefined ? (initialInvoices ?? []) : (invoicesApi.data?.items ?? [])
  const loading = allocationMutation.loading || cancelPaymentMutation.loading

  useEffect(() => {
    if (paymentsApi.error) onError(paymentsApi.error)
  }, [paymentsApi.error, onError])
  useEffect(() => {
    if (initialInvoices === undefined && invoicesApi.error) onError(invoicesApi.error)
  }, [initialInvoices, invoicesApi.error, onError])

  const openManualAllocation = () => {
    invoicesApi.refetch()
    setAllocationLines([])
    setAllocationForm({ invoice_id: '', invoice_line_id: '', amount: '' })
    setAllocationDialogOpen(true)
  }

  const loadInvoiceLinesForAllocation = async (invoiceId: string) => {
    if (!invoiceId) {
      setAllocationLines([])
      return
    }
    try {
      const response = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${invoiceId}`)
      setAllocationLines(response.data.data.lines)
    } catch {
      setAllocationLines([])
    }
  }

  const submitManualAllocation = async () => {
    allocationMutation.reset()
    const ok = await allocationMutation.execute(() =>
      api
        .post('/payments/allocations/manual', {
          student_id: studentId,
          invoice_id: Number(allocationForm.invoice_id),
          invoice_line_id: allocationForm.invoice_line_id
            ? Number(allocationForm.invoice_line_id)
            : null,
          amount: Number(allocationForm.amount),
        })
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      setAllocationDialogOpen(false)
      onBalanceChange()
    } else if (allocationMutation.error) {
      onError(allocationMutation.error)
    }
  }

  const cancelPayment = async (paymentId: number) => {
    cancelPaymentMutation.reset()
    const ok = await cancelPaymentMutation.execute(() =>
      api
        .post(`/payments/${paymentId}/cancel`)
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      paymentsApi.refetch()
      onBalanceChange()
    } else if (cancelPaymentMutation.error) {
      onError(cancelPaymentMutation.error)
    }
  }

  const openInvoicesForAllocation = invoices.filter((invoice) => {
    const status = invoice.status?.toLowerCase()
    return status !== 'paid' && status !== 'cancelled' && status !== 'void'
  })

  const downloadReceiptPdf = async (payment: PaymentResponse) => {
    if (payment.status !== 'completed') return
    setDownloadingReceiptId(payment.id)
    try {
      const response = await api.get(`/payments/${payment.id}/receipt/pdf`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `receipt_${payment.receipt_number ?? payment.payment_number}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      onError('Failed to download receipt PDF.')
    } finally {
      setDownloadingReceiptId(null)
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Typography variant="h6">Payments</Typography>
        <div className="flex gap-2">
          <Button variant="outlined" onClick={openManualAllocation}>
            Allocate credit
          </Button>
          <Button
            variant="contained"
            onClick={() => navigate('/payments/new', { state: { studentId } })}
          >
            Record payment
          </Button>
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Payment #</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Amount</TableHeaderCell>
              <TableHeaderCell>Method</TableHeaderCell>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Receipt</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.map((payment) => (
              <TableRow key={payment.id}>
                <TableCell>{payment.payment_number}</TableCell>
                <TableCell>{payment.status}</TableCell>
                <TableCell>{formatMoney(parseNumber(payment.amount))}</TableCell>
                <TableCell>{payment.payment_method}</TableCell>
                <TableCell>{formatDate(payment.payment_date)}</TableCell>
                <TableCell>{payment.receipt_number ?? '—'}</TableCell>
                <TableCell align="right">
                  <div className="flex gap-2 justify-end">
                    <Button size="small" onClick={() => setSelectedPayment(payment)}>
                      View
                    </Button>
                    {payment.status === 'completed' && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => downloadReceiptPdf(payment)}
                        disabled={downloadingReceiptId === payment.id}
                      >
                        <FileText className="h-4 w-4 mr-1" />
                        {downloadingReceiptId === payment.id ? '…' : 'Receipt PDF'}
                      </Button>
                    )}
                    {canCancelPayment(user) && payment.status === 'pending' && (
                      <Button size="small" variant="outlined" onClick={() => cancelPayment(payment.id)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {!payments.length && (
              <TableRow>
                <TableCell colSpan={7} align="center" className="py-8">
                  <Typography color="secondary">No payments yet</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Payment Detail Dialog */}
      <Dialog
        open={Boolean(selectedPayment)}
        onClose={() => setSelectedPayment(null)}
        maxWidth="sm"
      >
        <DialogCloseButton onClose={() => setSelectedPayment(null)} />
        <DialogTitle>Payment details</DialogTitle>
        <DialogContent>
          <div className="space-y-2 mt-4">
            <Typography variant="body2">Payment #: {selectedPayment?.payment_number ?? '—'}</Typography>
            <Typography variant="body2">Receipt #: {selectedPayment?.receipt_number ?? '—'}</Typography>
            <Typography variant="body2">
              Amount: {formatMoney(parseNumber(selectedPayment?.amount))}
            </Typography>
            <Typography variant="body2">Method: {selectedPayment?.payment_method ?? '—'}</Typography>
            <Typography variant="body2">
              Date: {selectedPayment?.payment_date ? formatDate(selectedPayment.payment_date) : '—'}
            </Typography>
            <Typography variant="body2">Reference: {selectedPayment?.reference ?? '—'}</Typography>
            {selectedPayment?.confirmation_attachment_id && (
              <Button
                variant="outlined"
                size="small"
                onClick={() => openAttachmentInNewTab(selectedPayment!.confirmation_attachment_id!)}
              >
                View confirmation file
              </Button>
            )}
            {selectedPayment?.status === 'completed' && (
              <Button
                variant="outlined"
                size="small"
                onClick={() => selectedPayment && downloadReceiptPdf(selectedPayment)}
                disabled={downloadingReceiptId === selectedPayment?.id}
              >
                <FileText className="h-4 w-4 mr-1" />
                {downloadingReceiptId === selectedPayment?.id ? 'Downloading…' : 'Download receipt PDF'}
              </Button>
            )}
            <Typography variant="body2">Notes: {selectedPayment?.notes ?? '—'}</Typography>
            <Typography variant="body2">Status: {selectedPayment?.status ?? '—'}</Typography>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setSelectedPayment(null)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Allocation Dialog */}
      <Dialog
        open={allocationDialogOpen}
        onClose={() => setAllocationDialogOpen(false)}
        maxWidth="sm"
      >
        <DialogCloseButton onClose={() => setAllocationDialogOpen(false)} />
        <DialogTitle>Allocate credit</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Select
              value={allocationForm.invoice_id}
              onChange={(e) => {
                const nextInvoice = e.target.value
                setAllocationForm({ ...allocationForm, invoice_id: nextInvoice, invoice_line_id: '' })
                loadInvoiceLinesForAllocation(nextInvoice)
              }}
              label="Invoice"
            >
              <option value="">Select invoice</option>
              {openInvoicesForAllocation.map((invoice) => (
                <option key={invoice.id} value={String(invoice.id)}>
                  {invoice.invoice_number} · {formatMoney(parseNumber(invoice.amount_due))}
                </option>
              ))}
            </Select>
            <Select
              value={allocationForm.invoice_line_id}
              onChange={(e) =>
                setAllocationForm({ ...allocationForm, invoice_line_id: e.target.value })
              }
              label="Invoice line (optional)"
            >
              <option value="">Any line</option>
              {allocationLines.map((line) => (
                <option key={line.id} value={String(line.id)}>
                  {line.description} · {formatMoney(parseNumber(line.remaining_amount))}
                </option>
              ))}
            </Select>
            <Input
              label="Amount"
              type="number"
              value={allocationForm.amount}
              onChange={(e) => setAllocationForm({ ...allocationForm, amount: e.target.value })}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAllocationDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitManualAllocation} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Allocate'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
