import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'
import { canManageReservations } from '../../utils/permissions'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { ToggleButton, ToggleButtonGroup } from '../../components/ui/ToggleButton'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface ReservationItem {
  id: number
  item_name?: string | null
  item_sku?: string | null
  quantity_required: number
  quantity_issued: number
}

interface ReservationRow {
  id: number
  student_id: number
  student_name?: string | null
  invoice_id: number
  status: string
  created_at: string
  items: ReservationItem[]
}

interface IssueLine {
  reservation_item_id: number
  quantity: number
}

export const ReservationsPage = () => {
  const { user } = useAuth()
  const canManage = canManageReservations(user)
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
  const { execute: issueReservation, loading: issuing, error: issueError, reset: resetIssueMutation } = useApiMutation()
  const { execute: cancelReservation, loading: cancelling, error: cancelError } = useApiMutation()

  const rows = reservationsData?.items || []
  const total = reservationsData?.total || 0

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

  const filteredRows = rows.filter((row) => {
    if (statusFilter !== 'active') {
      return true
    }
    return row.status === 'pending' || row.status === 'partial'
  })

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Reservations
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap">
        <ToggleButtonGroup
          size="small"
          value={statusFilter}
          exclusive
          onChange={(_, value) => {
            if (value && (value === 'all' || value === 'active')) {
              setStatusFilter(value)
            }
          }}
        >
          <ToggleButton value="active">Active</ToggleButton>
          <ToggleButton value="all">All</ToggleButton>
        </ToggleButtonGroup>
      </div>

      {(error || issueError || cancelError) && (
        <Alert severity="error" className="mb-4">
          {error || issueError || cancelError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Reservation #</TableHeaderCell>
              <TableHeaderCell>Student</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Items</TableHeaderCell>
              <TableHeaderCell>Created</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
              {filteredRows.map((row) => (
                <TableRow key={row.id}>
                 <TableCell>{row.id}</TableCell>
                 <TableCell>{row.student_name ?? `Student #${row.student_id}`}</TableCell>
                 <TableCell>{row.status}</TableCell>
                 <TableCell>{row.items.length}</TableCell>
                 <TableCell>{formatDateTime(row.created_at)}</TableCell>
                 <TableCell align="right">
                  {canManage ? (
                    <>
                      {row.status === 'pending' || row.status === 'partial' ? (
                        <div className="flex gap-2 justify-end">
                          <Button size="small" variant="outlined" onClick={() => openIssueDialog(row)}>
                            Issue
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={() => openCancelDialog(row)}
                          >
                            Cancel
                          </Button>
                        </div>
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
            {loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Spinner size="small" />
                </td>
              </TableRow>
            )}
            {!filteredRows.length && !loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Typography color="secondary">No reservations found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <TablePagination
        count={statusFilter === 'active' ? filteredRows.length : total}
        page={page}
        onPageChange={(nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(newLimit) => {
          setLimit(newLimit)
          setPage(0)
        }}
      />

      <Dialog open={issueDialogOpen} onClose={() => setIssueDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setIssueDialogOpen(false)} />
        <DialogTitle>Issue reservation items</DialogTitle>
        <DialogContent>
          <div className="space-y-4">
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Item</TableHeaderCell>
                    <TableHeaderCell>Required</TableHeaderCell>
                    <TableHeaderCell>Issued</TableHeaderCell>
                    <TableHeaderCell>To issue</TableHeaderCell>
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
                          <div>
                            <Input
                              type="number"
                              value={line?.quantity ?? remaining}
                              onChange={(e) => {
                                const value = Number(e.target.value) || 0
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
                              min={0}
                              max={remaining}
                              error={lineError || undefined}
                              className="w-24"
                            />
                            {lineError && (
                              <Typography variant="caption" color="error" className="mt-1 block">
                                {lineError}
                              </Typography>
                            )}
                            </div>
                         </TableCell>
                        </TableRow>
                      )
                  })}
                </TableBody>
              </Table>
            </div>
            <Textarea
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setIssueDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitIssue} disabled={issuing}>
            {issuing ? <Spinner size="small" /> : 'Issue'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setCancelDialogOpen(false)} />
        <DialogTitle>Cancel reservation</DialogTitle>
        <DialogContent>
          <Textarea
            label="Reason"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            rows={3}
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCancelDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitCancel} disabled={cancelling}>
            {cancelling ? <Spinner size="small" /> : 'Cancel reservation'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
