import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { canManageCatalog } from '../../utils/permissions'
import { api, unwrapResponse } from '../../services/api'
import { formatMoney } from '../../utils/format'
import { cn } from '../../utils/cn'
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
import { Autocomplete } from '../../components/ui/Autocomplete'
import { Plus, Trash2 } from 'lucide-react'

type CatalogTab = 'items' | 'categories' | 'variants'

type ItemType = 'product' | 'service'

interface CategoryRow {
  id: number
  name: string
  is_active: boolean
}

interface KitItemRow {
  id: number
  source_type: 'item' | 'variant'
  item_id?: number | null
  variant_id?: number | null
  default_item_id?: number | null
  item_name?: string | null
  variant_name?: string | null
  default_item_name?: string | null
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
   // When true, this kit can have its inventory components overridden per sale (uniform kits)
  is_editable_components?: boolean
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

interface VariantGroupItemRow {
  id: number
  name: string
  sku_code: string
}

interface VariantRow {
  id: number
  name: string
  is_active: boolean
  items: VariantGroupItemRow[]
}

const itemTypeOptions: { label: string; value: ItemType }[] = [
  { label: 'Product', value: 'product' },
  { label: 'Service', value: 'service' },
]

const tabConfig: { key: CatalogTab; label: string; path: string }[] = [
  { key: 'items', label: 'Items', path: '/billing/catalog/items' },
  { key: 'categories', label: 'Categories', path: '/billing/catalog/categories' },
  { key: 'variants', label: 'Variants', path: '/billing/catalog/variants' },
]

const emptyKitForm = {
  name: '',
  category_id: '',
  item_type: 'product' as ItemType,
  price: '',
  is_editable_components: false,
  items: [{ source_type: 'item' as 'item' | 'variant', item_id: '', variant_id: '', default_item_id: '', quantity: 1 }],
}

const emptyCategoryForm = { name: '' }
const emptyVariantForm = { name: '', item_ids: [] as number[] }

export const CatalogPage = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canEdit = canManageCatalog(user)
  const readOnly = !canEdit

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

  const [variantDialogOpen, setVariantDialogOpen] = useState(false)
  const [editingVariant, setEditingVariant] = useState<VariantRow | null>(null)
  const [variantForm, setVariantForm] = useState({ ...emptyVariantForm })

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
  const variantsApi = useApi<VariantRow[]>('/items/variants')
  const kitMutation = useApiMutation<unknown>()
  const categoryMutation = useApiMutation<CategoryRow | unknown>()
  const toggleMutation = useApiMutation<unknown>()
  const variantMutation = useApiMutation<unknown>()

  const categories = categoriesApi.data ?? []
  const kits = useMemo(
    () => (kitsApi.data ?? []).filter((kit) => kit.price_type === 'standard'),
    [kitsApi.data]
  )
  const inventoryItems = inventoryApi.data ?? []
  const variants = variantsApi.data ?? []
  const tabError =
    categoriesApi.error ??
    kitsApi.error ??
    inventoryApi.error ??
    variantsApi.error ??
    kitMutation.error ??
    categoryMutation.error ??
    toggleMutation.error ??
    variantMutation.error
  const loading =
    categoriesApi.loading ||
    categoryMutation.loading ||
    kitMutation.loading ||
    toggleMutation.loading ||
    variantMutation.loading
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

  const buildKitFormFromKit = (kit: KitRow) => ({
      name: kit.name,
      category_id: String(kit.category_id),
      item_type: kit.item_type,
      price: kit.price?.toString() ?? '',
      is_editable_components: Boolean(kit.is_editable_components),
      items:
        kit.item_type === 'product' && kit.items.length
          ? kit.items.map((item) => ({
              source_type: item.source_type as 'item' | 'variant',
              item_id: item.item_id ? String(item.item_id) : '',
              variant_id: item.variant_id ? String(item.variant_id) : '',
              default_item_id: item.default_item_id ? String(item.default_item_id) : '',
              quantity: item.quantity,
            }))
          : [{ source_type: 'item' as 'item' | 'variant', item_id: '', variant_id: '', default_item_id: '', quantity: 1 }],
  })

  const openCreateKit = () => {
    setEditingKit(null)
    setKitForm({ ...emptyKitForm })
    setKitDialogOpen(true)
  }

  const openEditKit = (kit: KitRow) => {
    setEditingKit(kit)
    setKitForm(buildKitFormFromKit(kit))
    setKitDialogOpen(true)
  }

