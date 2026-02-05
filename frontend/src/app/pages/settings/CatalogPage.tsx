import AddIcon from '@mui/icons-material/Add'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
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
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { isAccountant } from '../../utils/permissions'
import { api, unwrapResponse } from '../../services/api'
import { formatMoney } from '../../utils/format'

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

const TabPanel = ({
  active,
  name,
  children,
}: {
  active: CatalogTab
  name: CatalogTab
  children: React.ReactNode
}) => {
  if (active !== name) {
    return null
  }
  return <Box sx={{ mt: 3 }}>{children}</Box>
}

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

  const handleTabChange = (_: React.SyntheticEvent, value: CatalogTab) => {
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
    setVariantForm((prev) => {
      const exists = prev.item_ids.includes(itemId)
      return {
        ...prev,
        item_ids: exists
          ? prev.item_ids.filter((id) => id !== itemId)
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

  const addKitItem = () => {
    setKitForm((prev) => ({
      ...prev,
      items: [...prev.items, { source_type: 'item' as 'item' | 'variant', item_id: '', variant_id: '', default_item_id: '', quantity: 1 }],
    }))
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Catalog
      </Typography>

      <Tabs value={activeTab} onChange={handleTabChange}>
        {tabConfig.map((tab) => (
          <Tab key={tab.key} label={tab.label} value={tab.key} />
        ))}
      </Tabs>

      {displayTabError ? (
        <Alert severity="error" sx={{ mt: 2 }}>
          {displayTabError}
        </Alert>
      ) : null}

      <TabPanel active={activeTab} name="items">
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Catalog items
          </Typography>
          {!readOnly && (
            <Button variant="contained" onClick={openCreateKit}>
              New item
            </Button>
          )}
        </Box>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mt: 2 }}>
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
              onChange={(event) => {
                const value = event.target.value
                setCategoryFilter(value === 'all' ? 'all' : Number(value))
              }}
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
            <InputLabel>Type</InputLabel>
            <Select
              value={typeFilter}
              label="Type"
              onChange={(event) => setTypeFilter(event.target.value as ItemType | 'all')}
            >
              <MenuItem value="all">All</MenuItem>
              {itemTypeOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControlLabel
            control={
              <Switch
                checked={showInactive}
                onChange={(event) => setShowInactive(event.target.checked)}
              />
            }
            label="Show inactive"
          />
        </Box>

        <Table sx={{ mt: 2 }}>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Category</TableCell>
              <TableCell>Price</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
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
                  {readOnly ? (
                    <Button size="small" onClick={() => openEditKit(kit)}>
                      View
                    </Button>
                  ) : (
                    <>
                      <Button size="small" onClick={() => openEditKit(kit)}>
                        Edit
                      </Button>
                      <Button size="small" startIcon={<ContentCopyIcon fontSize="small" />} onClick={() => openCopyKit(kit)}>
                        Copy
                      </Button>
                      <Button size="small" onClick={() => requestToggleKitActive(kit)}>
                        {kit.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!filteredKits.length && !kitsLoading ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No catalog items found
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TabPanel>

      <TabPanel active={activeTab} name="categories">
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Categories
          </Typography>
          {!readOnly && (
            <Button variant="contained" onClick={openCreateCategory}>
              New category
            </Button>
          )}
        </Box>

        <Table sx={{ mt: 2 }}>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
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
                    <>
                      <Button size="small" onClick={() => openEditCategory(category)}>
                        Edit
                      </Button>
                      <Button size="small" onClick={() => requestToggleCategoryActive(category)}>
                        {category.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {loading ? (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : null}
            {!categories.length && !loading ? (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  No categories found
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TabPanel>

      <TabPanel active={activeTab} name="variants">
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Variants
          </Typography>
          {!readOnly && (
            <Button variant="contained" onClick={openCreateVariant}>
              New variant
            </Button>
          )}
        </Box>

        <Table sx={{ mt: 2 }}>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Items</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {variants.map((variant) => (
              <TableRow key={variant.id}>
                <TableCell>{variant.name}</TableCell>
                <TableCell>
                  {variant.items.length
                    ? variant.items.map((item) => item.sku_code).join(', ')
                    : 'No items'}
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
                    <Button size="small" onClick={() => openEditVariant(variant)}>
                      Edit
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!variants.length && !loading ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  No variants found
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TabPanel>


      <Dialog open={kitDialogOpen} onClose={resetKitDialog} fullWidth maxWidth="md">
        <DialogTitle>
          {readOnly && editingKit ? 'View item' : editingKit ? 'Edit item' : 'Create item'}
        </DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Name"
            value={kitForm.name}
            onChange={(event) => setKitForm({ ...kitForm, name: event.target.value })}
            fullWidth
            required
            disabled={readOnly}
          />
          <FormControl fullWidth disabled={readOnly}>
            <InputLabel>Category</InputLabel>
            <Select
              value={kitForm.category_id}
              label="Category"
              onChange={(event) => handleCategorySelect(event.target.value as number | string)}
            >
              {categories.map((category) => (
                <MenuItem key={category.id} value={category.id}>
                  {category.name}
                </MenuItem>
              ))}
              {!readOnly && (
                <MenuItem value="create">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AddIcon fontSize="small" />
                    Add new category
                  </Box>
                </MenuItem>
              )}
            </Select>
          </FormControl>
          <FormControl fullWidth disabled={!!editingKit || readOnly}>
            <InputLabel>Type</InputLabel>
            <Select
              value={kitForm.item_type}
              label="Type"
              onChange={(event) =>
                setKitForm({
                  ...kitForm,
                  item_type: event.target.value as ItemType,
                })
              }
            >
              {itemTypeOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Price"
            type="number"
            value={kitForm.price}
            onChange={(event) => setKitForm({ ...kitForm, price: event.target.value })}
            fullWidth
            required
            disabled={readOnly}
            inputProps={{ min: 0, step: 0.01 }}
          />

          <FormControlLabel
            control={
              <Switch
                checked={Boolean(kitForm.is_editable_components)}
                onChange={(event) =>
                  setKitForm((prev) => ({
                    ...prev,
                    is_editable_components: event.target.checked,
                  }))
                }
                disabled={readOnly}
              />
            }
            label="Allow configuring components per sale (uniform kit)"
          />

          {kitForm.item_type === 'product' ? (
            <Box sx={{ display: 'grid', gap: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                Components
              </Typography>
              {kitForm.items.map((item, index) => (
                <Box key={`kit-item-${index}`} sx={{ display: 'grid', gap: 1, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                  <FormControl fullWidth disabled={readOnly}>
                    <InputLabel>Source type</InputLabel>
                    <Select
                      value={item.source_type}
                      label="Source type"
                      onChange={(event) =>
                        updateKitItem(index, 'source_type', event.target.value as 'item' | 'variant')
                      }
                    >
                      <MenuItem value="item">Inventory item</MenuItem>
                      <MenuItem value="variant">Variant</MenuItem>
                    </Select>
                  </FormControl>
                  {item.source_type === 'item' ? (
                    <FormControl fullWidth disabled={readOnly}>
                      <InputLabel>Inventory item</InputLabel>
                      <Select
                        value={item.item_id}
                        label="Inventory item"
                        onChange={(event) =>
                          updateKitItem(index, 'item_id', event.target.value as string)
                        }
                      >
                        {inventoryItems.map((option) => (
                          <MenuItem key={option.id} value={option.id}>
                            {option.name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : (
                    <>
                      <FormControl fullWidth disabled={readOnly}>
                        <InputLabel>Variant</InputLabel>
                        <Select
                          value={item.variant_id}
                          label="Variant"
                          onChange={(event) => {
                            updateKitItem(index, 'variant_id', event.target.value as string)
                            updateKitItem(index, 'default_item_id', '') // Reset default_item when variant changes
                          }}
                        >
                          {variants.filter(v => v.is_active).map((variant) => (
                            <MenuItem key={variant.id} value={variant.id}>
                              {variant.name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl fullWidth disabled={readOnly || !item.variant_id}>
                        <InputLabel>Default item</InputLabel>
                        <Select
                          value={item.default_item_id}
                          label="Default item"
                          onChange={(event) =>
                            updateKitItem(index, 'default_item_id', event.target.value as string)
                          }
                        >
                          {variants.find(v => v.id === Number(item.variant_id))?.items.map((variantItem) => (
                            <MenuItem key={variantItem.id} value={variantItem.id}>
                              {variantItem.name} ({variantItem.sku_code})
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </>
                  )}
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <TextField
                      label="Qty"
                      type="number"
                      value={item.quantity}
                      onChange={(event) => updateKitItem(index, 'quantity', event.target.value)}
                      onFocus={(event) => event.currentTarget.select()}
                      disabled={readOnly}
                      inputProps={{ min: 1, step: 1 }}
                      sx={{ flex: 1 }}
                    />
                    {!readOnly && (
                      <IconButton onClick={() => removeKitItem(index)} aria-label="Remove component">
                        <DeleteOutlineIcon />
                      </IconButton>
                    )}
                  </Box>
                </Box>
              ))}
              {!readOnly && (
                <Button variant="outlined" onClick={addKitItem} sx={{ alignSelf: 'flex-start' }}>
                  Add component
                </Button>
              )}
            </Box>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={resetKitDialog}>{readOnly ? 'Close' : 'Cancel'}</Button>
          {!readOnly && (
            <Button variant="contained" onClick={submitKit} disabled={loading}>
              Save
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={categoryDialogOpen} onClose={resetCategoryDialog} fullWidth maxWidth="sm">
        <DialogTitle>{editingCategory ? 'Edit category' : 'Create category'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Name"
            value={categoryForm.name}
            onChange={(event) => setCategoryForm({ name: event.target.value })}
            fullWidth
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={resetCategoryDialog}>Cancel</Button>
          <Button variant="contained" onClick={submitCategory} disabled={loading}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={variantDialogOpen} onClose={resetVariantDialog} fullWidth maxWidth="md">
        <DialogTitle>{editingVariant ? 'Edit variant group' : 'Create variant group'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Name"
            value={variantForm.name}
            onChange={(event) => setVariantForm({ ...variantForm, name: event.target.value })}
            fullWidth
            required
          />
          <Box sx={{ mt: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
              Items in this group
            </Typography>
            <Box sx={{ maxHeight: 280, overflowY: 'auto', border: '1px solid #eee', borderRadius: 1, p: 1 }}>
              {inventoryItems.map((item) => {
                const checked = variantForm.item_ids.includes(item.id)
                return (
                  <Box
                    key={item.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      py: 0.5,
                    }}
                  >
                    <Box>
                      <Typography variant="body2">
                        {item.name} · {item.sku_code}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {item.category_name ?? 'No category'}
                      </Typography>
                    </Box>
                    <Button
                      size="small"
                      variant={checked ? 'contained' : 'outlined'}
                      onClick={() => toggleItemInVariant(item.id)}
                    >
                      {checked ? 'Remove' : 'Add'}
                    </Button>
                  </Box>
                )
              })}
              {!inventoryItems.length ? (
                <Typography variant="body2" color="text.secondary">
                  No inventory items found.
                </Typography>
              ) : null}
            </Box>
          </Box>
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
    </Box>
  )
}
