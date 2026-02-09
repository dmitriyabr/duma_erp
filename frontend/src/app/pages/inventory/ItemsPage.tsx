import { useEffect, useMemo, useState } from 'react'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

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
  const { data: items, loading, error, refetch } = useApi<ItemRow[]>('/items?item_type=product&include_inactive=true')
  const { data: categories } = useApi<CategoryRow[]>('/items/categories?include_inactive=true')
  const { execute: saveItem, loading: saving, error: saveError } = useApiMutation<{ id: number }>()
  const { execute: toggleActive, loading: _toggling, error: toggleError } = useApiMutation()

  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')
  const [showInactive, setShowInactive] = useState(false)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<ItemRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })
  const [validationError, setValidationError] = useState<string | null>(null)

  const [confirmState, setConfirmState] = useState<{
    open: boolean
    item?: ItemRow
    nextActive?: boolean
  }>({ open: false })

  useEffect(() => {
    if (!dialogOpen || editingItem || !categories || !items) {
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
    return (items || []).filter((item) => {
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
      setValidationError('Select a category.')
      return
    }
    if (!form.name.trim()) {
      setValidationError('Enter item name.')
      return
    }

    if (!editingItem && !form.sku_code.trim()) {
      setValidationError('SKU was not generated. Try selecting category again.')
      return
    }

    const openingQuantity = form.opening_quantity ? Number(form.opening_quantity) : 0
    const unitCost = form.unit_cost ? Number(form.unit_cost) : 0
    if (!editingItem && openingQuantity && !unitCost) {
      setValidationError('Provide unit cost for opening quantity.')
      return
    }

    setValidationError(null)

    const result = await saveItem(async () => {
      if (editingItem) {
        return api.patch(`/items/${editingItem.id}`, {
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
        return response
      }
    })

    if (result) {
      resetDialog()
      refetch()
    }
  }

  const requestToggleActive = (item: ItemRow) => {
    setConfirmState({ open: true, item, nextActive: !item.is_active })
  }

  const confirmToggleActive = async () => {
    if (!confirmState.item) {
      return
    }
    const item = confirmState.item
    const nextActive = confirmState.nextActive
    setConfirmState({ open: false })

    const result = await toggleActive(() =>
      api.patch(`/items/${item.id}`, {
        is_active: nextActive,
      })
    )

    if (result) {
      refetch()
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Inventory items
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New item
        </Button>
      </div>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or SKU"
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Category"
            value={categoryFilter === 'all' ? 'all' : String(categoryFilter)}
            onChange={(e) => setCategoryFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          >
            <option value="all">All</option>
            {(categories || []).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Status"
            value={showInactive ? 'all' : 'active'}
            onChange={(e) => setShowInactive(e.target.value === 'all')}
          >
            <option value="active">Active</option>
            <option value="all">All</option>
          </Select>
        </div>
      </div>

      {(error || saveError || toggleError || validationError) && (
        <Alert severity="error" className="mb-4">
          {error || saveError || toggleError || validationError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Category</TableHeaderCell>
              <TableHeaderCell>SKU</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
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
                  <div className="flex gap-2 justify-end">
                    <Button size="small" variant="outlined" onClick={() => openEdit(item)}>
                      Edit
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color={item.is_active ? 'error' : 'success'}
                      onClick={() => requestToggleActive(item)}
                    >
                      {item.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!filteredItems.length && !loading && (
              <TableRow>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <Typography color="secondary">No items found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onClose={resetDialog} maxWidth="md">
        <DialogCloseButton onClose={resetDialog} />
        <DialogTitle>{editingItem ? 'Edit item' : 'Create item'}</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Select
              label="Category"
              value={form.category_id}
              onChange={(e) => setForm((prev) => ({ ...prev, category_id: e.target.value }))}
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
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              required
            />
            {!editingItem && (
              <>
                <Input
                  label="Opening quantity"
                  type="number"
                  value={form.opening_quantity}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, opening_quantity: e.target.value }))
                  }
                />
                <Input
                  label="Unit cost"
                  type="number"
                  value={form.unit_cost}
                  onChange={(e) => setForm((prev) => ({ ...prev, unit_cost: e.target.value }))}
                />
              </>
            )}
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={resetDialog}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleSubmit} disabled={saving}>
            {saving ? <Spinner size="small" /> : 'Save'}
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
    </div>
  )
}
