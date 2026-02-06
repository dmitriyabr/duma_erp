import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate } from '../../utils/format'
import { canApproveGRN, isAccountant, isSuperAdmin } from '../../utils/permissions'

interface GRNLine {
  id: number
  po_line_id: number
  item_id: number | null
  quantity_received: number
}

interface GRNResponse {
  id: number
  grn_number: string
  po_id: number
  status: string
  received_date: string
  received_by_id: number
  approved_by_id: number | null
  approved_at: string | null
  notes: string | null
  lines: GRNLine[]
}

interface POLine {
  id: number
  description: string
  quantity_expected: number
  unit_price: number
}

export const GRNDetailPage = () => {
  const { grnId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const resolvedId = grnId ? Number(grnId) : null
  const [poLines, setPoLines] = useState<Map<number, POLine>>(new Map())
  const [error, setError] = useState<string | null>(null)
  const [confirmState, setConfirmState] = useState<{ open: boolean; action?: 'approve' | 'cancel' }>({
    open: false,
  })
  const [rollbackDialogOpen, setRollbackDialogOpen] = useState(false)
  const [rollbackReason, setRollbackReason] = useState('')

  const { data: grn, refetch: refetchGRN } = useApi<GRNResponse>(
    resolvedId ? `/procurement/grns/${resolvedId}` : null
  )
  const { data: poData } = useApi<{ lines: POLine[] }>(
    grn?.po_id ? `/procurement/purchase-orders/${grn.po_id}` : null
  )
  const { execute: approveGRN, loading: approving } = useApiMutation()
  const { execute: cancelGRN, loading: cancelling } = useApiMutation()
  const { execute: rollbackGRN, loading: rollingBack } = useApiMutation()
  const busy = approving || cancelling || rollingBack

  // Update PO lines map when PO data loads
  if (poData && poData.lines.length > 0 && poLines.size === 0) {
    setPoLines(new Map(poData.lines.map((line) => [line.id, line])))
  }

  const handleApprove = async () => {
    if (!resolvedId) return
    setError(null)
    const result = await approveGRN(() => api.post(`/procurement/grns/${resolvedId}/approve`))
    if (result) {
      await refetchGRN()
      setConfirmState({ open: false })
    } else {
      setError('Failed to approve GRN.')
    }
  }

  const handleCancel = async () => {
    if (!resolvedId) return
    setError(null)
    const result = await cancelGRN(() => api.post(`/procurement/grns/${resolvedId}/cancel`))
    if (result) {
      await refetchGRN()
      setConfirmState({ open: false })
    } else {
      setError('Failed to cancel GRN.')
    }
  }

  const handleRollback = async () => {
    if (!resolvedId || !rollbackReason.trim()) {
      setError('Enter rollback reason.')
      return
    }
    setError(null)
    const result = await rollbackGRN(() =>
      api.post(`/procurement/grns/${resolvedId}/rollback`, { reason: rollbackReason.trim() })
    )
    if (result) {
      setRollbackDialogOpen(false)
      setRollbackReason('')
      await refetchGRN()
    } else {
      setError('Failed to rollback GRN.')
    }
  }

  if (!grn) {
    return (
      <Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Box>
    )
  }

  const readOnly = isAccountant(user)
  const canApprove = !readOnly && grn.status === 'draft' && canApproveGRN(user)
  const canCancel = !readOnly && grn.status === 'draft'
  const canRollback = !readOnly && isSuperAdmin(user) && grn.status === 'approved'

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {grn.grn_number}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            PO #{grn.po_id} · {formatDate(grn.received_date)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip
            label={grn.status}
            color={grn.status === 'approved' ? 'success' : grn.status === 'cancelled' ? 'default' : 'warning'}
          />
          {canApprove ? (
            <Button variant="contained" disabled={busy} onClick={() => setConfirmState({ open: true, action: 'approve' })}>
              Approve
            </Button>
          ) : null}
          {canCancel ? (
            <Button variant="outlined" color="error" disabled={busy} onClick={() => setConfirmState({ open: true, action: 'cancel' })}>
              Cancel
            </Button>
          ) : null}
          {canRollback ? (
            <Button
              variant="outlined"
              color="warning"
              disabled={busy}
              onClick={() => {
                setRollbackReason('')
                setRollbackDialogOpen(true)
              }}
            >
              Rollback
            </Button>
          ) : null}
          <Button variant="outlined" onClick={() => navigate(`/procurement/orders/${grn.po_id}`)}>
            View PO
          </Button>
        </Box>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      {grn.notes ? (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Notes
          </Typography>
          <Typography>{grn.notes}</Typography>
        </Box>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Description</TableCell>
            <TableCell align="right">Quantity received</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {grn.lines.map((line) => {
            const poLine = poLines.get(line.po_line_id)
            return (
              <TableRow key={line.id}>
                <TableCell>{poLine?.description ?? '—'}</TableCell>
                <TableCell align="right">{line.quantity_received}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>

      <ConfirmDialog
        open={confirmState.open && confirmState.action === 'approve'}
        title="Approve GRN"
        description="Are you sure you want to approve this GRN? This will update stock and PO quantities."
        confirmLabel="Approve"
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={handleApprove}
      />

      <ConfirmDialog
        open={confirmState.open && confirmState.action === 'cancel'}
        title="Cancel GRN"
        description="Are you sure you want to cancel this GRN?"
        confirmLabel="Cancel"
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={handleCancel}
      />

      <Dialog open={rollbackDialogOpen} onClose={() => setRollbackDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Rollback GRN</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            This will cancel this approved GRN, revert PO received quantities, and (if tracked) revert warehouse stock receipts.
            Cancel procurement payments first if any exist.
          </Typography>
          <TextField
            label="Reason"
            value={rollbackReason}
            onChange={(e) => setRollbackReason(e.target.value)}
            multiline
            minRows={3}
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRollbackDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={handleRollback}
            disabled={!rollbackReason.trim() || busy}
          >
            {rollingBack ? 'Rolling back…' : 'Rollback'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
