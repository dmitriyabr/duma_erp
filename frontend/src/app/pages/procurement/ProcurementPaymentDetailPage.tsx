import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { openAttachmentInNewTab } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Textarea } from '../../components/ui/Textarea'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface PaymentResponse {
  id: number
  payment_number: string
  po_id: number | null
  purpose_id: number
  purpose_name: string | null
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

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!payment) {
    return (
      <div>
        {(error || cancelError || validationError) && (
          <Alert severity="error">
            {error || cancelError || validationError}
          </Alert>
        )}
      </div>
    )
  }

  const canCancel = payment.status === 'posted'

  return (
    <div>
      <div className="flex justify-between items-start mb-4 flex-wrap gap-4">
        <div>
          <Typography variant="h4">
            {payment.payment_number}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {formatDate(payment.payment_date)} · {formatMoney(payment.amount)}
          </Typography>
        </div>
        <div className="flex gap-2 items-center">
          <Chip
            label={payment.status}
            color={payment.status === 'posted' ? 'success' : 'default'}
          />
          {canCancel && (
            <Button variant="outlined" color="error" disabled={cancelBusy} onClick={() => setCancelDialogOpen(true)}>
              Cancel
            </Button>
          )}
          {payment.po_id && (
            <Button variant="outlined" onClick={() => navigate(`/procurement/orders/${payment.po_id}`)}>
              View PO
            </Button>
          )}
        </div>
      </div>

      {(error || cancelError || validationError) && (
        <Alert severity="error" className="mb-4">
          {error || cancelError || validationError}
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Amount
          </Typography>
          <Typography variant="h6">{formatMoney(payment.amount)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Category
          </Typography>
          <Typography>{payment.purpose_name ?? '—'}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Payment method
          </Typography>
          <Typography>{payment.payment_method}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Payee
          </Typography>
          <Typography>{payment.payee_name ?? '—'}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Reference number
          </Typography>
          <Typography>{payment.reference_number ?? '—'}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Paid by
          </Typography>
          <Typography>{payment.company_paid ? 'Company' : 'Employee'}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            PO ID
          </Typography>
          <Typography>{payment.po_id ?? '—'}</Typography>
        </div>
      </div>

      {payment.proof_text && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Proof / Reference
          </Typography>
          <Typography className="whitespace-pre-wrap">{payment.proof_text}</Typography>
        </div>
      )}

      {payment.proof_attachment_id && (
        <div className="mb-6">
          <Button
            variant="outlined"
            onClick={() => openAttachmentInNewTab(payment.proof_attachment_id!)}
          >
            View confirmation file
          </Button>
        </div>
      )}

      {payment.cancelled_reason && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Cancellation reason
          </Typography>
          <Typography className="text-error">{payment.cancelled_reason}</Typography>
        </div>
      )}

      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setCancelDialogOpen(false)} />
        <DialogTitle>Cancel payment</DialogTitle>
        <DialogContent>
          <Textarea
            label="Cancellation reason"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            rows={3}
            required
            error={validationError || undefined}
            placeholder="Enter cancellation reason"
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCancelDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="outlined" color="error" onClick={handleCancel} disabled={cancelBusy || !cancelReason.trim()}>
            {cancelBusy ? <Spinner size="small" /> : 'Cancel payment'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
