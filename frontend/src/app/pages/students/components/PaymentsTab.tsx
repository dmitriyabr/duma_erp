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
import React, { useEffect, useState } from 'react'
import { useAuth } from '../../../auth/AuthContext'
import { api } from '../../../services/api'
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
}

export const PaymentsTab = ({
  studentId,
  onError,
  onBalanceChange,
  onAllocationResult,
}: PaymentsTabProps) => {
  const { user } = useAuth()
  const [loading, setLoading] = useState(false)
  const [payments, setPayments] = useState<PaymentResponse[]>([])
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false)
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    payment_method: 'mpesa',
    payment_date: new Date().toISOString().slice(0, 10),
    reference: '',
    notes: '',
  })
  const [selectedPayment, setSelectedPayment] = useState<PaymentResponse | null>(null)
  const [confirmationAttachmentId, setConfirmationAttachmentId] = useState<number | null>(null)
  const [confirmationFileName, setConfirmationFileName] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const confirmationFileInputRef = React.useRef<HTMLInputElement>(null)
  const [allocationDialogOpen, setAllocationDialogOpen] = useState(false)
  const [allocationForm, setAllocationForm] = useState({
    invoice_id: '',
    invoice_line_id: '',
    amount: '',
  })
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([])
  const [allocationLines, setAllocationLines] = useState<InvoiceLine[]>([])
  const [downloadingReceiptId, setDownloadingReceiptId] = useState<number | null>(null)

  const loadPayments = async () => {
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<PaymentResponse>>>('/payments', {
        params: { student_id: studentId, limit: 100, page: 1 },
      })
      setPayments(response.data.data.items)
    } catch {
      onError('Failed to load payments.')
    }
  }

  const loadInvoices = async () => {
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<InvoiceSummary>>>('/invoices', {
        params: { student_id: studentId, limit: 200, page: 1 },
      })
      setInvoices(response.data.data.items)
    } catch {
      onError('Failed to load invoices.')
    }
  }

  useEffect(() => {
    loadPayments()
  }, [studentId])

  const openPaymentDialog = () => {
    setPaymentForm({
      amount: '',
      payment_method: 'mpesa',
      payment_date: new Date().toISOString().slice(0, 10),
      reference: '',
      notes: '',
    })
    setConfirmationAttachmentId(null)
    setConfirmationFileName(null)
    if (confirmationFileInputRef.current) confirmationFileInputRef.current.value = ''
    setPaymentDialogOpen(true)
  }

  const handleConfirmationFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploadingFile(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await api.post<ApiResponse<{ id: number; file_name: string }>>(
        '/attachments',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      setConfirmationAttachmentId(response.data.data.id)
      setConfirmationFileName(file.name)
    } catch {
      onError('Failed to upload confirmation file.')
    } finally {
      setUploadingFile(false)
    }
  }

  const submitPayment = async () => {
    const hasReference = Boolean(paymentForm.reference?.trim())
    const hasFile = confirmationAttachmentId != null
    if (!hasReference && !hasFile) {
      onError('Reference or confirmation file is required.')
      return
    }
    setLoading(true)
    try {
      const createResponse = await api.post<ApiResponse<PaymentResponse>>('/payments', {
        student_id: studentId,
        amount: Number(paymentForm.amount),
        payment_method: paymentForm.payment_method,
        payment_date: paymentForm.payment_date,
        reference: paymentForm.reference.trim() || null,
        confirmation_attachment_id: confirmationAttachmentId ?? undefined,
        notes: paymentForm.notes.trim() || null,
      })
      await api.post(`/payments/${createResponse.data.data.id}/complete`)
      const allocationResponse = await api.post<
        ApiResponse<{
          total_allocated: number
          invoices_fully_paid: number
          invoices_partially_paid: number
          remaining_balance: number
        }>
      >('/payments/allocations/auto', { student_id: studentId })
      const result = allocationResponse.data.data
      onAllocationResult(
        `Auto-allocated ${formatMoney(parseNumber(result.total_allocated))}. Remaining balance: ${formatMoney(
          parseNumber(result.remaining_balance)
        )}.`
      )
      setPaymentDialogOpen(false)
      await loadPayments()
      onBalanceChange()
    } catch {
      onError('Failed to record payment.')
    } finally {
      setLoading(false)
    }
  }

  const openManualAllocation = async () => {
    await loadInvoices()
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
    setLoading(true)
    try {
      await api.post('/payments/allocations/manual', {
        student_id: studentId,
        invoice_id: Number(allocationForm.invoice_id),
        invoice_line_id: allocationForm.invoice_line_id
          ? Number(allocationForm.invoice_line_id)
          : null,
        amount: Number(allocationForm.amount),
      })
      setAllocationDialogOpen(false)
      onBalanceChange()
    } catch {
      onError('Failed to allocate credit.')
    } finally {
      setLoading(false)
    }
  }

  const cancelPayment = async (paymentId: number) => {
    setLoading(true)
    try {
      await api.post(`/payments/${paymentId}/cancel`)
      await loadPayments()
      onBalanceChange()
    } catch {
      onError('Failed to cancel payment.')
    } finally {
      setLoading(false)
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
          <Button variant="contained" onClick={openPaymentDialog}>
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
                {user?.role === 'SuperAdmin' && payment.status === 'pending' ? (
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

      {/* Payment Dialog */}
      <Dialog open={paymentDialogOpen} onClose={() => setPaymentDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Record payment</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Amount"
            type="number"
            value={paymentForm.amount}
            onChange={(event) => setPaymentForm({ ...paymentForm, amount: event.target.value })}
          />
          <FormControl>
            <InputLabel>Method</InputLabel>
            <Select
              value={paymentForm.payment_method}
              label="Method"
              onChange={(event) => setPaymentForm({ ...paymentForm, payment_method: event.target.value })}
            >
              <MenuItem value="mpesa">M-Pesa</MenuItem>
              <MenuItem value="bank_transfer">Bank transfer</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Payment date"
            type="date"
            value={paymentForm.payment_date}
            onChange={(event) => setPaymentForm({ ...paymentForm, payment_date: event.target.value })}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="Reference (optional if file uploaded)"
            value={paymentForm.reference}
            onChange={(event) => setPaymentForm({ ...paymentForm, reference: event.target.value })}
            helperText="Reference or confirmation file below is required"
          />
          <Box>
            <Button
              variant="outlined"
              component="label"
              disabled={uploadingFile}
              sx={{ mr: 1 }}
            >
              {uploadingFile ? 'Uploading…' : 'Upload confirmation (image/PDF)'}
              <input
                ref={confirmationFileInputRef}
                type="file"
                hidden
                accept="image/*,.pdf,application/pdf"
                onChange={handleConfirmationFileChange}
              />
            </Button>
            {confirmationFileName && (
              <Typography variant="body2" color="text.secondary" component="span">
                {confirmationFileName}
              </Typography>
            )}
          </Box>
          <TextField
            label="Notes"
            value={paymentForm.notes}
            onChange={(event) => setPaymentForm({ ...paymentForm, notes: event.target.value })}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPaymentDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={submitPayment}
            disabled={
              loading ||
              (!paymentForm.reference?.trim() && confirmationAttachmentId == null)
            }
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

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
