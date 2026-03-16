import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../../auth/AuthContext'
import { ReservationIssueDialog } from '../../../components/inventory/ReservationIssueDialog'
import { Button } from '../../../components/ui/Button'
import { SECONDARY_LIST_LIMIT } from '../../../constants/pagination'
import { useApi } from '../../../hooks/useApi'
import { canManageReservations } from '../../../utils/permissions'
import { formatDateTime } from '../../../utils/format'
import type { PaginatedResponse, ReservationResponse } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../../components/ui/Table'

interface ItemsToIssueTabProps {
  studentId: number
  onError: (message: string) => void
}

export const ItemsToIssueTab = ({ studentId, onError }: ItemsToIssueTabProps) => {
  const { user } = useAuth()
  const canManage = canManageReservations(user)
  const [selectedForIssue, setSelectedForIssue] = useState<ReservationResponse | null>(null)
  const [issueDialogOpen, setIssueDialogOpen] = useState(false)
  const url = useMemo(
    () => `/reservations?student_id=${studentId}&limit=${SECONDARY_LIST_LIMIT}&page=1`,
    [studentId]
  )
  const { data, error, refetch } = useApi<PaginatedResponse<ReservationResponse>>(url)

  const reservations = data?.items || []

  useEffect(() => {
    if (error) {
      onError('Failed to load items to issue.')
    }
  }, [error, onError])

  const openIssueDialog = (reservation: ReservationResponse) => {
    setSelectedForIssue(reservation)
    setIssueDialogOpen(true)
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Reservation #</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Created</TableHeaderCell>
            <TableHeaderCell>Items</TableHeaderCell>
            <TableHeaderCell align="right">Actions</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {reservations.map((reservation) => (
            <TableRow key={reservation.id}>
              <TableCell>{reservation.id}</TableCell>
              <TableCell>{reservation.status}</TableCell>
              <TableCell>{formatDateTime(reservation.created_at)}</TableCell>
              <TableCell>
                {reservation.items.map((item) => (
                  <Typography key={item.id} variant="body2" className="block">
                    {item.item_name ?? 'Item'} · {item.quantity_issued}/{item.quantity_required}
                  </Typography>
                ))}
              </TableCell>
              <TableCell align="right">
                {canManage &&
                (reservation.status === 'pending' || reservation.status === 'partial') ? (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => openIssueDialog(reservation)}
                  >
                    Issue
                  </Button>
                ) : (
                  '—'
                )}
              </TableCell>
            </TableRow>
          ))}
          {!reservations.length && (
            <TableRow>
              <td colSpan={5} className="px-4 py-8 text-center">
                <Typography color="secondary">No items to issue</Typography>
              </td>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <ReservationIssueDialog
        open={issueDialogOpen}
        reservation={selectedForIssue}
        onClose={() => setIssueDialogOpen(false)}
        onReservationChanged={refetch}
      />
    </div>
  )
}
