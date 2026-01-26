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
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api } from '../../services/api'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface CategoryRow {
  id: number
  name: string
  is_active: boolean
}

interface ItemRow {
  id: number
  category_id: number
  category_name?: string | null
  sku_code: string
  name: string
  is_active: boolean
}

const emptyForm = {
  category_id: '',
  sku_code: '',
  name: '',
  opening_quantity: '',
  unit_cost: '',
}

const buildSkuPrefix = (categoryName: string) => {
  const cleaned = categoryName.toUpperCase().replace(/[^A-Z0-9]/g, '')
  return cleaned ? cleaned.slice(0, 6) : 'CAT'
}

const nextSkuForCategory = (categoryName: string, items: ItemRow[]) => {
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

export const ItemsPage = () => {
  const [items, setItems] = useState<ItemRow[]>([])
  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')
  const [showInactive, setShowInactive] = useState(false)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<ItemRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const [confirmState, setConfirmState] = useState<{
    open: boolean
    item?: ItemRow
    nextActive?: boolean
  }>({ open: false })

  const loadItems = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<ItemRow[]>>('/items', {
        params: { item_type: 'product', include_inactive: true },
      })
      setItems(response.data.data)
    } catch {
      setError('Failed to load items.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadCategories = useCallback(async () => {
    try {
      const response = await api.get<ApiResponse<CategoryRow[]>>('/items/categories', {
        params: { include_inactive: true },
      })
      setCategories(response.data.data)
    } catch {
      setCategories([])
    }
  }, [])

  useEffect(() => {
    loadItems()
    loadCategories()
  }, [loadItems, loadCategories])

  useEffect(() => {
    if (!dialogOpen || editingItem) {
      return
    }
    const categoryId =
      typeof form.category_id === 'string' ? Number(form.category_id) : form.category_id
    if (!categoryId) {
      return
    }
    const category = categories.find((entry) => entry.id === categoryId)
    if (!category) {
      return
    }
    setForm((prev) => ({
      ...prev,
      sku_code: nextSkuForCategory(category.name, items),
    }))
  }, [dialogOpen, editingItem, form.category_id, categories, items])

  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase()
    return items.filter((item) => {
      if (!showInactive && !item.is_active) {
        return false
      }
      if (categoryFilter !== 'all' && item.category_id !== categoryFilter) {
        return false
      }
      if (term) {
        const matchesName = item.name.toLowerCase().includes(term)
        const matchesSku = item.sku_code.toLowerCase().includes(term)
        if (!matchesName && !matchesSku) {
          return false
        }
      }
      return true
    })
  }, [items, search, categoryFilter, showInactive])

  const openCreate = () => {
    setEditingItem(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (item: ItemRow) => {
    setEditingItem(item)
    setForm({
      category_id: String(item.category_id),
      sku_code: item.sku_code,
      name: item.name,
      opening_quantity: '',
      unit_cost: '',
    })
    setDialogOpen(true)
  }

  const resetDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    setForm({ ...emptyForm })
  }

  const handleSubmit = async () => {
    const categoryId =
      typeof form.category_id === 'string' ? Number(form.category_id) : form.category_id
    if (!categoryId || Number.isNaN(categoryId)) {
      setError('Select a category.')
      return
    }
    if (!form.name.trim()) {
      setError('Enter item name.')
      return
    }

    if (!editingItem && !form.sku_code.trim()) {
      setError('SKU was not generated. Try selecting category again.')
      return
    }

    const openingQuantity = form.opening_quantity ? Number(form.opening_quantity) : 0
    const unitCost = form.unit_cost ? Number(form.unit_cost) : 0
    if (!editingItem && openingQuantity && !unitCost) {
      setError('Provide unit cost for opening quantity.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      if (editingItem) {
        await api.patch(`/items/${editingItem.id}`, {
          category_id: categoryId,
          name: form.name.trim(),
        })
      } else {
        const response = await api.post<ApiResponse<{ id: number }>>('/items', {
          category_id: categoryId,
          sku_code: form.sku_code.trim(),
          name: form.name.trim(),
          item_type: 'product',
          price_type: 'standard',
          price: 0,
        })
        if (openingQuantity) {
          await api.post('/inventory/receive', {
            item_id: response.data.data.id,
            quantity: openingQuantity,
            unit_cost: unitCost,
            notes: 'Initial stock',
          })
        }
      }
      await loadItems()
      resetDialog()
    } catch {
      setError('Failed to save item.')
    } finally {
      setLoading(false)
    }
  }

  const requestToggleActive = (item: ItemRow) => {
    setConfirmState({ open: true, item, nextActive: !item.is_active })
  }

  const confirmToggleActive = async () => {
    if (!confirmState.item) {
      return
    }
    setConfirmState({ open: false })
    setLoading(true)
    try {
      await api.patch(`/items/${confirmState.item.id}`, {
        is_active: confirmState.nextActive,
      })
      await loadItems()
    } catch {
      setError('Failed to update item status.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Inventory items
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New item
        </Button>
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
            {categories.map((category) => (
              <MenuItem key={category.id} value={category.id}>
                {category.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={showInactive ? 'all' : 'active'}
            label="Status"
            onChange={(event) => setShowInactive(event.target.value === 'all')}
          >
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="all">All</MenuItem>
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
            <TableCell>Name</TableCell>
            <TableCell>Category</TableCell>
            <TableCell>SKU</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filteredItems.map((item) => (
            <TableRow key={item.id}>
              <TableCell>{item.name}</TableCell>
              <TableCell>{item.category_name ?? '—'}</TableCell>
              <TableCell>{item.sku_code}</TableCell>
              <TableCell>
                <Chip
                  size="small"
                  label={item.is_active ? 'Active' : 'Inactive'}
                  color={item.is_active ? 'success' : 'default'}
                />
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => openEdit(item)}>
                  Edit
                </Button>
                <Button size="small" onClick={() => requestToggleActive(item)}>
                  {item.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!filteredItems.length && !loading ? (
            <TableRow>
              <TableCell colSpan={5} align="center">
                No items found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={resetDialog} fullWidth maxWidth="sm">
        <DialogTitle>{editingItem ? 'Edit item' : 'Create item'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Category</InputLabel>
            <Select
              value={form.category_id}
              label="Category"
              onChange={(event) => setForm((prev) => ({ ...prev, category_id: event.target.value }))}
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
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
          />
          {!editingItem ? (
            <>
              <TextField
                label="Opening quantity"
                type="number"
                value={form.opening_quantity}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, opening_quantity: event.target.value }))
                }
              />
              <TextField
                label="Unit cost"
                type="number"
                value={form.unit_cost}
                onChange={(event) => setForm((prev) => ({ ...prev, unit_cost: event.target.value }))}
              />
            </>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={resetDialog}>Cancel</Button>
          <Button variant="contained" onClick={handleSubmit} disabled={loading}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmState.open}
        title={`${confirmState.nextActive ? 'Activate' : 'Deactivate'} item`}
        description={`Are you sure you want to ${
          confirmState.nextActive ? 'activate' : 'deactivate'
        } this item?`}
        confirmLabel={confirmState.nextActive ? 'Activate' : 'Deactivate'}
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={confirmToggleActive}
      />
    </Box>
  )
}
