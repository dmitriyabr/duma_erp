import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'
import { isSuperAdmin } from '../../utils/permissions'
import { openAttachmentInNewTab } from '../../utils/attachments'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Textarea } from '../../components/ui/Textarea'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface ClaimResponse {
  id: number
  claim_number: string
  employee_id: number
  employee_name: string
  purpose_id: number
  amount: number
  payee_name: string | null
  description: string
  rejection_reason: string | null
  expense_date: string
  proof_text: string | null
  proof_attachment_id: number | null
  status: string
  paid_amount: number
  remaining_amount: number
  auto_created_from_payment: boolean
  related_procurement_payment_id: number | null
}

const statusColor = (status: string) => {
  if (status === 'approved' || status === 'paid') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'pending_approval' || status === 'partially_paid') return 'warning'
  return 'info'
}

export const ExpenseClaimDetailPage = () => {
  const { claimId } = useParams()
  const { user } = useAuth()
  const userIsSuperAdmin = isSuperAdmin(user)
  const resolvedId = claimId ? Number(claimId) : null

  const { data: claim, loading, error, refetch } = useApi<ClaimResponse>(
    resolvedId ? `/compensations/claims/${resolvedId}` : null
  )
  const { execute: approveClaim, loading: approving, error: approveError } = useApiMutation()
  const { execute: rejectClaim, loading: _rejecting, error: rejectError } = useApiMutation()

  const [proofPreview, setState] = useState<{
    url: string | null
    contentType: string | null
    fileName: string | null
    loading: boolean
    error: string | null
  }>({ url: null, contentType: null, fileName: null, loading: false, error: null })

  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  useEffect(() => {
    const attachmentId = claim?.proof_attachment_id
    if (!attachmentId) {
      queueMicrotask(() => {
        setState((prev) => {
          if (prev.url) URL.revokeObjectURL(prev.url)
          return { url: null, contentType: null, fileName: null, loading: false, error: null }
        })
      })
      return
    }

    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) setState((prev) => ({ ...prev, loading: true, error: null }))
    })

    api
      .get(`/attachments/${attachmentId}/download`, { responseType: 'blob' })
      .then((res) => {
        const blob = res.data as Blob
        const url = URL.createObjectURL(blob)

        const disposition = (res.headers as Record<string, string | undefined>)['content-disposition']
        const match = disposition?.match(/filename="?([^";]+)"?/)
        const filename = match?.[1] ?? null

        if (cancelled) {
          URL.revokeObjectURL(url)
          return
        }

        setState((prev) => {
          if (prev.url) URL.revokeObjectURL(prev.url)
          return {
            url,
            contentType: blob.type || null,
            fileName: filename,
            loading: false,
            error: null,
          }
        })
      })
      .catch(() => {
        if (!cancelled) setState((prev) => ({ ...prev, loading: false, error: 'Failed to load receipt preview.' }))
      })
      .finally(() => {
        if (!cancelled) setState((prev) => ({ ...prev, loading: false }))
      })

    return () => {
      cancelled = true
    }
  }, [claim?.proof_attachment_id])

  const handleApprove = async () => {
    if (!resolvedId) return
    const result = await approveClaim(() =>
      api.post(`/compensations/claims/${resolvedId}/approve`, {
        approve: true,
        reason: reason.trim() || null,
      })
    )

    if (result) {
      setApproveDialogOpen(false)
      setReason('')
      refetch()
    }
  }

  const handleReject = async () => {
    if (!resolvedId || !reason.trim()) {
      setValidationError('Enter rejection reason.')
      return
    }
    setValidationError(null)

    const result = await rejectClaim(() =>
      api.post(`/compensations/claims/${resolvedId}/approve`, {
        approve: false,
        reason: reason.trim(),
      })
    )

    if (result) {
      setRejectDialogOpen(false)
      setReason('')
      refetch()
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!claim) {
    return (
      <div>
        {(error || approveError || rejectError || validationError) && (
          <Alert severity="error">
            {error || approveError || rejectError || validationError}
          </Alert>
        )}
      </div>
    )
  }

  const splitLegacyRejectionReason = (description: string): { description: string; rejection_reason: string | null } => {
    const marker = 'Rejection reason:'
    const idx = description.indexOf(marker)
    if (idx === -1) return { description, rejection_reason: null }
    const before = description.slice(0, idx).trim()
    const after = description.slice(idx + marker.length).trim()
    return { description: before || description, rejection_reason: after || null }
  }

  const legacySplit = splitLegacyRejectionReason(claim.description)
  const displayDescription = claim.rejection_reason ? claim.description : legacySplit.description
  const displayRejectionReason = claim.rejection_reason ?? legacySplit.rejection_reason

  const canApprove = userIsSuperAdmin && claim.status === 'pending_approval'
  const canReject = userIsSuperAdmin && claim.status === 'pending_approval'

  return (
    <div>
      <div className="flex justify-between items-start mb-4 flex-wrap gap-4">
        <div>
          <Typography variant="h4">
            {claim.claim_number}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {formatDate(claim.expense_date)} · {formatMoney(claim.amount)}
          </Typography>
        </div>
        <div className="flex gap-2 items-center">
          <Chip label={claim.status} color={statusColor(claim.status)} />
          {canApprove && (
            <Button variant="contained" color="success" onClick={() => setApproveDialogOpen(true)}>
              Approve
            </Button>
          )}
          {canReject && (
            <Button variant="outlined" color="error" onClick={() => setRejectDialogOpen(true)}>
              Reject
            </Button>
          )}
        </div>
      </div>

      {(error || approveError || rejectError || validationError) && (
        <Alert severity="error" className="mb-4">
          {error || approveError || rejectError || validationError}
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Employee
          </Typography>
          <Typography>{claim.employee_name}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Amount
          </Typography>
          <Typography variant="h6">{formatMoney(claim.amount)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Status
          </Typography>
          <Chip label={claim.status} color={statusColor(claim.status)} />
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Paid amount
          </Typography>
          <Typography>{formatMoney(claim.paid_amount)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Remaining amount
          </Typography>
          <Typography className={claim.remaining_amount > 0 ? 'text-error' : ''}>
            {formatMoney(claim.remaining_amount)}
          </Typography>
        </div>
      </div>

      <div className="mb-6">
        <Typography variant="subtitle2" color="secondary" className="mb-1">
          Description
        </Typography>
        <Typography>{displayDescription}</Typography>
      </div>

      {displayRejectionReason && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Rejection reason
          </Typography>
          <Typography>{displayRejectionReason}</Typography>
        </div>
      )}

      {(claim.payee_name || claim.proof_text || claim.proof_attachment_id != null) && (
        <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Typography variant="subtitle2" color="secondary" className="mb-1">
              Payee / vendor
            </Typography>
            <Typography>{claim.payee_name ?? '—'}</Typography>
          </div>
          <div>
            <Typography variant="subtitle2" color="secondary" className="mb-1">
              Proof
            </Typography>
            <div className="flex items-center gap-2 flex-wrap">
              <Typography>
                {claim.proof_text ??
                  (claim.proof_attachment_id != null ? `Receipt file attached${proofPreview.fileName ? ` (${proofPreview.fileName})` : ''}` : '—')}
              </Typography>
              {claim.proof_attachment_id != null && (
                <Button size="small" variant="outlined" onClick={() => openAttachmentInNewTab(claim.proof_attachment_id!)}>
                  Open
                </Button>
              )}
            </div>

            {claim.proof_attachment_id != null && (
              <div className="mt-3">
                {proofPreview.loading && (
                  <div className="flex items-center gap-2">
                    <Spinner size="small" />
                    <Typography variant="body2" color="secondary">
                      Loading preview...
                    </Typography>
                  </div>
                )}
                {proofPreview.error && (
                  <Alert severity="error">{proofPreview.error}</Alert>
                )}
                {!proofPreview.loading && !proofPreview.error && proofPreview.url && (
                  <>
                    {proofPreview.contentType?.startsWith('image/') ? (
                      <img
                        src={proofPreview.url}
                        alt={proofPreview.fileName ?? 'Receipt'}
                        className="w-full max-h-[70vh] object-contain rounded-xl border border-slate-200 bg-white"
                      />
                    ) : proofPreview.contentType === 'application/pdf' ? (
                      <iframe
                        src={proofPreview.url}
                        title={proofPreview.fileName ?? 'Receipt PDF'}
                        className="w-full h-[70vh] rounded-xl border border-slate-200 bg-white"
                      />
                    ) : (
                      <Typography variant="body2" color="secondary">
                        Preview is not available for this file type.
                      </Typography>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <Dialog open={approveDialogOpen} onClose={() => setApproveDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setApproveDialogOpen(false)} />
        <DialogTitle>Approve expense claim</DialogTitle>
        <DialogContent>
          <Textarea
            label="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Optional approval reason"
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setApproveDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" color="success" onClick={handleApprove} disabled={approving}>
            {approving ? <Spinner size="small" /> : 'Approve'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setRejectDialogOpen(false)} />
        <DialogTitle>Reject expense claim</DialogTitle>
        <DialogContent>
          <Textarea
            label="Rejection reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            required
            error={validationError || undefined}
            placeholder="Enter rejection reason"
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setRejectDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="outlined" color="error" onClick={handleReject} disabled={_rejecting}>
            {_rejecting ? <Spinner size="small" /> : 'Reject'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
