import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
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
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'

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
  const canManage = user?.role === 'SuperAdmin' || user?.role === 'Admin'
  const canCreateItem = user?.role === 'SuperAdmin'
  const [rows, setRows] = useState<StockRow[]>([])
  const [items, setItems] = useState<ItemOption[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [includeZero, setIncludeZero] = useState(false)
  const [lowStockOnly, setLowStockOnly] = useState(false)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')
  const [categories, setCategories] = useState<CategoryOption[]>([])
  const [loading, setLoading] = useState(false)
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

  const fetchCategories = async () => {
    try {
      const response = await api.get<ApiResponse<CategoryOption[]>>('/items/categories')
      setCategories(response.data.data)
    } catch {
      setCategories([])
    }
  }

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

  const fetchStock = async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number | boolean> = {
        page: page + 1,
        limit: lowStockOnly || search.trim() ? 500 : limit,
        include_zero: includeZero,
      }
      if (categoryFilter !== 'all') {
        params.category_id = categoryFilter
      }
      const response = await api.get<ApiResponse<PaginatedResponse<StockRow>>>('/inventory/stock', {
        params,
      })
      setRows(response.data.data.items)
      setTotal(response.data.data.total)
    } catch {
      setError('Failed to load stock.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCategories()
    fetchItems()
  }, [])

  useEffect(() => {
    if (!createItemOpen || !newItemCategoryId) {
      return
    }
    const category = categories.find((entry) => entry.id === Number(newItemCategoryId))
    if (!category) {
      return
    }
    setNewItemSku(nextSkuForCategory(category.name, items))
  }, [createItemOpen, newItemCategoryId, categories, items])

  useEffect(() => {
    fetchStock()
  }, [page, limit, includeZero, categoryFilter, lowStockOnly])

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
    setLoading(true)
    setError(null)
    try {
      await api.post('/inventory/receive', {
        item_id: itemId,
        quantity: Number(quantity),
        unit_cost: Number(unitCost),
        notes: notes.trim() || null,
      })
      setReceiveOpen(false)
      setReceiveDialog(null)
      resetDialogState()
      await fetchStock()
      await fetchItems()
    } catch {
      setError('Failed to receive stock.')
    } finally {
      setLoading(false)
    }
  }

  const handleWriteOff = async () => {
    if (!writeoffDialog) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.post('/inventory/writeoff', {
        items: [
          {
            item_id: writeoffDialog.item_id,
            quantity: Number(quantity),
            reason_category: reasonCategory,
            reason_detail: reasonDetail.trim() || null,
          },
        ],
      })
      setWriteoffDialog(null)
      resetDialogState()
      await fetchStock()
    } catch {
      setError('Failed to write off stock.')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateItem = async () => {
    if (
      !newItemCategoryId ||
      !newItemName.trim() ||
      !newItemQuantity ||
      !newItemUnitCost
    ) {
      setError('Fill category, name, quantity, and unit cost.')
      return
    }
    if (!newItemSku.trim()) {
      setError('SKU was not generated. Re-select category.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await api.post<ApiResponse<{ id: number }>>('/items', {
        category_id: Number(newItemCategoryId),
        sku_code: newItemSku.trim(),
        name: newItemName.trim(),
        item_type: 'product',
        price_type: 'standard',
        price: 0,
      })
      await api.post('/inventory/receive', {
        item_id: response.data.data.id,
        quantity: Number(newItemQuantity),
        unit_cost: Number(newItemUnitCost),
        notes: 'Initial stock',
      })
      await fetchStock()
      await fetchItems()
      setCreateItemOpen(false)
      resetNewItemForm()
    } catch {
      setError('Failed to create item.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Stock
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {canManage ? (
            <Button variant="contained" onClick={() => navigate('/inventory/issue')}>
              Issue
            </Button>
          ) : null}
          {canCreateItem ? (
            <Button
              variant="contained"
              onClick={() => {
                resetNewItemForm()
                setCreateItemOpen(true)
              }}
            >
              New item
            </Button>
          ) : null}
        </Box>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Category</InputLabel>
          <Select
            value={categoryFilter}
            label="Category"
            onChange={(event) => setCategoryFilter(event.target.value as number | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            {productCategories.map((category) => (
              <MenuItem key={category.id} value={category.id}>
                {category.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={includeZero}
              onChange={(event) => setIncludeZero(event.target.checked)}
            />
          }
          label="Include zero"
        />
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={lowStockOnly}
              onChange={(event) => setLowStockOnly(event.target.checked)}
            />
          }
          label={`Low stock (<= ${lowStockThreshold})`}
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
            <TableCell>Item</TableCell>
            <TableCell>On hand</TableCell>
            <TableCell>Reserved</TableCell>
            <TableCell>Available</TableCell>
            <TableCell>Avg cost</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                  <>
                    <Button
                      size="small"
                      onClick={() => {
                        setReceiveDialog(row)
                        setReceiveOpen(true)
                      }}
                    >
                      Receive
                    </Button>
                    <Button size="small" onClick={() => setWriteoffDialog(row)}>
                      Write-off
                    </Button>
                  </>
                ) : (
                  '—'
                )}
              </TableCell>
            </TableRow>
          ))}
          {!filteredRows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={7} align="center">
                No stock found
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

      <Dialog
        open={receiveOpen}
        onClose={() => {
          setReceiveOpen(false)
          setReceiveDialog(null)
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Receive stock</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          {receiveDialog?.item_id ? (
            <TextField label="Item" value={receiveDialog?.item_name ?? ''} disabled />
          ) : (
            <FormControl>
              <InputLabel>Item</InputLabel>
              <Select
                value={receiveItemId}
                label="Item"
                onChange={(event) => setReceiveItemId(Number(event.target.value))}
                displayEmpty
              >
                <MenuItem value="">Select item</MenuItem>
                {items.map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.name} ({item.sku_code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          <TextField
            label="Quantity"
            type="number"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
          <TextField
            label="Unit cost"
            type="number"
            value={unitCost}
            onChange={(event) => setUnitCost(event.target.value)}
          />
          <TextField
            label="Notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReceiveDialog(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleReceive} disabled={loading}>
            Receive
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={createItemOpen} onClose={() => setCreateItemOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>New product item</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Category</InputLabel>
            <Select
              value={newItemCategoryId}
              label="Category"
              onChange={(event) => setNewItemCategoryId(Number(event.target.value))}
              displayEmpty
            >
              <MenuItem value="">Select category</MenuItem>
              {categories.map((category) => (
                <MenuItem key={category.id} value={category.id}>
                  {category.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Name"
            value={newItemName}
            onChange={(event) => setNewItemName(event.target.value)}
          />
          <TextField
            label="Note"
            value="Selling price is set in Catalog"
            disabled
          />
          <TextField
            label="Opening quantity"
            type="number"
            value={newItemQuantity}
            onChange={(event) => setNewItemQuantity(event.target.value)}
          />
          <TextField
            label="Unit cost"
            type="number"
            value={newItemUnitCost}
            onChange={(event) => setNewItemUnitCost(event.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateItemOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateItem} disabled={loading}>
            Create item
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(writeoffDialog)} onClose={() => setWriteoffDialog(null)} fullWidth maxWidth="sm">
        <DialogTitle>Write-off</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField label="Item" value={writeoffDialog?.item_name ?? ''} disabled />
          <TextField
            label="Quantity"
            type="number"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
          <FormControl>
            <InputLabel>Reason</InputLabel>
            <Select
              value={reasonCategory}
              label="Reason"
              onChange={(event) => setReasonCategory(event.target.value as WriteOffReason)}
            >
              <MenuItem value="damage">Damage</MenuItem>
              <MenuItem value="expired">Expired</MenuItem>
              <MenuItem value="lost">Lost</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Details"
            value={reasonDetail}
            onChange={(event) => setReasonDetail(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWriteoffDialog(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleWriteOff} disabled={loading}>
            Write-off
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
