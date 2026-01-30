import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'

interface IssuanceItem {
  id: number
  item_name?: string | null
  item_sku?: string | null
  quantity: number
}

interface IssuanceRow {
  id: number
  issuance_number: string
  issuance_type: string
  recipient_type: string
  recipient_name: string
  status: string
  issued_at: string
  notes?: string | null
  items: IssuanceItem[]
}


export const IssuancesPage = () => {
  const { user } = useAuth()
  const canCancel = user?.role === 'SuperAdmin'
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [typeFilter, setTypeFilter] = useState<string | 'all'>('all')
  const [recipientFilter, setRecipientFilter] = useState<string | 'all'>('all')
  const [selected, setSelected] = useState<IssuanceRow | null>(null)

  const params = useMemo(() => {
    const p: Record<string, string | number> = { page: page + 1, limit }
    if (typeFilter !== 'all') {
      p.issuance_type = typeFilter
    }
    if (recipientFilter !== 'all') {
      p.recipient_type = recipientFilter
    }
    return p
  }, [page, limit, typeFilter, recipientFilter])

  const url = useMemo(() => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value))
    })
    return `/inventory/issuances?${searchParams.toString()}`
  }, [params])

  const { data, loading, error, refetch } = useApi<PaginatedResponse<IssuanceRow>>(url)
  const { execute: cancelIssuanceApi, loading: _cancelling, error: cancelError } = useApiMutation()

  const rows = data?.items || []
  const total = data?.total || 0

  const cancelIssuance = async (issuanceId: number) => {
    const result = await cancelIssuanceApi(() => api.post(`/inventory/issuances/${issuanceId}/cancel`))
    if (result) {
      setSelected(null)
      refetch()
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Issuances
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Type</InputLabel>
          <Select
            value={typeFilter}
            label="Type"
            onChange={(event) => setTypeFilter(event.target.value as string | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="internal">Internal</MenuItem>
            <MenuItem value="reservation">Reservation</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Recipient</InputLabel>
          <Select
            value={recipientFilter}
            label="Recipient"
            onChange={(event) => setRecipientFilter(event.target.value as string | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="employee">Employee</MenuItem>
            <MenuItem value="department">Department</MenuItem>
            <MenuItem value="student">Student</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {error || cancelError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || cancelError}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Issuance #</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Recipient</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Issued at</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.issuance_number}</TableCell>
              <TableCell>{row.issuance_type}</TableCell>
              <TableCell>{row.recipient_name}</TableCell>
              <TableCell>{row.status}</TableCell>
              <TableCell>{formatDateTime(row.issued_at)}</TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => setSelected(row)}>
                  View
                </Button>
                {canCancel ? (
                  <Button size="small" onClick={() => cancelIssuance(row.id)}>
                    Cancel
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
          {loading ? (
            <TableRow>
              <TableCell colSpan={6} align="center">
                Loading…
              </TableCell>
            </TableRow>
          ) : null}
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={6} align="center">
                No issuances found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
      />

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="md">
        <DialogTitle>Issuance details</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2 }}>
          <Typography variant="body2">Issuance #: {selected?.issuance_number}</Typography>
          <Typography variant="body2">Recipient: {selected?.recipient_name}</Typography>
          <Typography variant="body2">Status: {selected?.status}</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Item</TableCell>
                <TableCell>SKU</TableCell>
                <TableCell>Qty</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {selected?.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.item_name ?? '—'}</TableCell>
                  <TableCell>{item.item_sku ?? '—'}</TableCell>
                  <TableCell>{item.quantity}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelected(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
