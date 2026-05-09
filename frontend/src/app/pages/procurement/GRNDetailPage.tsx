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
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'

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
  item_id: number | null
  description: string
  quantity_expected: number
  quantity_cancelled: number
  quantity_received: number
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
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editQuantities, setEditQuantities] = useState<Record<number, number>>({})
  const [editReceivedDate, setEditReceivedDate] = useState('')
  const [editNotes, setEditNotes] = useState('')
  const [editReason, setEditReason] = useState('')

  const { data: grn, loading, refetch: refetchGRN } = useApi<GRNResponse>(
    resolvedId ? `/procurement/grns/${resolvedId}` : null
  )
  const { data: poData, refetch: refetchPO } = useApi<{ lines: POLine[] }>(
    grn?.po_id ? `/procurement/purchase-orders/${grn.po_id}` : null
  )
  const { execute: approveGRN, loading: approving } = useApiMutation()
  const { execute: cancelGRN, loading: cancelling } = useApiMutation()
  const { execute: rollbackGRN, loading: rollingBack } = useApiMutation()
  const { execute: updateGRN, loading: updating } = useApiMutation()
  const busy = approving || cancelling || rollingBack || updating

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

  const openEdit = () => {
    if (!grn) return
    const quantities: Record<number, number> = {}
    grn.lines.forEach((line) => {
      quantities[line.po_line_id] = (quantities[line.po_line_id] || 0) + line.quantity_received
    })
    setEditQuantities(quantities)
    setEditReceivedDate(grn.received_date)
    setEditNotes(grn.notes || '')
    setEditReason('')
    setEditDialogOpen(true)
  }

  const getOriginalGRNQuantity = (poLineId: number) =>
    grn?.lines
      .filter((line) => line.po_line_id === poLineId)
      .reduce((sum, line) => sum + line.quantity_received, 0) || 0

  const handleEditQuantityChange = (poLine: POLine, value: string) => {
    const originalInThisGRN = getOriginalGRNQuantity(poLine.id)
    const receivedOutsideThisGRN = Math.max(0, poLine.quantity_received - originalInThisGRN)
    const maxQty = Math.max(0, poLine.quantity_expected - poLine.quantity_cancelled - receivedOutsideThisGRN)
    const nextQty = Math.max(0, Math.min(Number(value) || 0, maxQty))
    setEditQuantities((prev) => ({ ...prev, [poLine.id]: nextQty }))
  }

  const handleSaveEdit = async () => {
    if (!resolvedId || !grn) return
    const lines = Object.entries(editQuantities)
      .map(([poLineId, quantity]) => ({
        po_line_id: Number(poLineId),
        quantity_received: Number(quantity) || 0,
      }))
      .filter((line) => line.quantity_received > 0)

    if (!lines.length) {
      setError('Add at least one GRN line.')
      return
    }
    if (grn.status === 'approved' && !editReason.trim()) {
      setError('Enter edit reason.')
      return
    }

    setError(null)
    const result = await updateGRN(() =>
      api.put(`/procurement/grns/${resolvedId}`, {
        received_date: editReceivedDate || null,
        notes: editNotes.trim() || null,
        reason: editReason.trim() || null,
        lines,
      })
    )
    if (result) {
      setEditDialogOpen(false)
      await refetchGRN()
      await refetchPO()
    } else {
      setError('Failed to update GRN.')
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
  const canEdit = !readOnly && isSuperAdmin(user) && grn.status !== 'cancelled'

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
          {canEdit && (
            <Button variant="outlined" disabled={busy} onClick={openEdit}>
              Edit
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

      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="lg" fullWidth>
        <DialogTitle>Edit GRN</DialogTitle>
        <DialogContent className="space-y-4">
          {grn.status === 'approved' && (
            <Alert severity="warning">
              Saving an approved GRN will update PO received quantities and create correcting stock movements.
            </Alert>
          )}
          <Input
            label="Received date"
            type="date"
            value={editReceivedDate}
            onChange={(e) => setEditReceivedDate(e.target.value)}
          />
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Description</TableHeaderCell>
                  <TableHeaderCell align="right">Expected</TableHeaderCell>
                  <TableHeaderCell align="right">PO received</TableHeaderCell>
                  <TableHeaderCell align="right">Current GRN</TableHeaderCell>
                  <TableHeaderCell align="right">Correct GRN qty</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(poData?.lines || []).map((poLine) => {
                  const currentInThisGRN = editQuantities[poLine.id] || 0
                  const originalInThisGRN = getOriginalGRNQuantity(poLine.id)
                  const receivedOutsideThisGRN = Math.max(0, poLine.quantity_received - originalInThisGRN)
                  const maxQty = Math.max(
                    0,
                    poLine.quantity_expected - poLine.quantity_cancelled - receivedOutsideThisGRN
                  )
                  return (
                    <TableRow key={poLine.id}>
                      <TableCell>{poLine.description}</TableCell>
                      <TableCell align="right">{poLine.quantity_expected}</TableCell>
                      <TableCell align="right">{poLine.quantity_received}</TableCell>
                      <TableCell align="right">
                        {originalInThisGRN}
                      </TableCell>
                      <TableCell align="right">
                        <Input
                          type="number"
                          value={currentInThisGRN === 0 ? '' : currentInThisGRN}
                          onChange={(e) => handleEditQuantityChange(poLine, e.target.value)}
                          onFocus={(e) => e.currentTarget.select()}
                          onWheel={(e) => e.currentTarget.blur()}
                          min={0}
                          max={maxQty}
                          className="w-28"
                        />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <Textarea
            label="Notes"
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
            rows={3}
          />
          {grn.status === 'approved' && (
            <Textarea
              label="Reason"
              value={editReason}
              onChange={(e) => setEditReason(e.target.value)}
              rows={3}
              required
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setEditDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveEdit}
            disabled={busy || (grn.status === 'approved' && !editReason.trim())}
          >
            {updating ? 'Saving…' : 'Save changes'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
