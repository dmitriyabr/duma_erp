import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { isAccountant } from '../../utils/permissions'
import { api, unwrapResponse } from '../../services/api'
import { formatMoney } from '../../utils/format'
import {
  Typography,
  Alert,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  Input,
  Switch,
  Tabs,
  TabsList,
  Tab,
  TabPanel,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Spinner,
} from '../../components/ui'
import { Plus, Trash2 } from 'lucide-react'

type CatalogTab = 'items' | 'categories'

type ItemType = 'product' | 'service'

interface CategoryRow {
  id: number
  name: string
  is_active: boolean
}

interface KitItemRow {
  id: number
  item_id: number
  item_name?: string | null
  item_sku?: string | null
  quantity: number
}

interface KitRow {
  id: number
  category_id: number
  category_name?: string | null
  sku_code: string
  name: string
  item_type: ItemType
  price_type: string
  price?: number | null
  requires_full_payment: boolean
  is_active: boolean
  items: KitItemRow[]
}

interface InventoryItemRow {
  id: number
  sku_code: string
  name: string
  category_id: number
  category_name?: string | null
  item_type: ItemType
  is_active: boolean
}

const itemTypeOptions: { label: string; value: ItemType }[] = [
  { label: 'Product', value: 'product' },
  { label: 'Service', value: 'service' },
]

const tabConfig: { key: CatalogTab; label: string; path: string }[] = [
  { key: 'items', label: 'Items', path: '/billing/catalog/items' },
  { key: 'categories', label: 'Categories', path: '/billing/catalog/categories' },
]

const emptyKitForm = {
  name: '',
  category_id: '',
  item_type: 'product' as ItemType,
  price: '',
  items: [{ item_id: '', quantity: 1 }],
}

const emptyCategoryForm = { name: '' }

