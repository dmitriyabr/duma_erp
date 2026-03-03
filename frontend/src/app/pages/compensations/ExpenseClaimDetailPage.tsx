import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
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
  payment_id: number | null
  fee_payment_id: number | null
  employee_id: number
  employee_name: string
  purpose_id: number
  amount: number
  expense_amount: number
  fee_amount: number
  payee_name: string | null
  description: string
  rejection_reason: string | null
  edit_comment: string | null
  expense_date: string
  proof_text: string | null
  proof_attachment_id: number | null
  fee_proof_text: string | null
  fee_proof_attachment_id: number | null
  status: string
  paid_amount: number
  remaining_amount: number
  auto_created_from_payment: boolean
  related_procurement_payment_id: number | null
}

const statusColor = (status: string) => {
  if (status === 'approved' || status === 'paid') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'pending_approval' || status === 'partially_paid' || status === 'needs_edit') return 'warning'
  return 'info'
}

export const ExpenseClaimDetailPage = () => {
  const navigate = useNavigate()
  const { claimId } = useParams()
  const { user } = useAuth()
  const userIsSuperAdmin = isSuperAdmin(user)
  const resolvedId = claimId ? Number(claimId) : null

  const { data: claim, loading, error, refetch } = useApi<ClaimResponse>(
    resolvedId ? `/compensations/claims/${resolvedId}` : null
  )
  const { execute: approveClaim, loading: approving, error: approveError } = useApiMutation()
  const { execute: rejectClaim, loading: _rejecting, error: rejectError } = useApiMutation()
  const { execute: sendToEdit, loading: sendingToEdit, error: sendToEditError } = useApiMutation()
  const { execute: resubmitClaim, loading: resubmitting, error: resubmitError } = useApiMutation()

  const [proofPreview, setState] = useState<{
    url: string | null
    contentType: string | null
    fileName: string | null
    loading: boolean
    error: string | null
  }>({ url: null, contentType: null, fileName: null, loading: false, error: null })

  const [feeProofPreview, setFeeProofPreview] = useState<{
    url: string | null
    contentType: string | null
    fileName: string | null
    loading: boolean
    error: string | null
  }>({ url: null, contentType: null, fileName: null, loading: false, error: null })

  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [sendToEditDialogOpen, setSendToEditDialogOpen] = useState(false)
  const [approveReason, setApproveReason] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [editComment, setEditComment] = useState('')
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

  useEffect(() => {
    const attachmentId = claim?.fee_proof_attachment_id
    if (!attachmentId) {
      queueMicrotask(() => {
        setFeeProofPreview((prev) => {
          if (prev.url) URL.revokeObjectURL(prev.url)
          return { url: null, contentType: null, fileName: null, loading: false, error: null }
        })
      })
      return
    }

    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) setFeeProofPreview((prev) => ({ ...prev, loading: true, error: null }))
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

        setFeeProofPreview((prev) => {
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
        if (!cancelled) setFeeProofPreview((prev) => ({ ...prev, loading: false, error: 'Failed to load fee proof preview.' }))
      })
      .finally(() => {
        if (!cancelled) setFeeProofPreview((prev) => ({ ...prev, loading: false }))
      })

    return () => {
      cancelled = true
    }
  }, [claim?.fee_proof_attachment_id])

  const handleApprove = async () => {
    if (!resolvedId) return
    const result = await approveClaim(() =>
      api.post(`/compensations/claims/${resolvedId}/approve`, {
        approve: true,
        reason: approveReason.trim() || null,
      })
    )

    if (result) {
      setApproveDialogOpen(false)
      setApproveReason('')
      refetch()
    }
  }

  const handleReject = async () => {
    if (!resolvedId || !rejectReason.trim()) {
      setValidationError('Enter rejection reason.')
      return
    }
    setValidationError(null)

    const result = await rejectClaim(() =>
      api.post(`/compensations/claims/${resolvedId}/approve`, {
        approve: false,
        reason: rejectReason.trim(),
      })
    )

    if (result) {
      setRejectDialogOpen(false)
      setRejectReason('')
      refetch()
    }
  }

  const handleSendToEdit = async () => {
    if (!resolvedId || !editComment.trim()) {
      setValidationError('Enter edit comment.')
      return
    }
    setValidationError(null)

    const result = await sendToEdit(() =>
      api.post(`/compensations/claims/${resolvedId}/send-to-edit`, {
        comment: editComment.trim(),
      })
    )
    if (result) {
      setSendToEditDialogOpen(false)
      setEditComment('')
      refetch()
    }
  }

  const handleResubmit = async () => {
    if (!resolvedId) return
    const result = await resubmitClaim(() => api.post(`/compensations/claims/${resolvedId}/submit`))
    if (result) {
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
        {(error || approveError || rejectError || sendToEditError || resubmitError || validationError) && (
          <Alert severity="error">
            {error || approveError || rejectError || sendToEditError || resubmitError || validationError}
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
  const canSendToEdit =
    userIsSuperAdmin && claim.status === 'pending_approval' && !claim.auto_created_from_payment
  const canEditClaim =
    user?.id === claim.employee_id &&
    !claim.auto_created_from_payment &&
    (claim.status === 'pending_approval' || claim.status === 'needs_edit' || claim.status === 'draft')
  const canResubmit = user?.id === claim.employee_id && claim.status === 'needs_edit'

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
          {canEditClaim && (
            <Button variant="outlined" onClick={() => navigate(`/compensations/claims/${claim.id}/edit`)}>
              Edit claim
            </Button>
          )}
          {canResubmit && (
            <Button variant="contained" onClick={handleResubmit} disabled={resubmitting}>
              {resubmitting ? <Spinner size="small" /> : 'Resubmit'}
            </Button>
          )}
          {canSendToEdit && (
            <Button variant="outlined" color="warning" onClick={() => setSendToEditDialogOpen(true)}>
              Send to edit
            </Button>
          )}
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

      {(error || approveError || rejectError || sendToEditError || resubmitError || validationError) && (
        <Alert severity="error" className="mb-4">
          {error || approveError || rejectError || sendToEditError || resubmitError || validationError}
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
            Total amount
          </Typography>
          <Typography variant="h6">{formatMoney(claim.amount)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Expense amount
          </Typography>
          <Typography>{formatMoney(claim.expense_amount)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Transaction fee
          </Typography>
          <Typography>{formatMoney(claim.fee_amount)}</Typography>
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

      {claim.edit_comment && claim.status === 'needs_edit' && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Needs edit comment
          </Typography>
          <Typography>{claim.edit_comment}</Typography>
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

      {(claim.fee_amount > 0 || claim.fee_proof_text || claim.fee_proof_attachment_id != null) && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Fee proof
          </Typography>
          <div className="flex items-center gap-2 flex-wrap">
            <Typography>
              {claim.fee_proof_text ??
                (claim.fee_proof_attachment_id != null
                  ? `Fee proof file attached${feeProofPreview.fileName ? ` (${feeProofPreview.fileName})` : ''}`
                  : '—')}
            </Typography>
            {claim.fee_proof_attachment_id != null && (
              <Button size="small" variant="outlined" onClick={() => openAttachmentInNewTab(claim.fee_proof_attachment_id!)}>
                Open
              </Button>
            )}
          </div>

          {claim.fee_proof_attachment_id != null && (
            <div className="mt-3">
              {feeProofPreview.loading && (
                <div className="flex items-center gap-2">
                  <Spinner size="small" />
                  <Typography variant="body2" color="secondary">
                    Loading preview...
                  </Typography>
                </div>
              )}
              {feeProofPreview.error && <Alert severity="error">{feeProofPreview.error}</Alert>}
              {!feeProofPreview.loading && !feeProofPreview.error && feeProofPreview.url && (
                <>
                  {feeProofPreview.contentType?.startsWith('image/') ? (
                    <img
                      src={feeProofPreview.url}
                      alt={feeProofPreview.fileName ?? 'Fee proof'}
                      className="w-full max-h-[70vh] object-contain rounded-xl border border-slate-200 bg-white"
                    />
                  ) : feeProofPreview.contentType === 'application/pdf' ? (
                    <iframe
                      src={feeProofPreview.url}
                      title={feeProofPreview.fileName ?? 'Fee proof PDF'}
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
      )}

      <Dialog open={approveDialogOpen} onClose={() => setApproveDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setApproveDialogOpen(false)} />
        <DialogTitle>Approve expense claim</DialogTitle>
        <DialogContent>
          <Textarea
            label="Reason (optional)"
            value={approveReason}
            onChange={(e) => setApproveReason(e.target.value)}
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
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
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

      <Dialog open={sendToEditDialogOpen} onClose={() => setSendToEditDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setSendToEditDialogOpen(false)} />
        <DialogTitle>Send claim to edit</DialogTitle>
        <DialogContent>
          <Textarea
            label="Comment"
            value={editComment}
            onChange={(e) => setEditComment(e.target.value)}
            rows={3}
            required
            error={validationError || undefined}
            placeholder="What should be corrected"
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setSendToEditDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="outlined" color="warning" onClick={handleSendToEdit} disabled={sendingToEdit}>
            {sendingToEdit ? <Spinner size="small" /> : 'Send to edit'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
