import { useMemo, useState } from 'react'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDateTime, formatMoney } from '../../utils/format'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

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
    <div>
      <Typography variant="h4" className="mb-4">
        Movements
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Item name or SKU"
          />
        </div>
        <div className="min-w-[220px]">
          <Select
            label="Item"
            value={itemFilter}
            onChange={(e) => setItemFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          >
            <option value="all">All</option>
            {(items || []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.sku_code})
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All</option>
            {movementTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Item</TableHeaderCell>
              <TableHeaderCell>SKU</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Qty</TableHeaderCell>
              <TableHeaderCell>Unit cost</TableHeaderCell>
              <TableHeaderCell>Before</TableHeaderCell>
              <TableHeaderCell>After</TableHeaderCell>
              <TableHeaderCell>By</TableHeaderCell>
              <TableHeaderCell>When</TableHeaderCell>
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
            {loading && (
              <TableRow>
                <td colSpan={9} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!filteredRows.length && !loading && (
              <TableRow>
                <td colSpan={9} className="px-4 py-8 text-center">
                  <Typography color="secondary">No movements found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(newLimit) => {
            setLimit(newLimit)
            setPage(0)
          }}
        />
      </div>
    </div>
  )
}
