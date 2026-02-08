import { useMemo } from 'react'
import { SECONDARY_LIST_LIMIT } from '../../../constants/pagination'
import { useApi } from '../../../hooks/useApi'
import { formatDateTime } from '../../../utils/format'
import type { PaginatedResponse, ReservationResponse } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../../components/ui/Table'

interface ItemsToIssueTabProps {
  studentId: number
  onError: (message: string) => void
}

export const ItemsToIssueTab = ({ studentId, onError }: ItemsToIssueTabProps) => {
  const url = useMemo(
    () => `/reservations?student_id=${studentId}&limit=${SECONDARY_LIST_LIMIT}&page=1`,
    [studentId]
  )
  const { data, error } = useApi<PaginatedResponse<ReservationResponse>>(url)

  const reservations = data?.items || []

  if (error) {
    onError('Failed to load items to issue.')
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
            </TableRow>
          ))}
          {!reservations.length && (
            <TableRow>
              <td colSpan={4} className="px-4 py-8 text-center">
                <Typography color="secondary">No items to issue</Typography>
              </td>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
