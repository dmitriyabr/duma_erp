import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { formatDateTime } from '../../utils/format'

interface ReservationItem {
  id: number
  item_name?: string | null
  item_sku?: string | null
  quantity_required: number
  quantity_reserved: number
  quantity_issued: number
}

interface ReservationRow {
  id: number
  student_id: number
  invoice_id: number
  status: string
  created_at: string
  items: ReservationItem[]
}

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

interface StudentOption {
  id: number
  full_name: string
}

interface IssueLine {
  reservation_item_id: number
  quantity: number
}

export const ReservationsPage = () => {
  const { user } = useAuth()
  const canManage = user?.role === 'SuperAdmin' || user?.role === 'Admin'
  const [rows, setRows] = useState<ReservationRow[]>([])
  const [students, setStudents] = useState<Record<number, string>>({})
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ReservationRow | null>(null)
  const [issueLines, setIssueLines] = useState<IssueLine[]>([])
  const [issueDialogOpen, setIssueDialogOpen] = useState(false)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [notes, setNotes] = useState('')

  const fetchReservations = async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = { page: page + 1, limit }
      // active uses client-side filtering (pending + partial)
      const response = await api.get<ApiResponse<PaginatedResponse<ReservationRow>>>(
        '/reservations',
        { params }
      )
      setRows(response.data.data.items)
      setTotal(response.data.data.total)
    } catch {
      setError('Failed to load reservations.')
    } finally {
      setLoading(false)
    }
  }

  const fetchStudents = async () => {
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<StudentOption>>>('/students', {
        params: { page: 1, limit: 500 },
      })
      const map = response.data.data.items.reduce<Record<number, string>>((acc, student) => {
        acc[student.id] = student.full_name
        return acc
      }, {})
      setStudents(map)
    } catch {
      setStudents({})
    }
  }

  useEffect(() => {
    fetchReservations()
  }, [page, limit, statusFilter])

  useEffect(() => {
    setPage(0)
  }, [statusFilter])

  useEffect(() => {
    fetchStudents()
  }, [])

  const openIssueDialog = (reservation: ReservationRow) => {
    setSelected(reservation)
    setIssueLines(
      reservation.items.map((item) => ({
        reservation_item_id: item.id,
        quantity: Math.max(0, item.quantity_required - item.quantity_issued),
      }))
    )
    setNotes('')
    setIssueDialogOpen(true)
  }

  const submitIssue = async () => {
    if (!selected) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.post(`/reservations/${selected.id}/issue`, {
        items: issueLines.map((line) => ({
          reservation_item_id: line.reservation_item_id,
          quantity: line.quantity,
        })),
        notes: notes.trim() || null,
      })
      setIssueDialogOpen(false)
      await fetchReservations()
    } catch {
      setError('Failed to issue reservation items.')
    } finally {
      setLoading(false)
    }
  }

  const openCancelDialog = (reservation: ReservationRow) => {
    setSelected(reservation)
    setCancelReason('')
    setCancelDialogOpen(true)
  }

  const submitCancel = async () => {
    if (!selected) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.post(`/reservations/${selected.id}/cancel`, {
        reason: cancelReason.trim() || null,
      })
      setCancelDialogOpen(false)
      await fetchReservations()
    } catch {
      setError('Failed to cancel reservation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Reservations
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <ToggleButtonGroup
          size="small"
          value={statusFilter}
          exclusive
          onChange={(_, value) => value && setStatusFilter(value)}
        >
          <ToggleButton value="active">Active</ToggleButton>
          <ToggleButton value="all">All</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Reservation #</TableCell>
            <TableCell>Student</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Items</TableCell>
            <TableCell>Created</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows
            .filter((row) => {
              if (statusFilter !== 'active') {
                return true
              }
              return row.status === 'pending' || row.status === 'partial'
            })
            .map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.id}</TableCell>
              <TableCell>{students[row.student_id] ?? `Student #${row.student_id}`}</TableCell>
              <TableCell>{row.status}</TableCell>
              <TableCell>{row.items.length}</TableCell>
              <TableCell>{formatDateTime(row.created_at)}</TableCell>
              <TableCell align="right">
                {canManage ? (
                  <>
                    {row.status === 'pending' || row.status === 'partial' ? (
                      <>
                        <Button size="small" onClick={() => openIssueDialog(row)}>
                          Issue
                        </Button>
                        <Button size="small" onClick={() => openCancelDialog(row)}>
                          Cancel
                        </Button>
                      </>
                    ) : (
                      '—'
                    )}
                  </>
                ) : (
                  '—'
                )}
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={5} align="center">
                No reservations found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <TablePagination
        component="div"
        count={statusFilter === 'active' ? rows.filter((row) => row.status === 'pending' || row.status === 'partial').length : total}
        page={page}
        onPageChange={(_, nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
      />

      <Dialog open={issueDialogOpen} onClose={() => setIssueDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Issue reservation items</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Item</TableCell>
                <TableCell>Required</TableCell>
                <TableCell>Issued</TableCell>
                <TableCell>To issue</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {selected?.items.map((item) => {
                const line = issueLines.find((entry) => entry.reservation_item_id === item.id)
                const remaining = Math.max(0, item.quantity_required - item.quantity_issued)
                return (
                  <TableRow key={item.id}>
                    <TableCell>{item.item_name ?? '—'}</TableCell>
                    <TableCell>{item.quantity_required}</TableCell>
                    <TableCell>{item.quantity_issued}</TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        type="number"
                        value={line?.quantity ?? remaining}
                        onChange={(event) => {
                          const value = Number(event.target.value) || 0
                          setIssueLines((prev) =>
                            prev.map((entry) =>
                              entry.reservation_item_id === item.id
                                ? { ...entry, quantity: value }
                                : entry
                            )
                          )
                        }}
                        inputProps={{ min: 0, max: remaining }}
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
          <TextField
            label="Notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIssueDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitIssue} disabled={loading}>
            Issue
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Cancel reservation</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Reason"
            value={cancelReason}
            onChange={(event) => setCancelReason(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCancelDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitCancel} disabled={loading}>
            Cancel reservation
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
