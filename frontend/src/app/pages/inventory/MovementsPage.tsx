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
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../services/api'
import { formatDateTime, formatMoney } from '../../utils/format'

interface MovementRow {
  id: number
  item_id: number
  item_sku?: string | null
  item_name?: string | null
  movement_type: string
  quantity: number
  unit_cost?: number | null
  quantity_before: number
  quantity_after: number
  notes?: string | null
  created_by_name?: string | null
  created_at: string
}

interface ItemOption {
  id: number
  name: string
  sku_code: string
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

const movementTypeOptions = [
  { value: 'receipt', label: 'Receipt' },
  { value: 'issue', label: 'Issue' },
  { value: 'reserve', label: 'Reserve' },
  { value: 'unreserve', label: 'Unreserve' },
  { value: 'adjustment', label: 'Adjustment' },
]

export const MovementsPage = () => {
  const [rows, setRows] = useState<MovementRow[]>([])
  const [items, setItems] = useState<ItemOption[]>([])
  const [itemFilter, setItemFilter] = useState<number | 'all'>('all')
  const [typeFilter, setTypeFilter] = useState<string | 'all'>('all')
  const [search, setSearch] = useState('')
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = async () => {
    try {
      const response = await api.get<ApiResponse<ItemOption[]>>('/items', {
        params: { include_inactive: true, item_type: 'product' },
      })
      setItems(response.data.data)
    } catch {
      setItems([])
    }
  }

  const fetchMovements = async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = {
        page: page + 1,
        limit,
      }
      if (itemFilter !== 'all') {
        params.item_id = itemFilter
      }
      if (typeFilter !== 'all') {
        params.movement_type = typeFilter
      }
      const response = await api.get<ApiResponse<PaginatedResponse<MovementRow>>>(
        '/inventory/movements',
        { params }
      )
      setRows(response.data.data.items)
      setTotal(response.data.data.total)
    } catch {
      setError('Failed to load movements.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [])

  useEffect(() => {
    fetchMovements()
  }, [page, limit, itemFilter, typeFilter])

  const filteredRows = useMemo(() => {
    if (!search.trim()) {
      return rows
    }
    const query = search.trim().toLowerCase()
    return rows.filter(
      (row) =>
        row.item_name?.toLowerCase().includes(query) ||
        row.item_sku?.toLowerCase().includes(query)
    )
  }, [rows, search])

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Movements
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Item</InputLabel>
          <Select
            value={itemFilter}
            label="Item"
            onChange={(event) => setItemFilter(event.target.value as number | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            {items.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.name} ({item.sku_code})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Type</InputLabel>
          <Select
            value={typeFilter}
            label="Type"
            onChange={(event) => setTypeFilter(event.target.value as string | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            {movementTypeOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Item</TableCell>
            <TableCell>SKU</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Qty</TableCell>
            <TableCell>Unit cost</TableCell>
            <TableCell>Before</TableCell>
            <TableCell>After</TableCell>
            <TableCell>By</TableCell>
            <TableCell>When</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filteredRows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.item_name ?? '—'}</TableCell>
              <TableCell>{row.item_sku ?? '—'}</TableCell>
              <TableCell>{row.movement_type}</TableCell>
              <TableCell>{row.quantity}</TableCell>
              <TableCell>{row.unit_cost !== null ? formatMoney(Number(row.unit_cost)) : '—'}</TableCell>
              <TableCell>{row.quantity_before}</TableCell>
              <TableCell>{row.quantity_after}</TableCell>
              <TableCell>{row.created_by_name ?? '—'}</TableCell>
              <TableCell>{formatDateTime(row.created_at)}</TableCell>
            </TableRow>
          ))}
          {!filteredRows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={9} align="center">
                No movements found
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
