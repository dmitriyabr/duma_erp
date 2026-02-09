import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { formatMoney } from '../../utils/format'
import { canCreateItem, canManageStock } from '../../utils/permissions'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Switch } from '../../components/ui/Switch'
import { Textarea } from '../../components/ui/Textarea'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface StockRow {
  id: number
  item_id: number
  item_sku?: string | null
  item_name?: string | null
  quantity_on_hand: number
  quantity_reserved: number
  quantity_available: number
  average_cost: number
}

const EMPTY_STOCK_ROWS: StockRow[] = []

interface CategoryOption {
  id: number
  name: string
}

interface ItemOption {
  id: number
  category_id: number
  name: string
  sku_code: string
}

type WriteOffReason = 'damage' | 'expired' | 'lost' | 'other'

const lowStockThreshold = 5

const buildSkuPrefix = (categoryName: string) => {
  const cleaned = categoryName.toUpperCase().replace(/[^A-Z0-9]/g, '')
  return cleaned ? cleaned.slice(0, 6) : 'CAT'
}

const nextSkuForCategory = (categoryName: string, items: ItemOption[]) => {
  const prefix = buildSkuPrefix(categoryName)
  const regex = new RegExp(`^${prefix}-(\\d{6})$`)
  const max = items.reduce((current, item) => {
    const match = regex.exec(item.sku_code)
    if (!match) {
      return current
    }
    const nextNumber = Number(match[1])
    return Number.isNaN(nextNumber) ? current : Math.max(current, nextNumber)
  }, 0)
  return `${prefix}-${String(max + 1).padStart(6, '0')}`
}