export const CatalogPage = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const readOnly = isAccountant(user)

  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')
  const [typeFilter, setTypeFilter] = useState<ItemType | 'all'>('all')
  const [showInactive, setShowInactive] = useState(false)

  const [kitDialogOpen, setKitDialogOpen] = useState(false)
  const [editingKit, setEditingKit] = useState<KitRow | null>(null)
  const [kitForm, setKitForm] = useState({ ...emptyKitForm })

  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false)
  const [editingCategory, setEditingCategory] = useState<CategoryRow | null>(null)
  const [categoryForm, setCategoryForm] = useState({ ...emptyCategoryForm })

  const [confirmState, setConfirmState] = useState<{
    open: boolean
    kit?: KitRow
    category?: CategoryRow
    nextActive?: boolean
  }>({ open: false })
  const [validationError, setValidationError] = useState<string | null>(null)

  const categoriesApi = useApi<CategoryRow[]>('/items/categories', {
    params: { include_inactive: true },
  })
  const kitsApi = useApi<KitRow[]>('/items/kits', { params: { include_inactive: showInactive } }, [
    showInactive,
  ])
  const inventoryApi = useApi<InventoryItemRow[]>('/items', {
    params: { item_type: 'product', include_inactive: false },
  })
  const kitMutation = useApiMutation<unknown>()
  const categoryMutation = useApiMutation<CategoryRow | unknown>()
  const toggleMutation = useApiMutation<unknown>()

  const categories = categoriesApi.data ?? []
  const kits = useMemo(
    () => (kitsApi.data ?? []).filter((kit) => kit.price_type === 'standard'),
    [kitsApi.data]
  )
  const inventoryItems = inventoryApi.data ?? []
  const tabError =
    categoriesApi.error ??
    kitsApi.error ??
    inventoryApi.error ??
    kitMutation.error ??
    categoryMutation.error ??
    toggleMutation.error
  const loading = categoriesApi.loading || categoryMutation.loading || kitMutation.loading || toggleMutation.loading
  const kitsLoading = kitsApi.loading

  const activeTab = useMemo<CatalogTab>(() => {
    const match = tabConfig.find((tab) => location.pathname.startsWith(tab.path))
    return match?.key ?? 'items'
  }, [location.pathname])

  useEffect(() => {
    if (location.pathname === '/billing/catalog') {
      navigate('/billing/catalog/items', { replace: true })
    }
  }, [location.pathname, navigate])

  const handleTabChange = (value: CatalogTab) => {
    const target = tabConfig.find((tab) => tab.key === value)
    if (target) {
      navigate(target.path)
    }
  }

  const filteredKits = useMemo(() => {
    const term = search.trim().toLowerCase()
    return kits.filter((kit) => {
      if (term) {
        const matchesName = kit.name.toLowerCase().includes(term)
        const matchesCategory = kit.category_name?.toLowerCase().includes(term)
        if (!matchesName && !matchesCategory) {
          return false
        }
      }
      if (categoryFilter !== 'all' && kit.category_id !== categoryFilter) {
        return false
      }
      if (typeFilter !== 'all' && kit.item_type !== typeFilter) {
        return false
      }
      return true
    })
  }, [kits, search, categoryFilter, typeFilter])

  const openCreateKit = () => {
    setEditingKit(null)
    setKitForm({ ...emptyKitForm })
    setKitDialogOpen(true)
  }

  const openEditKit = (kit: KitRow) => {
    setEditingKit(kit)
    setKitForm({
      name: kit.name,
      category_id: String(kit.category_id),
      item_type: kit.item_type,
      price: kit.price?.toString() ?? '',
      items:
        kit.item_type === 'product' && kit.items.length
          ? kit.items.map((item) => ({
              item_id: String(item.item_id),
              quantity: item.quantity,
            }))
          : [{ item_id: '', quantity: 1 }],
    })
    setKitDialogOpen(true)
  }

  const resetKitDialog = () => {
    setKitDialogOpen(false)
    setKitForm({ ...emptyKitForm })
    setEditingKit(null)
  }

  const displayTabError = validationError ?? tabError

  const submitKit = async () => {
    const categoryId =
      typeof kitForm.category_id === 'string'
        ? Number(kitForm.category_id)
        : kitForm.category_id
    if (!categoryId || Number.isNaN(categoryId)) {
      setValidationError('Select a category before saving.')
      return
    }
    if (!kitForm.name.trim()) {
      setValidationError('Enter a name for the item.')
      return
    }
    const priceValue = kitForm.price === '' ? null : Number(kitForm.price)
    if (priceValue === null || Number.isNaN(priceValue)) {
      setValidationError('Enter a valid price.')
      return
    }
    const itemsPayload =
      kitForm.item_type === 'product'
        ? kitForm.items
            .filter((item) => item.item_id)
            .map((item) => ({ item_id: Number(item.item_id), quantity: item.quantity }))
        : []
    if (kitForm.item_type === 'product' && !itemsPayload.length) {
      setValidationError('Product items must include at least one component.')
      return
    }
    setValidationError(null)
    kitMutation.reset()
    const ok = editingKit
      ? await kitMutation.execute(() =>
          api
            .patch(`/items/kits/${editingKit.id}`, {
              category_id: categoryId,
              name: kitForm.name.trim(),
              price: priceValue,
              items: kitForm.item_type === 'product' ? itemsPayload : undefined,
            })
            .then((r) => ({ data: { data: unwrapResponse(r) } }))
        )
      : await kitMutation.execute(() =>
          api
            .post('/items/kits', {
              category_id: categoryId,
              name: kitForm.name.trim(),
              item_type: kitForm.item_type,
              price_type: 'standard',
              price: priceValue,
              items: kitForm.item_type === 'product' ? itemsPayload : [],
            })
            .then((r) => ({ data: { data: unwrapResponse(r) } }))
        )
    if (ok != null) {
      resetKitDialog()
      kitsApi.refetch()
    }
  }

  const requestToggleKitActive = (kit: KitRow) => {
    setConfirmState({ open: true, kit, nextActive: !kit.is_active })
  }

  const openCreateCategory = () => {
    setEditingCategory(null)
    setCategoryForm({ ...emptyCategoryForm })
    setCategoryDialogOpen(true)
  }

  const openEditCategory = (category: CategoryRow) => {
    setEditingCategory(category)
    setCategoryForm({ name: category.name })
    setCategoryDialogOpen(true)
  }

  const resetCategoryDialog = () => {
    setCategoryDialogOpen(false)
    setCategoryForm({ ...emptyCategoryForm })
    setEditingCategory(null)
  }

  const submitCategory = async () => {
    if (!categoryForm.name.trim()) {
      setValidationError('Enter a category name.')
      return
    }
    setValidationError(null)
    categoryMutation.reset()
    const result = editingCategory
      ? await categoryMutation.execute(() =>
          api
            .patch(`/items/categories/${editingCategory.id}`, {
              name: categoryForm.name.trim(),
            })
            .then((r) => ({ data: { data: unwrapResponse(r) } }))
        )
      : await categoryMutation.execute(() =>
          api
            .post('/items/categories', { name: categoryForm.name.trim() })
            .then((r) => ({ data: { data: unwrapResponse<CategoryRow>(r) } }))
        )
    if (result != null) {
      if (!editingCategory && typeof result === 'object' && 'id' in result) {
        setKitForm((prev) => ({ ...prev, category_id: String((result as CategoryRow).id) }))
      }
      resetCategoryDialog()
      categoriesApi.refetch()
    }
  }

  const requestToggleCategoryActive = (category: CategoryRow) => {
    setConfirmState({ open: true, category, nextActive: !category.is_active })
  }

  const confirmToggleActive = async () => {
    if (confirmState.kit) {
      setConfirmState({ open: false })
      toggleMutation.reset()
      const ok = await toggleMutation.execute(() =>
        api
          .patch(`/items/kits/${confirmState.kit!.id}`, { is_active: confirmState.nextActive })
          .then((r) => ({ data: { data: unwrapResponse(r) } }))
      )
      if (ok != null) kitsApi.refetch()
      return
    }
    if (confirmState.category) {
      setConfirmState({ open: false })
      toggleMutation.reset()
      const ok = await toggleMutation.execute(() =>
        api
          .patch(`/items/categories/${confirmState.category!.id}`, {
            is_active: confirmState.nextActive,
          })
          .then((r) => ({ data: { data: unwrapResponse(r) } }))
      )
      if (ok != null) categoriesApi.refetch()
    }
  }

  const handleCategorySelect = (value: number | string) => {
    if (value === 'create') {
      openCreateCategory()
      return
    }
    setKitForm((prev) => ({ ...prev, category_id: String(value) }))
  }

  const updateKitItem = (index: number, field: 'item_id' | 'quantity', value: string | number) => {
    setKitForm((prev) => {
      const nextItems = [...prev.items]
      const item = { ...nextItems[index] }
      if (field === 'quantity') {
        const nextValue = Number(value)
        item.quantity = Number.isNaN(nextValue) || nextValue < 1 ? 1 : nextValue
      } else {
        item.item_id = value as string
      }
      nextItems[index] = item
      return { ...prev, items: nextItems }
    })
  }

  const removeKitItem = (index: number) => {
    setKitForm((prev) => {
      const nextItems = prev.items.filter((_, idx) => idx !== index)
      return { ...prev, items: nextItems.length ? nextItems : [{ item_id: '', quantity: 1 }] }
    })
  }

  const addKitItem = () => {
    setKitForm((prev) => ({
      ...prev,
      items: [...prev.items, { item_id: '', quantity: 1 }],
    }))
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">
        Catalog
      </Typography>

      <Tabs value={activeTab} onChange={handleTabChange}>
        <TabsList>
          {tabConfig.map((tab) => (
            <Tab key={tab.key} value={tab.key}>
              {tab.label}
            </Tab>
          ))}
        </TabsList>

        {displayTabError && (
          <Alert severity="error" className="mt-4" onClose={() => {}}>
            {displayTabError}
          </Alert>
        )}

        <TabPanel value="items">
          <div className="flex items-center justify-between mt-4">
            <Typography variant="h6" className="font-semibold">
              Catalog items
            </Typography>
            {!readOnly && (
              <Button variant="contained" onClick={openCreateKit}>
                New item
              </Button>
            )}
          </div>

          <div className="flex flex-wrap gap-4 mt-4">
            <Input
              label="Search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="min-w-[200px]"
            />
            <Select
              value={categoryFilter === 'all' ? 'all' : String(categoryFilter)}
              onChange={(event) => {
                const value = event.target.value
                setCategoryFilter(value === 'all' ? 'all' : Number(value))
              }}
              label="Category"
              className="min-w-[180px]"
            >
              <option value="all">All</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
            <Select
              value={typeFilter === 'all' ? 'all' : typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as ItemType | 'all')}
              label="Type"
              className="min-w-[160px]"
            >
              <option value="all">All</option>
              {itemTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <div className="flex items-center gap-2">
              <Switch
                checked={showInactive}
                onChange={(event) => setShowInactive(event.target.checked)}
              />
              <span className="text-sm font-medium text-slate-700">Show inactive</span>
            </div>
          </div>

          <Table className="mt-4">
            <TableHead>
              <TableRow>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Category</TableHeaderCell>
                <TableHeaderCell>Price</TableHeaderCell>
                <TableHeaderCell>Type</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredKits.map((kit) => (
                <TableRow key={kit.id}>
                  <TableCell>{kit.name}</TableCell>
                  <TableCell>{kit.category_name ?? '—'}</TableCell>
                  <TableCell>{formatMoney(kit.price ?? null)}</TableCell>
                  <TableCell>{kit.item_type}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={kit.is_active ? 'Active' : 'Inactive'}
                      color={kit.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <div className="flex gap-2 justify-end">
                      {readOnly ? (
                        <Button size="small" onClick={() => openEditKit(kit)}>
                          View
                        </Button>
                      ) : (
                        <>
                          <Button size="small" onClick={() => openEditKit(kit)}>
                            Edit
                          </Button>
                          <Button size="small" onClick={() => requestToggleKitActive(kit)}>
                            {kit.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!filteredKits.length && !kitsLoading && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    No catalog items found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabPanel>

        <TabPanel value="categories">
          <div className="flex items-center justify-between mt-4">
            <Typography variant="h6" className="font-semibold">
              Categories
            </Typography>
            {!readOnly && (
              <Button variant="contained" onClick={openCreateCategory}>
                New category
              </Button>
            )}
          </div>

          <Table className="mt-4">
            <TableHead>
              <TableRow>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {categories.map((category) => (
                <TableRow key={category.id}>
                  <TableCell>{category.name}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={category.is_active ? 'Active' : 'Inactive'}
                      color={category.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell align="right">
                    {!readOnly && (
                      <div className="flex gap-2 justify-end">
                        <Button size="small" onClick={() => openEditCategory(category)}>
                          Edit
                        </Button>
                        <Button size="small" onClick={() => requestToggleCategoryActive(category)}>
                          {category.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {loading && (
                <TableRow>
                  <TableCell colSpan={3} align="center">
                    <Spinner size="small" />
                  </TableCell>
                </TableRow>
              )}
              {!categories.length && !loading && (
                <TableRow>
                  <TableCell colSpan={3} align="center">
                    No categories found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabPanel>
      </Tabs>

      <Dialog open={kitDialogOpen} onClose={resetKitDialog} maxWidth="md">
        <DialogTitle>
          {readOnly && editingKit ? 'View item' : editingKit ? 'Edit item' : 'Create item'}
        </DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Name"
              value={kitForm.name}
              onChange={(event) => setKitForm({ ...kitForm, name: event.target.value })}
              required
              disabled={readOnly}
            />
            <Select
              value={kitForm.category_id}
              onChange={(event) => handleCategorySelect(event.target.value as number | string)}
              label="Category"
              disabled={readOnly}
            >
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
              {!readOnly && (
                <option value="create">
                  <div className="flex items-center gap-2">
                    <Plus className="w-4 h-4" />
                    Add new category
                  </div>
                </option>
              )}
            </Select>
            <Select
              value={kitForm.item_type}
              onChange={(event) =>
                setKitForm({
                  ...kitForm,
                  item_type: event.target.value as ItemType,
                })
              }
              label="Type"
              disabled={!!editingKit || readOnly}
            >
              {itemTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Input
              label="Price"
              type="number"
              value={kitForm.price}
              onChange={(event) => setKitForm({ ...kitForm, price: event.target.value })}
              required
              disabled={readOnly}
              min={0}
              step={0.01}
            />

            {kitForm.item_type === 'product' && (
              <div className="grid gap-2">
                <Typography variant="subtitle1" className="font-semibold">
                  Components
                </Typography>
                {kitForm.items.map((item, index) => (
                  <div
                    key={`kit-item-${index}`}
                    className={readOnly ? 'grid grid-cols-[1fr_140px] gap-2' : 'grid grid-cols-[1fr_140px_auto] gap-2'}
                  >
                    <Select
                      value={item.item_id}
                      onChange={(event) =>
                        updateKitItem(index, 'item_id', event.target.value as string)
                      }
                      label="Inventory item"
                      disabled={readOnly}
                    >
                      <option value="">Select item</option>
                      {inventoryItems.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </Select>
                    <Input
                      label="Qty"
                      type="number"
                      value={item.quantity}
                      onChange={(event) => updateKitItem(index, 'quantity', event.target.value)}
                      onFocus={(event) => event.currentTarget.select()}
                      disabled={readOnly}
                      min={1}
                      step={1}
                    />
                    {!readOnly && (
                      <button
                        type="button"
                        onClick={() => removeKitItem(index)}
                        className="p-2 hover:bg-slate-100 rounded transition-colors self-end"
                        aria-label="Remove component"
                      >
                        <Trash2 className="w-5 h-5 text-slate-500" />
                      </button>
                    )}
                  </div>
                ))}
                {!readOnly && (
                  <Button variant="outlined" onClick={addKitItem} className="self-start">
                    <Plus className="w-4 h-4 mr-2" />
                    Add component
                  </Button>
                )}
              </div>
            )}
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={resetKitDialog}>{readOnly ? 'Close' : 'Cancel'}</Button>
          {!readOnly && (
            <Button variant="contained" onClick={submitKit} disabled={loading}>
              {loading ? <Spinner size="small" /> : 'Save'}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={categoryDialogOpen} onClose={resetCategoryDialog} maxWidth="sm">
        <DialogTitle>{editingCategory ? 'Edit category' : 'Create category'}</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Name"
              value={categoryForm.name}
              onChange={(event) => setCategoryForm({ name: event.target.value })}
              required
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={resetCategoryDialog}>Cancel</Button>
          <Button variant="contained" onClick={submitCategory} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmState.open}
        title={`${
          confirmState.nextActive ? 'Activate' : 'Deactivate'
        } ${confirmState.kit ? 'item' : 'category'}`}
        description={`Are you sure you want to ${
          confirmState.nextActive ? 'activate' : 'deactivate'
        } this ${confirmState.kit ? 'item' : 'category'}?`}
        confirmLabel={confirmState.nextActive ? 'Activate' : 'Deactivate'}
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={confirmToggleActive}
      />
    </div>
  )
}
