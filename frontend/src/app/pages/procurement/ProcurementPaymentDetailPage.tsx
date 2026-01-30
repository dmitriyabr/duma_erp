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
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { openAttachmentInNewTab } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'

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

  const { data: payment, loading, error, refetch } = useApi<PaymentResponse>(
    resolvedId ? `/procurement/payments/${resolvedId}` : null
  )
  const { execute: cancelPayment, loading: cancelling, error: cancelError } = useApiMutation()
  const cancelBusy = cancelling

  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleCancel = async () => {
    if (!resolvedId || !cancelReason.trim()) {
      setValidationError('Enter cancellation reason.')
      return
    }
    setValidationError(null)

    const result = await cancelPayment(() =>
      api.post(`/procurement/payments/${resolvedId}/cancel`, {
        reason: cancelReason.trim(),
      })
    )

    if (result) {
      refetch()
      setCancelDialogOpen(false)
      setCancelReason('')
    }
  }

  if (!payment) {
    return (
      <Box>
        {error || cancelError || validationError ? (
          <Alert severity="error">{error || cancelError || validationError}</Alert>
        ) : null}
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
            disabled={!cancelReason.trim() || loading || cancelBusy}
          >
            Cancel payment
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
