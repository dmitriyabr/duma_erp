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
import { useApi } from '../../hooks/useApi'
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
  const [itemFilter, setItemFilter] = useState<number | 'all'>('all')
  const [typeFilter, setTypeFilter] = useState<string | 'all'>('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)

  const { data: items } = useApi<ItemOption[]>('/items?include_inactive=true&item_type=product')

  const movementsUrl = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (itemFilter !== 'all') {
      params.item_id = itemFilter
    }
    if (typeFilter !== 'all') {
      params.movement_type = typeFilter
    }
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value))
    })
    return `/inventory/movements?${searchParams.toString()}`
  }, [page, limit, itemFilter, typeFilter])

  const { data: movementsData, loading, error } = useApi<PaginatedResponse<MovementRow>>(movementsUrl)

  const rows = movementsData?.items || []
  const total = movementsData?.total || 0

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
            {(items || []).map((item) => (
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
