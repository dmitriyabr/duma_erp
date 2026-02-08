import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate } from '../../utils/format'
import { canApproveGRN, isAccountant, isSuperAdmin } from '../../utils/permissions'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { Dialog, DialogTitle, DialogContent, DialogActions } from '../../components/ui/Dialog'

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

  const { data: grn, loading, refetch: refetchGRN } = useApi<GRNResponse>(
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
  useEffect(() => {
    if (poData && poData.lines.length > 0 && poLines.size === 0) {
      setPoLines(new Map(poData.lines.map((line) => [line.id, line])))
    }
  }, [poData, poLines.size])

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

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!grn) {
    return (
      <div>
        {error && <Alert severity="error">{error}</Alert>}
      </div>
    )
  }

  const readOnly = isAccountant(user)
  const canApprove = !readOnly && grn.status === 'draft' && canApproveGRN(user)
  const canCancel = !readOnly && grn.status === 'draft'
  const canRollback = !readOnly && isSuperAdmin(user) && grn.status === 'approved'

  return (
    <div>
      <div className="flex justify-between items-start mb-4 flex-wrap gap-4">
        <div>
          <Typography variant="h4">
            {grn.grn_number}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            PO #{grn.po_id} · {formatDate(grn.received_date)}
          </Typography>
        </div>
        <div className="flex gap-2 items-center">
          <Chip
            label={grn.status}
            color={grn.status === 'approved' ? 'success' : grn.status === 'cancelled' ? 'default' : 'warning'}
          />
          {canApprove && (
            <Button variant="contained" disabled={busy} onClick={() => setConfirmState({ open: true, action: 'approve' })}>
              Approve
            </Button>
          )}
          {canCancel && (
            <Button variant="outlined" color="error" disabled={busy} onClick={() => setConfirmState({ open: true, action: 'cancel' })}>
              Cancel
            </Button>
          )}
          {canRollback && (
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
          )}
          <Button variant="outlined" onClick={() => navigate(`/procurement/orders/${grn.po_id}`)}>
            View PO
          </Button>
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      {grn.notes && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Notes
          </Typography>
          <Typography>{grn.notes}</Typography>
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Description</TableHeaderCell>
              <TableHeaderCell align="right">Quantity received</TableHeaderCell>
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
      </div>

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

      <Dialog open={rollbackDialogOpen} onClose={() => setRollbackDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Rollback GRN</DialogTitle>
        <DialogContent className="space-y-4">
          <Typography variant="body2" color="secondary">
            This will cancel this approved GRN, revert PO received quantities, and (if tracked) revert warehouse stock receipts.
            Cancel procurement payments first if any exist.
          </Typography>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Reason <span className="text-error">*</span>
            </label>
            <textarea
              value={rollbackReason}
              onChange={(e) => setRollbackReason(e.target.value)}
              rows={3}
              required
              className="w-full px-4 py-2.5 rounded-lg border-2 border-slate-200 hover:border-primary-light focus:border-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:outline-none transition-all duration-200"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setRollbackDialogOpen(false)}>
            Cancel
          </Button>
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
    </div>
  )
}