  const openCopyKit = (kit: KitRow) => {
    // Create a new kit prefilled from the selected one (no editingKit → POST)
    setEditingKit(null)
    setKitForm(buildKitFormFromKit(kit))
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
            .filter((item) => 
              (item.source_type === 'item' && item.item_id) ||
              (item.source_type === 'variant' && item.variant_id && item.default_item_id)
            )
            .map((item) => {
              if (item.source_type === 'item') {
                return {
                  source_type: 'item' as const,
                  item_id: Number(item.item_id),
                  quantity: item.quantity,
                }
              } else {
                return {
                  source_type: 'variant' as const,
                  variant_id: Number(item.variant_id),
                  default_item_id: Number(item.default_item_id),
                  quantity: item.quantity,
                }
              }
            })
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
              is_editable_components: Boolean(kitForm.is_editable_components),
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
              is_editable_components: Boolean(kitForm.is_editable_components),
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

  const openCreateVariant = () => {
    setEditingVariant(null)
    setVariantForm({ ...emptyVariantForm })
    setVariantDialogOpen(true)
  }

  const openEditVariant = (variant: VariantRow) => {
    setEditingVariant(variant)
    setVariantForm({
      name: variant.name,
      item_ids: variant.items.map((i) => i.id),
    })
    setVariantDialogOpen(true)
  }

  const resetVariantDialog = () => {
    setVariantDialogOpen(false)
    setEditingVariant(null)
    setVariantForm({ ...emptyVariantForm })
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

  const submitVariant = async () => {
    if (!variantForm.name.trim()) {
      setValidationError('Enter a variant name.')
      return
    }
    setValidationError(null)
    variantMutation.reset()

    const payload = {
      name: variantForm.name.trim(),
      item_ids: variantForm.item_ids,
    }

    const ok = editingVariant
      ? await variantMutation.execute(() =>
          api
            .patch(`/items/variants/${editingVariant.id}`, payload)
            .then((r) => ({ data: { data: unwrapResponse(r) } }))
        )
      : await variantMutation.execute(() =>
          api
            .post('/items/variants', payload)
            .then((r) => ({ data: { data: unwrapResponse(r) } }))
        )

    if (ok != null) {
      resetVariantDialog()
      variantsApi.refetch()
    }
  }

  const toggleItemInVariant = (itemId: number) => {
    setVariantForm((prev: typeof emptyVariantForm) => {
      const exists = prev.item_ids.includes(itemId)
      return {
        ...prev,
        item_ids: exists
          ? prev.item_ids.filter((id: number) => id !== itemId)
          : [...prev.item_ids, itemId],
      }
    })
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

  const updateKitItem = (index: number, field: 'source_type' | 'item_id' | 'variant_id' | 'default_item_id' | 'quantity', value: string | number) => {
    setKitForm((prev) => {
      const nextItems = [...prev.items]
      const item = { ...nextItems[index] }
      if (field === 'quantity') {
        const nextValue = Number(value)
        item.quantity = Number.isNaN(nextValue) || nextValue < 1 ? 1 : nextValue
      } else if (field === 'source_type') {
        item.source_type = value as 'item' | 'variant'
        // Reset fields when switching source_type
        if (value === 'item') {
          item.variant_id = ''
          item.default_item_id = ''
        } else {
          item.item_id = ''
        }
      } else {
        item[field] = value as string
      }
      nextItems[index] = item
      return { ...prev, items: nextItems }
    })
  }

  const removeKitItem = (index: number) => {
    setKitForm((prev) => {
      const nextItems = prev.items.filter((_, idx) => idx !== index)
      return { ...prev, items: nextItems.length ? nextItems : [{ source_type: 'item' as 'item' | 'variant', item_id: '', variant_id: '', default_item_id: '', quantity: 1 }] }
    })
  }

  const addKitItem = (sourceType: 'item' | 'variant') => {
    setKitForm((prev) => ({
      ...prev,
      items: [
        ...prev.items,
        {
          source_type: sourceType,
          item_id: '',
          variant_id: '',
          default_item_id: '',
          quantity: 1,
        },
      ],
    }))
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">
        Catalog
      </Typography>

      <Tabs value={activeTab} onChange={(value) => handleTabChange(value as CatalogTab)}>
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

          <div className="flex flex-wrap items-end gap-4 mt-4">
            <Input
              containerClassName="w-[240px] min-w-[200px]"
              label="Search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Select
              containerClassName="w-[260px] min-w-[200px]"
              value={categoryFilter === 'all' ? 'all' : String(categoryFilter)}
              onChange={(event) => {
                const value = event.target.value
                setCategoryFilter(value === 'all' ? 'all' : Number(value))
              }}
              label="Category"
            >
              <option value="all">All</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
            <Select
              containerClassName="w-[200px] min-w-[180px]"
              value={typeFilter === 'all' ? 'all' : typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as ItemType | 'all')}
              label="Type"
            >
              <option value="all">All</option>
              {itemTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Switch
              containerClassName="self-end whitespace-nowrap pb-1"
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
              label="Show inactive"
            />
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
                        <Button size="small" variant="outlined" onClick={() => openEditKit(kit)}>
                          View
                        </Button>
                      ) : (
                        <>
                          <Button size="small" variant="outlined" onClick={() => openEditKit(kit)}>
                            Edit
                          </Button>
                          <Button size="small" variant="outlined" onClick={() => openCopyKit(kit)}>
                            Copy
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color={kit.is_active ? 'error' : 'success'}
                            onClick={() => requestToggleKitActive(kit)}
                          >
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
                  <td colSpan={6} className="px-4 py-3 text-center">
                    No catalog items found
                  </td>
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
                        <Button size="small" variant="outlined" onClick={() => openEditCategory(category)}>
                          Edit
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color={category.is_active ? 'error' : 'success'}
                          onClick={() => requestToggleCategoryActive(category)}
                        >
                          {category.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {loading && (
                <TableRow>
                  <td colSpan={3} className="px-4 py-3 text-center">
                    <Spinner size="small" />
                  </td>
                </TableRow>
              )}
              {!categories.length && !loading && (
                <TableRow>
                  <td colSpan={3} className="px-4 py-3 text-center">
                    No categories found
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabPanel>

        <TabPanel value="variants">
          <div className="flex items-center justify-between mt-4">
            <Typography variant="h6" className="font-semibold">
              Variant groups
            </Typography>
            {!readOnly && (
              <Button variant="contained" onClick={openCreateVariant}>
                New variant group
              </Button>
            )}
          </div>

          <Table className="mt-4">
            <TableHead>
              <TableRow>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Items</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {variants.map((variant) => (
                <TableRow key={variant.id}>
                  <TableCell>{variant.name}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {variant.items.map((item) => (
                        <Chip key={item.id} size="small" label={`${item.name} (${item.sku_code})`} />
                      ))}
                      {!variant.items.length && (
                        <Typography variant="body2" color="secondary">
                          No items
                        </Typography>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={variant.is_active ? 'Active' : 'Inactive'}
                      color={variant.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell align="right">
                    {!readOnly && (
                      <div className="flex gap-2 justify-end">
                        <Button size="small" variant="outlined" onClick={() => openEditVariant(variant)}>
                          Edit
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {variantsApi.loading && (
                <TableRow>
                  <td colSpan={4} className="px-4 py-3 text-center">
                    <Spinner size="small" />
                  </td>
                </TableRow>
              )}
              {!variants.length && !variantsApi.loading && (
                <TableRow>
                  <td colSpan={4} className="px-4 py-3 text-center">
                    No variant groups found
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabPanel>
      </Tabs>

      <Dialog open={kitDialogOpen} onClose={resetKitDialog} maxWidth="lg">
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
                  + Add new category
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
              <div className="grid gap-3">
                <Typography variant="subtitle1" className="font-semibold">
                  Components
                </Typography>
                {kitForm.items.map((item, index) => (
                  <div
                    key={`kit-item-${index}`}
                    className="rounded-xl border border-slate-200 bg-white p-3"
                  >
                    <div className={cn('flex flex-wrap items-end gap-3', !readOnly && 'pr-2')}>
                      <div className="w-[160px] min-w-[160px]">
                        <Select
                          value={item.source_type}
                          onChange={(event) => updateKitItem(index, 'source_type', event.target.value)}
                          label="Source type"
                          disabled={readOnly}
                        >
                          <option value="item">Inventory item</option>
                          <option value="variant">Variant</option>
                        </Select>
                      </div>
                      {item.source_type === 'item' ? (
                        <div className="flex-1 min-w-[260px]">
                          <Autocomplete
                            options={inventoryItems}
                            getOptionLabel={(invItem) => `${invItem.name} (${invItem.sku_code})`}
                            getOptionValue={(invItem) => invItem.id}
                            value={inventoryItems.find((invItem) => String(invItem.id) === String(item.item_id)) || null}
                            onChange={(invItem) => {
                              if (invItem) {
                                updateKitItem(index, 'item_id', String(invItem.id))
                              } else {
                                updateKitItem(index, 'item_id', '')
                              }
                            }}
                            label="Inventory item"
                            placeholder="Type to search items..."
                            disabled={readOnly}
                          />
                        </div>
                      ) : (
                        <div className="flex-1 min-w-[320px] grid gap-3 sm:grid-cols-2">
                          <Autocomplete
                            options={variants}
                            getOptionLabel={(variant) => variant.name}
                            getOptionValue={(variant) => variant.id}
                            value={variants.find((v) => String(v.id) === String(item.variant_id)) || null}
                            onChange={(variant) => {
                              if (variant) {
                                updateKitItem(index, 'variant_id', String(variant.id))
                              } else {
                                updateKitItem(index, 'variant_id', '')
                                updateKitItem(index, 'default_item_id', '')
                              }
                            }}
                            label="Variant group"
                            placeholder="Type to search variants..."
                            disabled={readOnly}
                          />
                          <Autocomplete
                            options={variants.find((v) => String(v.id) === String(item.variant_id))?.items || []}
                            getOptionLabel={(variantItem) => `${variantItem.name} (${variantItem.sku_code})`}
                            getOptionValue={(variantItem) => variantItem.id}
                            value={variants
                              .find((v) => String(v.id) === String(item.variant_id))
                              ?.items.find((vi) => String(vi.id) === String(item.default_item_id)) || null}
                            onChange={(variantItem) => {
                              if (variantItem) {
                                updateKitItem(index, 'default_item_id', String(variantItem.id))
                              } else {
                                updateKitItem(index, 'default_item_id', '')
                              }
                            }}
                            label="Default item"
                            placeholder={item.variant_id ? 'Type to search items...' : 'Select variant group first'}
                            disabled={readOnly || !item.variant_id}
                          />
                        </div>
                      )}
                      <div className="w-[140px] min-w-[140px]">
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
                      </div>
                      {!readOnly && (
                        <button
                          type="button"
                          onClick={() => removeKitItem(index)}
                          className="p-2 hover:bg-slate-100 rounded-lg transition-colors self-end"
                          aria-label="Remove component"
                        >
                          <Trash2 className="w-5 h-5 text-slate-500" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {!readOnly && (
                  <div className="flex gap-2 flex-wrap self-start">
                    <Button variant="outlined" onClick={() => addKitItem('item')}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add item
                    </Button>
                    <Button variant="outlined" onClick={() => addKitItem('variant')}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add variant
                    </Button>
                  </div>
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

      <Dialog open={variantDialogOpen} onClose={resetVariantDialog} fullWidth maxWidth="md">
        <DialogTitle>{editingVariant ? 'Edit variant group' : 'Create variant group'}</DialogTitle>
        <DialogContent className="space-y-4">
          <Input
            label="Name"
            value={variantForm.name}
            onChange={(event) => setVariantForm({ ...variantForm, name: event.target.value })}
            required
          />
          <div className="mt-2">
            <Typography variant="subtitle1" className="font-semibold mb-2">
              Items in this group
            </Typography>
            <div className="max-h-[280px] overflow-y-auto border border-slate-200 rounded-lg p-2">
              {inventoryItems.map((item) => {
                const checked = variantForm.item_ids.includes(item.id)
                return (
                  <div
                    key={item.id}
                    className="flex items-center justify-between py-1"
                  >
                    <div>
                      <Typography variant="body2">
                        {item.name} · {item.sku_code}
                      </Typography>
                      <Typography variant="caption" color="secondary">
                        {item.category_name ?? 'No category'}
                      </Typography>
                    </div>
                    <Button
                      size="small"
                      variant={checked ? 'contained' : 'outlined'}
                      onClick={() => toggleItemInVariant(item.id)}
                    >
                      {checked ? 'Remove' : 'Add'}
                    </Button>
                  </div>
                )
              })}
              {!inventoryItems.length && (
                <Typography variant="body2" color="secondary">
                  No inventory items found.
                </Typography>
              )}
            </div>
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={resetVariantDialog}>Cancel</Button>
          {!readOnly && (
            <Button variant="contained" onClick={submitVariant} disabled={loading}>
              Save
            </Button>
          )}
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
