import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { isAccountant } from '../../utils/permissions'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface POLine {
  id: number
  item_id: number | null
  description: string
  quantity_expected: number
  quantity_cancelled: number
  quantity_received: number
  unit_price: number
  line_total: number
}

interface POResponse {
  id: number
  po_number: string
  supplier_name: string
  supplier_contact: string | null
  purpose_id: number
  status: string
  order_date: string
  expected_delivery_date: string | null
  track_to_warehouse: boolean
  expected_total: number
  received_value: number
  paid_total: number
  debt_amount: number
  forecast_debt: number
  notes: string | null
  cancelled_reason: string | null
  lines: POLine[]
}

interface GRNRow {
  id: number
  grn_number: string
  status: string
  received_date: string
}

interface PaymentRow {
  id: number
  payment_number: string
  amount: number
  payment_date: string
  status: string
}

const statusColor = (status: string) => {
  if (status === 'received' || status === 'closed') return 'success'
  if (status === 'cancelled') return 'default'
  if (status === 'ordered' || status === 'partially_received') return 'warning'
  return 'info'
}

export const PurchaseOrderDetailPage = () => {
  const { orderId } = useParams()
  const navigate = useNavigate()
  const resolvedId = orderId ? Number(orderId) : null
  const [error, setError] = useState<string | null>(null)

  const [receiveDialogOpen, setReceiveDialogOpen] = useState(false)
  const [grnLines, setGrnLines] = useState<Array<{ po_line_id: number; quantity_received: number }>>([])
  const [receiveDate, setReceiveDate] = useState(new Date().toISOString().slice(0, 10))
  const [receiveNotes, setReceiveNotes] = useState('')

  const [confirmState, setConfirmState] = useState<{
    open: boolean
    action?: 'submit' | 'close' | 'cancel'
    reason?: string
  }>({ open: false })

  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const { data: po, loading: poLoading, refetch: refetchPO } = useApi<POResponse>(
    resolvedId ? `/procurement/purchase-orders/${resolvedId}` : null
  )
  const { data: grnsData } = useApi<PaginatedResponse<GRNRow>>(
    resolvedId ? '/procurement/grns' : null,
    { params: { po_id: resolvedId, limit: 100 } },
    [resolvedId]
  )
  const { data: paymentsData } = useApi<PaginatedResponse<PaymentRow>>(
    resolvedId ? '/procurement/payments' : null,
    { params: { po_id: resolvedId, limit: 100 } },
    [resolvedId]
  )
  const { execute: submitPO, loading: submitting } = useApiMutation()
  const { execute: closePO, loading: closing } = useApiMutation()
  const { execute: cancelPO, loading: cancelling } = useApiMutation()
  const { execute: createGRN, loading: creatingGRN } = useApiMutation()

  const grns = grnsData?.items || []
  const payments = paymentsData?.items || []
  const loading = submitting || closing || cancelling || creatingGRN

  const handleSubmit = async () => {
    if (!resolvedId) return
    setError(null)
    const result = await submitPO(() => api.post(`/procurement/purchase-orders/${resolvedId}/submit`))
    if (result) {
      await refetchPO()
      setConfirmState({ open: false })
    } else {
      setError('Failed to submit order.')
    }
  }

  const handleClose = async () => {
    if (!resolvedId) return
    setError(null)
    const result = await closePO(() => api.post(`/procurement/purchase-orders/${resolvedId}/close`))
    if (result) {
      await refetchPO()
      setConfirmState({ open: false })
    } else {
      setError('Failed to close order.')
    }
  }

  const handleCancel = async () => {
    if (!resolvedId || !confirmState.reason) return
    setError(null)
    const result = await cancelPO(() => api.post(`/procurement/purchase-orders/${resolvedId}/cancel`, {
      reason: confirmState.reason,
    }))
    if (result) {
      await refetchPO()
      setConfirmState({ open: false })
    } else {
      setError('Failed to cancel order.')
    }
  }

  const openReceive = () => {
    if (!po) return
    setGrnLines(
      po.lines
        .filter((line) => {
          const remaining = line.quantity_expected - line.quantity_cancelled - line.quantity_received
          return remaining > 0
        })
        .map((line) => ({
          po_line_id: line.id,
          quantity_received: line.quantity_expected - line.quantity_cancelled - line.quantity_received,
        }))
    )
    setReceiveDate(new Date().toISOString().slice(0, 10))
    setReceiveNotes('')
    setReceiveDialogOpen(true)
  }

  const submitGRN = async () => {
    if (!resolvedId || !grnLines.length) {
      setError('Add at least one line to receive.')
      return
    }
    setError(null)
    const result = await createGRN(() => api.post('/procurement/grns', {
      po_id: resolvedId,
      received_date: receiveDate || null,
      notes: receiveNotes.trim() || null,
      lines: grnLines.map((line) => ({
        po_line_id: line.po_line_id,
        quantity_received: line.quantity_received,
      })),
    }))
    if (result) {
      setReceiveDialogOpen(false)
      await refetchPO()
    } else {
      setError('Failed to create GRN.')
    }
  }

  if (poLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!po) {
    return (
      <div>
        {error && <Alert severity="error">{error}</Alert>}
      </div>
    )
  }

  const canEdit = !readOnly && (po.status === 'draft' || po.status === 'ordered')
  const canReceive = !readOnly && (po.status === 'ordered' || po.status === 'partially_received')

  return (
    <div>
      <div className="flex justify-between items-start mb-4 flex-wrap gap-4">
        <div>
          <Typography variant="h4">
            {po.po_number}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {po.supplier_name} · {formatDate(po.order_date)}
          </Typography>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <Chip label={po.status} color={statusColor(po.status)} />
          {canEdit && (
            <Button variant="outlined" onClick={() => navigate(`/procurement/orders/${po.id}/edit`)}>
              Edit
            </Button>
          )}
          {!readOnly && po.status === 'draft' && (
            <Button variant="contained" onClick={() => setConfirmState({ open: true, action: 'submit' })}>
              Submit
            </Button>
          )}
          {canReceive && (
            <Button variant="contained" onClick={openReceive}>
              Receive
            </Button>
          )}
          {!readOnly && po.status !== 'cancelled' && po.status !== 'closed' && (
            <Button
              variant="contained"
              color="success"
              onClick={() => navigate(`/procurement/payments/new?po_id=${po.id}`)}
            >
              Create Payment
            </Button>
          )}
          {!readOnly && (po.status === 'ordered' || po.status === 'partially_received') && (
            <Button variant="contained" color="warning" onClick={() => setConfirmState({ open: true, action: 'close' })}>
              Close
            </Button>
          )}
          {canEdit && (
            <Button
              variant="outlined"
              color="error"
              onClick={() => setConfirmState({ open: true, action: 'cancel', reason: '' })}
            >
              Cancel
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Expected total
          </Typography>
          <Typography variant="h6">{formatMoney(po.expected_total)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Received value
          </Typography>
          <Typography variant="h6">{formatMoney(po.received_value)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Paid total
          </Typography>
          <Typography variant="h6">{formatMoney(po.paid_total)}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Debt amount
          </Typography>
          <Typography variant="h6" className={po.debt_amount > 0 ? 'text-error' : ''}>
            {formatMoney(po.debt_amount)}
          </Typography>
        </div>
      </div>

      {po.notes && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Notes
          </Typography>
          <Typography>{po.notes}</Typography>
        </div>
      )}

      <div className="mb-6">
        <Typography variant="h6" className="mb-4">
          Order lines
        </Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Description</TableHeaderCell>
                <TableHeaderCell align="right">Expected</TableHeaderCell>
                <TableHeaderCell align="right">Cancelled</TableHeaderCell>
                <TableHeaderCell align="right">Received</TableHeaderCell>
                <TableHeaderCell align="right">Remaining</TableHeaderCell>
                <TableHeaderCell align="right">Unit price</TableHeaderCell>
                <TableHeaderCell align="right">Total</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {po.lines.map((line) => {
                const remaining = line.quantity_expected - line.quantity_cancelled - line.quantity_received
                return (
                  <TableRow key={line.id}>
                    <TableCell>{line.description}</TableCell>
                    <TableCell align="right">{line.quantity_expected}</TableCell>
                    <TableCell align="right">{line.quantity_cancelled}</TableCell>
                    <TableCell align="right">{line.quantity_received}</TableCell>
                    <TableCell align="right">{remaining}</TableCell>
                    <TableCell align="right">{formatMoney(line.unit_price)}</TableCell>
                    <TableCell align="right">{formatMoney(line.line_total)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </div>

      {grns.length > 0 && (
        <div className="mb-6">
          <Typography variant="h6" className="mb-4">
            Goods Received
          </Typography>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>GRN Number</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Date</TableHeaderCell>
                  <TableHeaderCell align="right">Actions</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {grns.map((grn) => (
                  <TableRow key={grn.id}>
                    <TableCell>{grn.grn_number}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={grn.status}
                        color={grn.status === 'approved' ? 'success' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>{formatDate(grn.received_date)}</TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => navigate(`/procurement/grn/${grn.id}`)}>
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {payments.length > 0 && (
        <div>
          <Typography variant="h6" className="mb-4">
            Payments
          </Typography>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Payment Number</TableHeaderCell>
                  <TableHeaderCell>Date</TableHeaderCell>
                  <TableHeaderCell align="right">Amount</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell align="right">Actions</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {payments.map((payment) => (
                  <TableRow key={payment.id}>
                    <TableCell>{payment.payment_number}</TableCell>
                    <TableCell>{formatDate(payment.payment_date)}</TableCell>
                    <TableCell align="right">{formatMoney(payment.amount)}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={payment.status}
                        color={payment.status === 'posted' ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => navigate(`/procurement/payments/${payment.id}`)}>
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      <Dialog open={receiveDialogOpen} onClose={() => setReceiveDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setReceiveDialogOpen(false)} />
        <DialogTitle>Receive goods</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Input
              label="Received date"
              type="date"
              value={receiveDate}
              onChange={(e) => setReceiveDate(e.target.value)}
            />
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Description</TableHeaderCell>
                    <TableHeaderCell align="right">Expected</TableHeaderCell>
                    <TableHeaderCell align="right">Received</TableHeaderCell>
                    <TableHeaderCell align="right">Qty to receive</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {grnLines.map((grnLine) => {
                    const poLine = po.lines.find((l) => l.id === grnLine.po_line_id)
                    if (!poLine) return null
                    return (
                      <TableRow key={grnLine.po_line_id}>
                        <TableCell>{poLine.description}</TableCell>
                        <TableCell align="right">{poLine.quantity_expected}</TableCell>
                        <TableCell align="right">{poLine.quantity_received}</TableCell>
                        <TableCell align="right">
                          <Input
                            type="number"
                            value={grnLine.quantity_received === 0 ? '' : grnLine.quantity_received}
                            onChange={(e) => {
                              const qty = Number(e.target.value) || 0
                              const maxQty = poLine.quantity_expected - poLine.quantity_cancelled - poLine.quantity_received
                              setGrnLines((prev) =>
                                prev.map((line) =>
                                  line.po_line_id === grnLine.po_line_id
                                    ? { ...line, quantity_received: Math.min(qty, maxQty) }
                                    : line
                                )
                              )
                            }}
                            onFocus={(e) => e.currentTarget.select()}
                            onWheel={(e) => e.currentTarget.blur()}
                            min={1}
                            max={poLine.quantity_expected - poLine.quantity_cancelled - poLine.quantity_received}
                            className="w-24"
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
              value={receiveNotes}
              onChange={(e) => setReceiveNotes(e.target.value)}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setReceiveDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitGRN} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Create Goods Received Note'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmState.open && confirmState.action === 'submit'}
        title="Submit purchase order"
        description="Are you sure you want to submit this order to the supplier?"
        confirmLabel="Submit"
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={handleSubmit}
      />

      <ConfirmDialog
        open={confirmState.open && confirmState.action === 'close'}
        title="Close purchase order"
        description="Are you sure you want to close this order? Remaining quantities will be cancelled."
        confirmLabel="Close"
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={handleClose}
      />

      {confirmState.open && confirmState.action === 'cancel' && (
        <Dialog open onClose={() => setConfirmState({ open: false })} maxWidth="sm">
          <DialogCloseButton onClose={() => setConfirmState({ open: false })} />
          <DialogTitle>Cancel purchase order</DialogTitle>
          <DialogContent>
            <div className="mt-4">
              <Textarea
                label="Reason"
                value={confirmState.reason ?? ''}
                onChange={(e) => setConfirmState({ ...confirmState, reason: e.target.value })}
                rows={3}
                required
              />
            </div>
          </DialogContent>
          <DialogActions>
            <Button variant="outlined" onClick={() => setConfirmState({ open: false })}>
              Cancel
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={handleCancel}
              disabled={!confirmState.reason?.trim() || loading}
            >
              {loading ? <Spinner size="small" /> : 'Cancel order'}
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </div>
  )
}
