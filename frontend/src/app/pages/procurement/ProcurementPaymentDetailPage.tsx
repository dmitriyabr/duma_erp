import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { openAttachmentInNewTab } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PaymentResponse {
  id: number
  payment_number: string
  po_id: number | null
  purpose_id: number
  payee_name: string | null
  payment_date: string
  amount: number
  payment_method: string
  reference_number: string | null
  proof_text: string | null
  proof_attachment_id: number | null
  company_paid: boolean
  employee_paid_id: number | null
  status: string
  cancelled_reason: string | null
}

export const ProcurementPaymentDetailPage = () => {
  const { paymentId } = useParams()
  const navigate = useNavigate()
  const resolvedId = paymentId ? Number(paymentId) : null
  const [payment, setPayment] = useState<PaymentResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')

  const loadPayment = useCallback(async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<PaymentResponse>>(
        `/procurement/payments/${resolvedId}`
      )
      setPayment(response.data.data)
    } catch {
      setError('Failed to load payment.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  useEffect(() => {
    loadPayment()
  }, [loadPayment])

  const handleCancel = async () => {
    if (!resolvedId || !cancelReason.trim()) {
      setError('Enter cancellation reason.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.post(`/procurement/payments/${resolvedId}/cancel`, {
        reason: cancelReason.trim(),
      })
      await loadPayment()
      setCancelDialogOpen(false)
      setCancelReason('')
    } catch {
      setError('Failed to cancel payment.')
    } finally {
      setLoading(false)
    }
  }

  if (!payment) {
    return (
      <Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Box>
    )
  }

  const canCancel = payment.status === 'posted'

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {payment.payment_number}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {formatDate(payment.payment_date)} · {formatMoney(payment.amount)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip
            label={payment.status}
            color={payment.status === 'posted' ? 'success' : 'default'}
          />
          {canCancel ? (
            <Button
              variant="outlined"
              color="error"
              onClick={() => setCancelDialogOpen(true)}
            >
              Cancel
            </Button>
          ) : null}
          {payment.po_id ? (
            <Button variant="outlined" onClick={() => navigate(`/procurement/orders/${payment.po_id}`)}>
              View PO
            </Button>
          ) : null}
        </Box>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Amount
          </Typography>
          <Typography variant="h6">{formatMoney(payment.amount)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Payment method
          </Typography>
          <Typography>{payment.payment_method}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Payee
          </Typography>
          <Typography>{payment.payee_name ?? '—'}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Reference number
          </Typography>
          <Typography>{payment.reference_number ?? '—'}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Paid by
          </Typography>
          <Typography>{payment.company_paid ? 'Company' : 'Employee'}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            PO ID
          </Typography>
          <Typography>{payment.po_id ?? '—'}</Typography>
        </Box>
      </Box>

      {payment.proof_text ? (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Proof
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{payment.proof_text}</Typography>
        </Box>
      ) : null}
      {payment.proof_attachment_id ? (
        <Box sx={{ mb: 3 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={() => openAttachmentInNewTab(payment.proof_attachment_id!)}
          >
            View confirmation file
          </Button>
        </Box>
      ) : null}

      {payment.cancelled_reason ? (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Cancellation reason
          </Typography>
          <Typography color="error">{payment.cancelled_reason}</Typography>
        </Box>
      ) : null}

      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Cancel payment</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Reason"
            value={cancelReason}
            onChange={(event) => setCancelReason(event.target.value)}
            multiline
            minRows={3}
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCancelDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleCancel}
            disabled={!cancelReason.trim() || loading}
          >
            Cancel payment
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
