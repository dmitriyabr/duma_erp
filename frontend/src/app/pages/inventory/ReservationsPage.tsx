import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormHelperText,
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
import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
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
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active')
  const [selected, setSelected] = useState<ReservationRow | null>(null)
  const [issueLines, setIssueLines] = useState<IssueLine[]>([])
  const [issueDialogOpen, setIssueDialogOpen] = useState(false)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [notes, setNotes] = useState('')
  const [issueLineErrors, setIssueLineErrors] = useState<Record<number, string>>({})

  const reservationsUrl = useMemo(() => {
    const params = { page: page + 1, limit }
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value))
    })
    return `/reservations?${searchParams.toString()}`
  }, [page, limit])

  const { data: reservationsData, loading, error, refetch } = useApi<PaginatedResponse<ReservationRow>>(reservationsUrl)
  const { data: studentsData } = useApi<PaginatedResponse<StudentOption>>('/students?page=1&limit=500')
  const { execute: issueReservation, loading: issuing, error: issueError, reset: resetIssueMutation } = useApiMutation()
  const { execute: cancelReservation, loading: cancelling, error: cancelError } = useApiMutation()

  const rows = reservationsData?.items || []
  const total = reservationsData?.total || 0
  const students = useMemo(() => {
    return (studentsData?.items || []).reduce<Record<number, string>>((acc, student) => {
      acc[student.id] = student.full_name
      return acc
    }, {})
  }, [studentsData])

  useEffect(() => {
    setPage(0)
  }, [statusFilter])

  useEffect(() => {
    if (issueError && issueDialogOpen) {
      const match = issueError.match(/reservation_item (\d+)/i)
      if (match) {
        setIssueLineErrors((prev) => ({ ...prev, [Number(match[1])]: issueError }))
        resetIssueMutation()
      }
    }
  }, [issueError, issueDialogOpen, resetIssueMutation])

  const openIssueDialog = (reservation: ReservationRow) => {
    setSelected(reservation)
    setIssueLines(
      reservation.items.map((item) => ({
        reservation_item_id: item.id,
        quantity: Math.max(0, item.quantity_required - item.quantity_issued),
      }))
    )
    setNotes('')
    setIssueLineErrors({})
    setIssueDialogOpen(true)
  }

  const submitIssue = async () => {
    if (!selected) return
    setIssueLineErrors({})
    resetIssueMutation()
    const result = await issueReservation(() =>
      api.post(`/reservations/${selected.id}/issue`, {
        items: issueLines.map((line) => ({
          reservation_item_id: line.reservation_item_id,
          quantity: line.quantity,
        })),
        notes: notes.trim() || null,
      })
    )

    if (result) {
      setIssueDialogOpen(false)
      refetch()
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
    const result = await cancelReservation(() =>
      api.post(`/reservations/${selected.id}/cancel`, {
        reason: cancelReason.trim() || null,
      })
    )

    if (result) {
      setCancelDialogOpen(false)
      refetch()
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

      {error || issueError || cancelError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || issueError || cancelError}
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
                const lineError = issueLineErrors[item.id]
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
                          if (issueLineErrors[item.id]) {
                            setIssueLineErrors((prev) => {
                              const next = { ...prev }
                              delete next[item.id]
                              return next
                            })
                          }
                        }}
                        inputProps={{ min: 0, max: remaining }}
                        error={Boolean(lineError)}
                      />
                      {lineError ? (
                        <FormHelperText error sx={{ mt: 0.5 }}>
                          {lineError}
                        </FormHelperText>
                      ) : null}
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
          <Button variant="contained" onClick={submitIssue} disabled={issuing}>
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
          <Button variant="contained" onClick={submitCancel} disabled={cancelling}>
            Cancel reservation
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
