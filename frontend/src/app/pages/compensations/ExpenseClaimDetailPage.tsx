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
import { useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface ClaimResponse {
  id: number
  claim_number: string
  employee_id: number
  purpose_id: number
  amount: number
  description: string
  expense_date: string
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
  const isSuperAdmin = user?.role === 'SuperAdmin'
  const resolvedId = claimId ? Number(claimId) : null

  const { data: claim, loading, error, refetch } = useApi<ClaimResponse>(
    resolvedId ? `/compensations/claims/${resolvedId}` : null
  )
  const { execute: approveClaim, loading: approving, error: approveError } = useApiMutation()
  const { execute: rejectClaim, loading: rejecting, error: rejectError } = useApiMutation()

  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

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

  if (!claim) {
    return (
      <Box>
        {error || approveError || rejectError || validationError ? (
          <Alert severity="error">{error || approveError || rejectError || validationError}</Alert>
        ) : null}
      </Box>
    )
  }

  const canApprove = isSuperAdmin && (claim.status === 'pending_approval' || claim.status === 'draft')
  const canReject = isSuperAdmin && (claim.status === 'pending_approval' || claim.status === 'draft')

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {claim.claim_number}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {formatDate(claim.expense_date)} · {formatMoney(claim.amount)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip label={claim.status} color={statusColor(claim.status)} />
          {canApprove ? (
            <Button variant="contained" color="success" onClick={() => setApproveDialogOpen(true)}>
              Approve
            </Button>
          ) : null}
          {canReject ? (
            <Button variant="contained" color="error" onClick={() => setRejectDialogOpen(true)}>
              Reject
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
          <Typography variant="h6">{formatMoney(claim.amount)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Paid Amount
          </Typography>
          <Typography variant="h6">{formatMoney(claim.paid_amount)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Remaining Amount
          </Typography>
          <Typography variant="h6" color={claim.remaining_amount > 0 ? 'error' : 'inherit'}>
            {formatMoney(claim.remaining_amount)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Status
          </Typography>
          <Typography>{claim.status}</Typography>
        </Box>
      </Box>

      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
          Description
        </Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{claim.description}</Typography>
      </Box>

      <Dialog open={approveDialogOpen} onClose={() => setApproveDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Approve expense claim</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Reason (optional)"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApproveDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" color="success" onClick={handleApprove} disabled={approving}>
            Approve
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Reject expense claim</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Rejection reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            multiline
            minRows={3}
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleReject} disabled={loading || !reason.trim()}>
            Reject
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
