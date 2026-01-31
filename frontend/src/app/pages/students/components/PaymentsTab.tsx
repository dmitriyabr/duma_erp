import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">Payments</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" onClick={openManualAllocation}>
            Allocate credit
          </Button>
          <Button
            variant="contained"
            onClick={() => navigate('/payments/new', { state: { studentId } })}
          >
            Record payment
          </Button>
        </Box>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Payment #</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Amount</TableCell>
            <TableCell>Method</TableCell>
            <TableCell>Date</TableCell>
            <TableCell>Receipt</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => setSelectedPayment(payment)}>
                  View
                </Button>
                {payment.status === 'completed' ? (
                  <Button
                    size="small"
                    startIcon={<PictureAsPdfIcon />}
                    onClick={() => downloadReceiptPdf(payment)}
                    disabled={downloadingReceiptId === payment.id}
                  >
                    {downloadingReceiptId === payment.id ? '…' : 'Receipt PDF'}
                  </Button>
                ) : null}
                {canCancelPayment(user) && payment.status === 'pending' ? (
                  <Button size="small" onClick={() => cancelPayment(payment.id)}>
                    Cancel
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
          {!payments.length ? (
            <TableRow>
              <TableCell colSpan={7} align="center">
                No payments yet
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      {/* Payment Detail Dialog */}
      <Dialog
        open={Boolean(selectedPayment)}
        onClose={() => setSelectedPayment(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Payment details</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 1 }}>
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
          {selectedPayment?.confirmation_attachment_id ? (
            <Button
              variant="outlined"
              size="small"
              onClick={() => openAttachmentInNewTab(selectedPayment!.confirmation_attachment_id!)}
            >
              View confirmation file
            </Button>
          ) : null}
          {selectedPayment?.status === 'completed' ? (
            <Button
              variant="outlined"
              size="small"
              startIcon={<PictureAsPdfIcon />}
              onClick={() => selectedPayment && downloadReceiptPdf(selectedPayment)}
              disabled={downloadingReceiptId === selectedPayment?.id}
            >
              {downloadingReceiptId === selectedPayment?.id ? 'Downloading…' : 'Download receipt PDF'}
            </Button>
          ) : null}
          <Typography variant="body2">Notes: {selectedPayment?.notes ?? '—'}</Typography>
          <Typography variant="body2">Status: {selectedPayment?.status ?? '—'}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedPayment(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Allocation Dialog */}
      <Dialog
        open={allocationDialogOpen}
        onClose={() => setAllocationDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Allocate credit</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Invoice</InputLabel>
            <Select
              value={allocationForm.invoice_id}
              label="Invoice"
              onChange={(event) => {
                const nextInvoice = event.target.value
                setAllocationForm({ ...allocationForm, invoice_id: nextInvoice, invoice_line_id: '' })
                loadInvoiceLinesForAllocation(nextInvoice)
              }}
            >
              {openInvoicesForAllocation.map((invoice) => (
                <MenuItem key={invoice.id} value={String(invoice.id)}>
                  {invoice.invoice_number} · {formatMoney(parseNumber(invoice.amount_due))}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl>
            <InputLabel>Invoice line (optional)</InputLabel>
            <Select
              value={allocationForm.invoice_line_id}
              label="Invoice line (optional)"
              onChange={(event) =>
                setAllocationForm({ ...allocationForm, invoice_line_id: event.target.value })
              }
            >
              <MenuItem value="">Any line</MenuItem>
              {allocationLines.map((line) => (
                <MenuItem key={line.id} value={String(line.id)}>
                  {line.description} · {formatMoney(parseNumber(line.remaining_amount))}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Amount"
            type="number"
            value={allocationForm.amount}
            onChange={(event) => setAllocationForm({ ...allocationForm, amount: event.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAllocationDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitManualAllocation} disabled={loading}>
            Allocate
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
