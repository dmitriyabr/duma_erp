import { useMemo, useState } from 'react'
import { useApi } from '../../hooks/useApi'
import type { PaginatedResponse } from '../../types/api'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Switch } from '../../components/ui/Switch'
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  TablePagination,
} from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'
import { Chip } from '../../components/ui/Chip'

interface RestockRow {
  item_id: number
  item_sku?: string | null
  item_name?: string | null
  category_id?: number | null
  category_name?: string | null
  quantity_on_hand: number
  quantity_owed: number
  quantity_inbound: number
  quantity_net: number
  quantity_to_order: number
}

interface CategoryOption {
  id: number
  name: string
}

const EMPTY_ROWS: RestockRow[] = []

export const RestockPage = () => {
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [onlyDemand, setOnlyDemand] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 350)
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')

  const { data: categories } = useApi<CategoryOption[]>('/items/categories')

  const params = useMemo(() => {
    const p: Record<string, string | number | boolean> = {
      page: page + 1,
      limit,
      only_demand: onlyDemand,
    }
    if (debouncedSearch.trim()) p.search = debouncedSearch.trim()
    if (categoryFilter !== 'all') p.category_id = categoryFilter
    return p
  }, [page, limit, onlyDemand, debouncedSearch, categoryFilter])

  const { data, loading, error } = useApi<PaginatedResponse<RestockRow>>(
    '/inventory/restock',
    { params },
    [params]
  )

  const rows = data?.items ?? EMPTY_ROWS
  const total = data?.total ?? 0

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">Restock</Typography>
        <Typography variant="body2" color="secondary">
          Sellable items only (active product kit components)
        </Typography>
      </div>

      <div className="flex flex-wrap items-end gap-4 mb-4">
        <Input
          containerClassName="w-[240px] min-w-[200px]"
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="SKU or name…"
        />
        <Select
          containerClassName="w-[260px] min-w-[200px]"
          label="Category"
          value={categoryFilter === 'all' ? '' : String(categoryFilter)}
          onChange={(e) =>
            setCategoryFilter(e.target.value === '' ? 'all' : Number(e.target.value))
          }
        >
          <option value="">All</option>
          {(categories || []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Switch
          containerClassName="self-end whitespace-nowrap pb-1"
          checked={onlyDemand}
          onChange={(e) => {
            setOnlyDemand(e.target.checked)
            setPage(0)
          }}
          label="Only items with demand"
        />
      </div>

      {error ? (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      ) : null}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Item</TableHeaderCell>
              <TableHeaderCell align="right">On hand</TableHeaderCell>
              <TableHeaderCell align="right">Owed</TableHeaderCell>
              <TableHeaderCell align="right">Inbound</TableHeaderCell>
              <TableHeaderCell align="right">Net</TableHeaderCell>
              <TableHeaderCell align="right">To order</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.item_id}>
                <TableCell>
                  <div className="grid">
                    <Typography className="font-medium">{r.item_name ?? '—'}</Typography>
                    <Typography variant="caption" color="secondary">
                      {r.item_sku ?? '—'}
                      {r.category_name ? ` • ${r.category_name}` : ''}
                    </Typography>
                  </div>
                </TableCell>
                <TableCell align="right">{r.quantity_on_hand}</TableCell>
                <TableCell align="right">{r.quantity_owed}</TableCell>
                <TableCell align="right">{r.quantity_inbound}</TableCell>
                <TableCell align="right">{r.quantity_net}</TableCell>
                <TableCell
                  align="right"
                  className={r.quantity_to_order > 0 ? 'font-semibold text-warning' : ''}
                >
                  {r.quantity_to_order}
                </TableCell>
                <TableCell>
                  {r.quantity_to_order > 0 ? (
                    <Chip size="small" color="warning" label="Order" />
                  ) : r.quantity_owed > 0 ? (
                    <Chip size="small" color="info" label="Covered" />
                  ) : (
                    <Chip size="small" color="success" label="OK" />
                  )}
                </TableCell>
              </TableRow>
            ))}
            {loading ? (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Spinner size="small" />
                </td>
              </TableRow>
            ) : null}
            {!rows.length && !loading ? (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Typography color="secondary">No items found</Typography>
                </td>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <TablePagination
        count={total}
        page={page}
        onPageChange={(nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(newLimit) => {
          setLimit(newLimit)
          setPage(0)
        }}
      />
    </div>
  )
}

