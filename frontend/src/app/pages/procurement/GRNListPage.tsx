import {
  Alert,
  Box,
  Button,
  Chip,
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
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import { formatDate } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

interface GRNRow {
  id: number
  grn_number: string
  po_id: number
  status: string
  received_date: string
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const GRNListPage = () => {
  const navigate = useNavigate()
  const [grns, setGrns] = useState<GRNRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [poIdFilter, setPoIdFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requestParams = useMemo(() => {
    const params: Record<string, string | number> = {
      page: page + 1,
      limit,
    }
    if (statusFilter !== 'all') {
      params.status = statusFilter
    }
    if (poIdFilter.trim()) {
      params.po_id = Number(poIdFilter)
    }
    if (dateFrom) {
      params.date_from = dateFrom
    }
    if (dateTo) {
      params.date_to = dateTo
    }
    return params
  }, [page, limit, statusFilter, poIdFilter, dateFrom, dateTo])

  const loadGRNs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<GRNRow>>>('/procurement/grns', {
        params: requestParams,
      })
      setGrns(response.data.data.items)
      setTotal(response.data.data.total)
    } catch {
      setError('Failed to load GRNs.')
    } finally {
      setLoading(false)
    }
  }, [requestParams])

  useEffect(() => {
    loadGRNs()
  }, [loadGRNs])

  const statusColor = (status: string) => {
    if (status === 'approved') return 'success'
    if (status === 'cancelled') return 'default'
    return 'warning'
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Goods Received
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="PO ID"
          value={poIdFilter}
          onChange={(event) => setPoIdFilter(event.target.value)}
          size="small"
          type="number"
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            {statusOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label="Date from"
          type="date"
          value={dateFrom}
          onChange={(event) => setDateFrom(event.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          label="Date to"
          type="date"
          value={dateTo}
          onChange={(event) => setDateTo(event.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>GRN Number</TableCell>
            <TableCell>PO ID</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Received date</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {grns.map((grn) => (
            <TableRow key={grn.id}>
              <TableCell>{grn.grn_number}</TableCell>
              <TableCell>{grn.po_id}</TableCell>
              <TableCell>
                <Chip size="small" label={grn.status} color={statusColor(grn.status)} />
              </TableCell>
              <TableCell>{formatDate(grn.received_date)}</TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => navigate(`/procurement/grn/${grn.id}`)}>
                  View
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!grns.length && !loading ? (
            <TableRow>
              <TableCell colSpan={5} align="center">
                No GRNs found
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
    </Box>
  )
}