export const StockPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = canManageStock(user)
  const allowCreateItem = canCreateItem(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [includeZero, setIncludeZero] = useState(false)
  const [lowStockOnly, setLowStockOnly] = useState(false)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 400)
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')
  const [error, setError] = useState<string | null>(null)
  const [receiveDialog, setReceiveDialog] = useState<StockRow | null>(null)
  const [receiveOpen, setReceiveOpen] = useState(false)
  const [receiveItemId, setReceiveItemId] = useState<number | ''>('')
  const [createItemOpen, setCreateItemOpen] = useState(false)
  const [newItemCategoryId, setNewItemCategoryId] = useState<number | ''>('')
  const [newItemSku, setNewItemSku] = useState('')
  const [newItemName, setNewItemName] = useState('')
  const [newItemQuantity, setNewItemQuantity] = useState('')
  const [newItemUnitCost, setNewItemUnitCost] = useState('')
  const [writeoffDialog, setWriteoffDialog] = useState<StockRow | null>(null)
  const [quantity, setQuantity] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [notes, setNotes] = useState('')
  const [reasonCategory, setReasonCategory] = useState<WriteOffReason>('damage')
  const [reasonDetail, setReasonDetail] = useState('')

  const { data: categories } = useApi<CategoryOption[]>('/items/categories')
  const { data: items, refetch: refetchItems } = useApi<ItemOption[]>('/items', {
    params: { include_inactive: true, item_type: 'product' },
  })

  const stockParams = useMemo(() => {
    const params: Record<string, string | number | boolean> = {
      page: page + 1,
      limit: lowStockOnly || debouncedSearch.trim() ? 500 : limit,
      include_zero: includeZero,
    }
    if (categoryFilter !== 'all') {
      params.category_id = categoryFilter
    }
    return params
  }, [page, limit, includeZero, categoryFilter, lowStockOnly, debouncedSearch])

  const {
    data: stockData,
    loading,
    error: stockError,
    refetch: refetchStock,
  } = useApi<PaginatedResponse<StockRow>>('/inventory/stock', { params: stockParams }, [stockParams])

  const rows = stockData?.items ?? EMPTY_STOCK_ROWS
  const total = stockData?.total || 0

  const { execute: receiveStock, loading: receivingStock, error: receiveError } = useApiMutation<void>()
  const { execute: writeoffStock, loading: writingOff, error: writeoffError } = useApiMutation<void>()
  const { execute: createItem, loading: creatingItem, error: createError } = useApiMutation<{ id: number }>()

  const filteredRows = useMemo(() => {
    let data = rows
    if (search.trim()) {
      const query = search.trim().toLowerCase()
      data = data.filter(
        (row) =>
          row.item_name?.toLowerCase().includes(query) ||
          row.item_sku?.toLowerCase().includes(query)
      )
    }
    if (lowStockOnly) {
      data = data.filter((row) => row.quantity_available <= lowStockThreshold)
    }
    return data
  }, [rows, search, lowStockOnly])

  const productCategories = useMemo(() => {
    if (!items || !categories) return []
    const categoryIds = new Set(items.map((item) => item.category_id))
    return categories.filter((category) => categoryIds.has(category.id))
  }, [categories, items])

  const resetDialogState = () => {
    setQuantity('')
    setUnitCost('')
    setNotes('')
    setReasonCategory('damage')
    setReasonDetail('')
    setReceiveItemId('')
  }

  const resetNewItemForm = () => {
    setNewItemCategoryId('')
    setNewItemSku('')
    setNewItemName('')
    setNewItemQuantity('')
    setNewItemUnitCost('')
  }

  const handleReceive = async () => {
    const itemId = receiveDialog?.item_id ?? (receiveItemId ? Number(receiveItemId) : null)
    if (!itemId) {
      setError('Select an item to receive.')
      return
    }

    setError(null)
    const result = await receiveStock(() =>
      api.post('/inventory/receive', {
        item_id: itemId,
        quantity: Number(quantity),
        unit_cost: Number(unitCost),
        notes: notes.trim() || null,
      })
    )

    if (result !== null) {
      setReceiveOpen(false)
      setReceiveDialog(null)
      resetDialogState()
      refetchStock()
      refetchItems()
    }
  }

  const handleWriteOff = async () => {
    if (!writeoffDialog) {
      return
    }

    setError(null)
    const result = await writeoffStock(() =>
      api.post('/inventory/writeoff', {
        items: [
          {
            item_id: writeoffDialog.item_id,
            quantity: Number(quantity),
            reason_category: reasonCategory,
            reason_detail: reasonDetail.trim() || null,
          },
        ],
      })
    )

    if (result !== null) {
      setWriteoffDialog(null)
      resetDialogState()
      refetchStock()
    }
  }

  const handleCreateItem = async () => {
    if (!newItemCategoryId || !newItemName.trim() || !newItemQuantity || !newItemUnitCost) {
      setError('Fill category, name, quantity, and unit cost.')
      return
    }
    let skuToUse = newItemSku.trim()
    if (!skuToUse && categories && items) {
      const category = categories.find((entry) => entry.id === Number(newItemCategoryId))
      if (category) {
        skuToUse = nextSkuForCategory(category.name, items)
      }
    }
    if (!skuToUse) {
      setError('SKU was not generated. Re-select category.')
      return
    }

    setError(null)
    const item = await createItem(() =>
      api.post<ApiResponse<{ id: number }>>('/items', {
        category_id: Number(newItemCategoryId),
        sku_code: skuToUse,
        name: newItemName.trim(),
        item_type: 'product',
        price_type: 'standard',
        price: 0,
      })
    )

    if (!item) return

    try {
      await api.post('/inventory/receive', {
        item_id: item.id,
        quantity: Number(newItemQuantity),
        unit_cost: Number(newItemUnitCost),
        notes: 'Initial stock',
      })
      refetchStock()
      refetchItems()
      setCreateItemOpen(false)
      resetNewItemForm()
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        return
      }
      setError('Failed to receive initial stock.')
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Stock
        </Typography>
        <div className="flex gap-2 flex-wrap">
          {canManage && (
            <Button variant="contained" onClick={() => navigate('/inventory/issue')}>
              Issue
            </Button>
          )}
          {allowCreateItem && (
            <Button
              variant="contained"
              onClick={() => {
                resetNewItemForm()
                setCreateItemOpen(true)
              }}
            >
              New item
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-4 mb-4">
        <Input
          containerClassName="w-[240px] min-w-[200px]"
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          containerClassName="w-[260px] min-w-[200px]"
          label="Category"
          value={categoryFilter === 'all' ? '' : String(categoryFilter)}
          onChange={(e) => setCategoryFilter(e.target.value === '' ? 'all' : Number(e.target.value))}
        >
          <option value="">All</option>
          {productCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </Select>
        <Switch
          containerClassName="self-end whitespace-nowrap pb-1"
          checked={includeZero}
          onChange={(e) => setIncludeZero(e.target.checked)}
          label="Include zero"
        />
        <Switch
          containerClassName="self-end whitespace-nowrap pb-1"
          checked={lowStockOnly}
          onChange={(e) => setLowStockOnly(e.target.checked)}
          label={`Low stock (<= ${lowStockThreshold})`}
        />
      </div>

      {(error || stockError || receiveError || writeoffError || createError) && (
        <Alert severity="error" className="mb-4">
          {error || stockError || receiveError || writeoffError || createError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Item</TableHeaderCell>
              <TableHeaderCell>On hand</TableHeaderCell>
              <TableHeaderCell>Reserved</TableHeaderCell>
              <TableHeaderCell>Available</TableHeaderCell>
              <TableHeaderCell>Avg cost</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
              {filteredRows.map((row) => (
                <TableRow key={row.id}>
                 <TableCell>{row.item_name ?? '—'}</TableCell>
                 <TableCell>{row.quantity_on_hand}</TableCell>
                 <TableCell>{row.quantity_reserved}</TableCell>
                 <TableCell>{row.quantity_available}</TableCell>
                 <TableCell>{formatMoney(Number(row.average_cost))}</TableCell>
                  <TableCell>
                  {row.quantity_available <= lowStockThreshold ? (
                    <Chip size="small" color="warning" label="Low stock" />
                  ) : (
                      <Chip size="small" color="success" label="OK" />
                    )}
                 </TableCell>
                  <TableCell align="right">
                  {canManage ? (
                    <div className="flex flex-wrap gap-2 justify-end">
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                          setReceiveDialog(row)
                          setReceiveOpen(true)
                        }}
                      >
                        Receive
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="error"
                        onClick={() => setWriteoffDialog(row)}
                      >
                        Write-off
                      </Button>
                    </div>
                  ) : (
                      '—'
                    )}
                 </TableCell>
                </TableRow>
              ))}
            {loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Spinner size="small" />
                </td>
              </TableRow>
            )}
            {!filteredRows.length && !loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Typography color="secondary">No stock found</Typography>
                </td>
              </TableRow>
            )}
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

      <Dialog
        open={receiveOpen}
        onClose={() => {
          setReceiveOpen(false)
          setReceiveDialog(null)
        }}
        maxWidth="sm"
      >
        <DialogCloseButton onClose={() => {
          setReceiveOpen(false)
          setReceiveDialog(null)
        }} />
        <DialogTitle>Receive stock</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            {receiveDialog?.item_id ? (
              <Input label="Item" value={receiveDialog?.item_name ?? ''} disabled />
            ) : (
              <Select
                value={receiveItemId ? String(receiveItemId) : ''}
                onChange={(e) => setReceiveItemId(e.target.value ? Number(e.target.value) : '')}
                label="Item"
              >
                <option value="">Select item</option>
                {(items || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.sku_code})
                  </option>
                ))}
              </Select>
            )}
            <Input
              label="Quantity"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
            <Input
              label="Unit cost"
              type="number"
              value={unitCost}
              onChange={(e) => setUnitCost(e.target.value)}
            />
            <Textarea
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => {
            setReceiveOpen(false)
            setReceiveDialog(null)
          }}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleReceive} disabled={receivingStock}>
            {receivingStock ? <Spinner size="small" /> : 'Receive'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={createItemOpen} onClose={() => setCreateItemOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setCreateItemOpen(false)} />
        <DialogTitle>New product item</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Select
              value={newItemCategoryId ? String(newItemCategoryId) : ''}
              onChange={(e) => {
                const nextId = e.target.value ? Number(e.target.value) : ''
                setNewItemCategoryId(nextId)
                if (!nextId || !categories || !items) {
                  setNewItemSku('')
                  return
                }
                const category = categories.find((entry) => entry.id === Number(nextId))
                setNewItemSku(category ? nextSkuForCategory(category.name, items) : '')
              }}
              label="Category"
            >
              <option value="">Select category</option>
              {(categories || []).map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
            <Input
              label="Name"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
            />
            <Input
              label="Note"
              value="Selling price is set in Catalog"
              disabled
            />
            <Input
              label="Opening quantity"
              type="number"
              value={newItemQuantity}
              onChange={(e) => setNewItemQuantity(e.target.value)}
            />
            <Input
              label="Unit cost"
              type="number"
              value={newItemUnitCost}
              onChange={(e) => setNewItemUnitCost(e.target.value)}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCreateItemOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleCreateItem} disabled={creatingItem}>
            {creatingItem ? <Spinner size="small" /> : 'Create item'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(writeoffDialog)} onClose={() => setWriteoffDialog(null)} maxWidth="sm">
        <DialogCloseButton onClose={() => setWriteoffDialog(null)} />
        <DialogTitle>Write-off</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Input label="Item" value={writeoffDialog?.item_name ?? ''} disabled />
            <Input
              label="Quantity"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
            <Select
              value={reasonCategory}
              onChange={(e) => setReasonCategory(e.target.value as WriteOffReason)}
              label="Reason"
            >
              <option value="damage">Damage</option>
              <option value="expired">Expired</option>
              <option value="lost">Lost</option>
              <option value="other">Other</option>
            </Select>
            <Textarea
              label="Details"
              value={reasonDetail}
              onChange={(e) => setReasonDetail(e.target.value)}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setWriteoffDialog(null)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleWriteOff} disabled={writingOff}>
            {writingOff ? <Spinner size="small" /> : 'Write-off'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
