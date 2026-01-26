import { Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'
import { useEffect, useState } from 'react'
import { api } from '../../../services/api'
import { formatDateTime } from '../../../utils/format'
import type { ApiResponse, PaginatedResponse, ReservationResponse } from '../types'

interface ItemsToIssueTabProps {
  studentId: number
  onError: (message: string) => void
}

export const ItemsToIssueTab = ({ studentId, onError }: ItemsToIssueTabProps) => {
  const [reservations, setReservations] = useState<ReservationResponse[]>([])

  const loadReservations = async () => {
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<ReservationResponse>>>(
        '/reservations',
        { params: { student_id: studentId, limit: 200, page: 1 } }
      )
      setReservations(response.data.data.items)
    } catch {
      onError('Failed to load items to issue.')
    }
  }

  useEffect(() => {
    loadReservations()
  }, [studentId])

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableCell>Reservation #</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Created</TableCell>
          <TableCell>Items</TableCell>
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
                <Typography key={item.id} variant="body2">
                  {item.item_name ?? 'Item'} · {item.quantity_issued}/{item.quantity_required}
                </Typography>
              ))}
            </TableCell>
          </TableRow>
        ))}
        {!reservations.length ? (
          <TableRow>
            <TableCell colSpan={4} align="center">
              No items to issue
            </TableCell>
          </TableRow>
        ) : null}
      </TableBody>
    </Table>
  )
}
