import { useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'
import { canManageReservations } from '../../utils/permissions'
import { ReservationIssueDialog } from '../../components/inventory/ReservationIssueDialog'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/Textarea'
import { ToggleButton, ToggleButtonGroup } from '../../components/ui/ToggleButton'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface ReservationItem {
  id: number
  item_id: number
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
  invoice_line_id: number
  status: string
  created_at: string
  items: ReservationItem[]
}

export const ReservationsPage = () => {
  const { user } = useAuth()
  const canManage = canManageReservations(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active')
  const [selectedForIssue, setSelectedForIssue] = useState<ReservationRow | null>(null)
  const [issueDialogOpen, setIssueDialogOpen] = useState(false)
  const [selectedForCancel, setSelectedForCancel] = useState<ReservationRow | null>(null)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')

  const reservationsUrl = useMemo(() => {
    const params = { page: page + 1, limit }
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value))
    })
    return `/reservations?${searchParams.toString()}`
  }, [page, limit])

  const { data: reservationsData, loading, error, refetch } = useApi<PaginatedResponse<ReservationRow>>(reservationsUrl)
  const { execute: cancelReservation, loading: cancelling, error: cancelError } = useApiMutation()

  const rows = reservationsData?.items || []
  const total = reservationsData?.total || 0

  const openIssueDialog = (reservation: ReservationRow) => {
    setSelectedForIssue(reservation)
    setIssueDialogOpen(true)
  }

  const openCancelDialog = (reservation: ReservationRow) => {
    setSelectedForCancel(reservation)
    setCancelReason('')
    setCancelDialogOpen(true)
  }

  const submitCancel = async () => {
    if (!selectedForCancel) {
      return
    }
    const result = await cancelReservation(() =>
      api.post(`/reservations/${selectedForCancel.id}/cancel`, {
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
              setPage(0)
              setStatusFilter(value)
            }
          }}
        >
          <ToggleButton value="active">Active</ToggleButton>
          <ToggleButton value="all">All</ToggleButton>
        </ToggleButtonGroup>
      </div>

      {(error || cancelError) && (
        <Alert severity="error" className="mb-4">
          {error || cancelError}
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

      <ReservationIssueDialog
        open={issueDialogOpen}
        reservation={selectedForIssue}
        onClose={() => setIssueDialogOpen(false)}
        onReservationChanged={refetch}
      />

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
