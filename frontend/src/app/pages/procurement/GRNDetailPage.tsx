import {
  Alert,
  Box,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api } from '../../services/api'
import { formatDate } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

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
  const [grn, setGrn] = useState<GRNResponse | null>(null)
  const [poLines, setPoLines] = useState<Map<number, POLine>>(new Map())
  const [_loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmState, setConfirmState] = useState<{ open: boolean; action?: 'approve' | 'cancel' }>({
    open: false,
  })

  const loadGRN = useCallback(async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<GRNResponse>>(`/procurement/grns/${resolvedId}`)
      const grnData = response.data.data
      setGrn(grnData)

      const poResponse = await api.get<ApiResponse<{ lines: POLine[] }>>(
        `/procurement/purchase-orders/${grnData.po_id}`
      )
      const linesMap = new Map(poResponse.data.data.lines.map((line) => [line.id, line]))
      setPoLines(linesMap)
    } catch {
      setError('Failed to load GRN.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  useEffect(() => {
    loadGRN()
  }, [loadGRN])

  const handleApprove = async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      await api.post(`/procurement/grns/${resolvedId}/approve`)
      await loadGRN()
      setConfirmState({ open: false })
    } catch {
      setError('Failed to approve GRN.')
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      await api.post(`/procurement/grns/${resolvedId}/cancel`)
      await loadGRN()
      setConfirmState({ open: false })
    } catch {
      setError('Failed to cancel GRN.')
    } finally {
      setLoading(false)
    }
  }

  if (!grn) {
    return (
      <Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Box>
    )
  }

  const canApprove = grn.status === 'draft' && user?.role === 'SuperAdmin'
  const canCancel = grn.status === 'draft'

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
            <Button variant="contained" onClick={() => setConfirmState({ open: true, action: 'approve' })}>
              Approve
            </Button>
          ) : null}
          {canCancel ? (
            <Button variant="outlined" color="error" onClick={() => setConfirmState({ open: true, action: 'cancel' })}>
              Cancel
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
    </Box>
  )
}
