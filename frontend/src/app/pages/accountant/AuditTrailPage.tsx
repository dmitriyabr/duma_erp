import {
  Alert,
  Box,
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
  TextField,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/format'

interface AuditEntry {
  id: number
  user_id: number | null
  user_full_name: string | null
  action: string
  entity_type: string
  entity_id: number
  entity_identifier: string | null
  comment: string | null
  created_at: string
}

export const AuditTrailPage = () => {
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [entityType, setEntityType] = useState('')
  const [actionFilter, setActionFilter] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    if (entityType) params.entity_type = entityType
    if (actionFilter) params.action = actionFilter
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/accountant/audit-trail?${sp.toString()}`
  }, [page, limit, dateFrom, dateTo, entityType, actionFilter])

  const { data, loading, error } = useApi<PaginatedResponse<AuditEntry>>(url)

  const items = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Audit Trail
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          label="Date from"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160 }}
        />
        <TextField
          label="Date to"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160 }}
        />
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Entity type</InputLabel>
          <Select
            value={entityType || '_'}
            label="Entity type"
            onChange={(e) => setEntityType(e.target.value === '_' ? '' : e.target.value)}
          >
            <MenuItem value="_">All</MenuItem>
            <MenuItem value="Payment">Payment</MenuItem>
            <MenuItem value="Invoice">Invoice</MenuItem>
            <MenuItem value="PurchaseOrder">PurchaseOrder</MenuItem>
            <MenuItem value="GoodsReceived">GoodsReceived</MenuItem>
            <MenuItem value="Student">Student</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Action</InputLabel>
          <Select
            value={actionFilter || '_'}
            label="Action"
            onChange={(e) => setActionFilter(e.target.value === '_' ? '' : e.target.value)}
          >
            <MenuItem value="_">All</MenuItem>
            <MenuItem value="CREATE">CREATE</MenuItem>
            <MenuItem value="UPDATE">UPDATE</MenuItem>
            <MenuItem value="CANCEL">CANCEL</MenuItem>
            <MenuItem value="APPROVE">APPROVE</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Date / Time</TableCell>
            <TableCell>User</TableCell>
            <TableCell>Action</TableCell>
            <TableCell>Document</TableCell>
            <TableCell>Details</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={5}>Loading…</TableCell>
            </TableRow>
          ) : (
            items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDate(row.created_at)}</TableCell>
                <TableCell>{row.user_full_name ?? '—'}</TableCell>
                <TableCell>{row.action}</TableCell>
                <TableCell>
                  {row.entity_identifier ?? `${row.entity_type} #${row.entity_id}`}
                </TableCell>
                <TableCell>{row.comment ?? '—'}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={limit}
        onRowsPerPageChange={(e) => {
          setLimit(Number(e.target.value))
          setPage(0)
        }}
        rowsPerPageOptions={[25, 50, 100]}
      />
    </Box>
  )
}
