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
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'

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

  const { data: po, refetch: refetchPO } = useApi<POResponse>(
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

  if (!po) {
    return (
      <Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Box>
    )
  }

  const canEdit = po.status === 'draft' || po.status === 'ordered'
  const canReceive = po.status === 'ordered' || po.status === 'partially_received'

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {po.po_number}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {po.supplier_name} · {formatDate(po.order_date)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip label={po.status} color={statusColor(po.status)} />
          {canEdit ? (
            <Button variant="outlined" onClick={() => navigate(`/procurement/orders/${po.id}/edit`)}>
              Edit
            </Button>
          ) : null}
          {po.status === 'draft' ? (
            <Button variant="contained" onClick={() => setConfirmState({ open: true, action: 'submit' })}>
              Submit
            </Button>
          ) : null}
          {canReceive ? (
            <Button variant="contained" onClick={openReceive}>
              Receive
            </Button>
          ) : null}
          {po.status !== 'cancelled' && po.status !== 'closed' ? (
            <Button
              variant="contained"
              color="success"
              onClick={() => navigate(`/procurement/payments/new?po_id=${po.id}`)}
            >
              Create Payment
            </Button>
          ) : null}
          {po.status === 'ordered' || po.status === 'partially_received' ? (
            <Button variant="contained" color="warning" onClick={() => setConfirmState({ open: true, action: 'close' })}>
              Close
            </Button>
          ) : null}
          {canEdit ? (
            <Button
              variant="outlined"
              color="error"
              onClick={() => setConfirmState({ open: true, action: 'cancel', reason: '' })}
            >
              Cancel
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
            Expected total
          </Typography>
          <Typography variant="h6">{formatMoney(po.expected_total)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Received value
          </Typography>
          <Typography variant="h6">{formatMoney(po.received_value)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Paid total
          </Typography>
          <Typography variant="h6">{formatMoney(po.paid_total)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Debt amount
          </Typography>
          <Typography variant="h6" color={po.debt_amount > 0 ? 'error' : 'inherit'}>
            {formatMoney(po.debt_amount)}
          </Typography>
        </Box>
      </Box>

      {po.notes ? (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Notes
          </Typography>
          <Typography>{po.notes}</Typography>
        </Box>
      ) : null}

      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Order lines
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Description</TableCell>
              <TableCell align="right">Expected</TableCell>
              <TableCell align="right">Cancelled</TableCell>
              <TableCell align="right">Received</TableCell>
              <TableCell align="right">Remaining</TableCell>
              <TableCell align="right">Unit price</TableCell>
              <TableCell align="right">Total</TableCell>
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
      </Box>

      {grns.length > 0 ? (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Goods Received
          </Typography>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>GRN Number</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Date</TableCell>
                <TableCell align="right">Actions</TableCell>
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
        </Box>
      ) : null}

      {payments.length > 0 ? (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Payments
          </Typography>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Payment Number</TableCell>
                <TableCell>Date</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
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
        </Box>
      ) : null}

      <Dialog open={receiveDialogOpen} onClose={() => setReceiveDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Receive goods</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Received date"
            type="date"
            value={receiveDate}
            onChange={(event) => setReceiveDate(event.target.value)}
            InputLabelProps={{ shrink: true }}
          />
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Description</TableCell>
                <TableCell align="right">Expected</TableCell>
                <TableCell align="right">Received</TableCell>
                <TableCell align="right">Qty to receive</TableCell>
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
                      <TextField
                        size="small"
                        type="number"
                        value={grnLine.quantity_received === 0 ? '' : grnLine.quantity_received}
                        onChange={(event) => {
                          const qty = Number(event.target.value) || 0
                          const maxQty = poLine.quantity_expected - poLine.quantity_cancelled - poLine.quantity_received
                          setGrnLines((prev) =>
                            prev.map((line) =>
                              line.po_line_id === grnLine.po_line_id
                                ? { ...line, quantity_received: Math.min(qty, maxQty) }
                                : line
                            )
                          )
                        }}
                        onFocus={(event) => event.currentTarget.select()}
                        onWheel={(event) => event.currentTarget.blur()}
                        inputProps={{ min: 1, max: poLine.quantity_expected - poLine.quantity_cancelled - poLine.quantity_received }}
                        sx={{ width: 100 }}
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
          <TextField
            label="Notes"
            value={receiveNotes}
            onChange={(event) => setReceiveNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReceiveDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitGRN} disabled={loading}>
            Create Goods Received Note
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

      {confirmState.open && confirmState.action === 'cancel' ? (
        <Dialog open onClose={() => setConfirmState({ open: false })} fullWidth maxWidth="sm">
          <DialogTitle>Cancel purchase order</DialogTitle>
          <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
            <TextField
              label="Reason"
              value={confirmState.reason ?? ''}
              onChange={(event) => setConfirmState({ ...confirmState, reason: event.target.value })}
              multiline
              minRows={3}
              required
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmState({ open: false })}>Cancel</Button>
            <Button
              variant="contained"
              color="error"
              onClick={handleCancel}
              disabled={!confirmState.reason?.trim() || loading}
            >
              Cancel order
            </Button>
          </DialogActions>
        </Dialog>
      ) : null}
    </Box>
  )
}
