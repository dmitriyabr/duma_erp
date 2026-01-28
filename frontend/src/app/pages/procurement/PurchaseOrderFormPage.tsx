import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PurposeRow {
  id: number
  name: string
}

interface InventoryItemRow {
  id: number
  name: string
  sku_code: string
  category_id: number
  category_name?: string | null
}

interface CategoryRow {
  id: number
  name: string
}

interface POLineDraft {
  id: string
  item_id: number | null
  description: string
  quantity_expected: number
  unit_price: number
  line_type: 'inventory' | 'new_item' | 'custom'
  newItemCategoryId?: number | null
  newItemName?: string
  newItemSku?: string
}

interface POResponse {
  id: number
  po_number: string
  supplier_name: string
  supplier_contact: string | null
  purpose_id: number
  status: string
  order_date: string
  expected_delivery_date: string | null
  track_to_warehouse: boolean
  notes: string | null
  lines: Array<{
    id: number
    item_id: number | null
    description: string
    quantity_expected: number
    quantity_received: number
    unit_price: number
    line_total: number
  }>
}

const getDefaultOrderDate = () => {
  return new Date().toISOString().slice(0, 10)
}

const emptyLine = (): POLineDraft => ({
  id: `${Date.now()}-${Math.random()}`,
  item_id: null,
  description: '',
  quantity_expected: 1,
  unit_price: 0,
  line_type: 'inventory',
})

export const PurchaseOrderFormPage = () => {
  const { orderId } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(orderId)
  const resolvedId = orderId ? Number(orderId) : null

  const [supplierName, setSupplierName] = useState('')
  const [supplierContact, setSupplierContact] = useState('')
  const [purposeId, setPurposeId] = useState<number | ''>('')
  const [orderDate, setOrderDate] = useState(getDefaultOrderDate())
  const [expectedDeliveryDate, setExpectedDeliveryDate] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<POLineDraft[]>([emptyLine()])

  const [purposes, setPurposes] = useState<PurposeRow[]>([])
  const [inventoryItems, setInventoryItems] = useState<InventoryItemRow[]>([])
  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newItemDialogOpen, setNewItemDialogOpen] = useState(false)
  const [newItemCategoryId, setNewItemCategoryId] = useState<number | ''>('')
  const [newItemName, setNewItemName] = useState('')
  const [newItemSku, setNewItemSku] = useState('')
  const [currentLineForNewItem, setCurrentLineForNewItem] = useState<POLineDraft | null>(null)

  const [newPurposeDialogOpen, setNewPurposeDialogOpen] = useState(false)
  const [newPurposeName, setNewPurposeName] = useState('')

  const [bulkCsvLoading, setBulkCsvLoading] = useState(false)
  const [bulkCsvErrors, setBulkCsvErrors] = useState<Array<{ row: number; message: string }>>([])
  const bulkCsvInputRef = useRef<HTMLInputElement>(null)

  const loadReferenceData = useCallback(async () => {
    try {
      const [purposesResponse, itemsResponse, categoriesResponse] = await Promise.all([
        api.get<ApiResponse<PurposeRow[]>>('/procurement/payment-purposes', {
          params: { include_inactive: true },
        }),
        api.get<ApiResponse<InventoryItemRow[]>>('/items', {
          params: { item_type: 'product', include_inactive: false },
        }),
        api.get<ApiResponse<CategoryRow[]>>('/items/categories', {
          params: { include_inactive: true },
        }),
      ])
      setPurposes(purposesResponse.data.data)
      setInventoryItems(itemsResponse.data.data)
      setCategories(categoriesResponse.data.data)
    } catch {
      setError('Failed to load reference data.')
    }
  }, [])

  const loadOrder = useCallback(async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<POResponse>>(`/procurement/purchase-orders/${resolvedId}`)
      const po = response.data.data
      setSupplierName(po.supplier_name)
      setSupplierContact(po.supplier_contact ?? '')
      setPurposeId(po.purpose_id)
      setOrderDate(po.order_date)
      setExpectedDeliveryDate(po.expected_delivery_date ?? '')
      setNotes(po.notes ?? '')
      setLines(
        po.lines.map((line) => ({
          id: `${line.id}`,
          item_id: line.item_id,
          description: line.description,
          quantity_expected: line.quantity_expected,
          unit_price: Number(line.unit_price),
          line_type: line.item_id ? 'inventory' : 'custom',
        }))
      )
    } catch {
      setError('Failed to load purchase order.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  useEffect(() => {
    loadReferenceData()
    if (isEdit) {
      loadOrder()
    }
  }, [isEdit, loadReferenceData, loadOrder])

  const trackToWarehouse = useMemo(() => {
    return lines.some((line) => line.item_id !== null)
  }, [lines])

  const updateLine = (lineId: string, updates: Partial<POLineDraft>) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? { ...line, ...updates } : line)))
  }

  const removeLine = (lineId: string) => {
    setLines((prev) => prev.filter((line) => line.id !== lineId))
  }

  const addLine = (type: 'inventory' | 'new_item' | 'custom') => {
    const newLine = emptyLine()
    newLine.line_type = type
    if (type === 'custom') {
      newLine.item_id = null
    }
    setLines((prev) => [...prev, newLine])
  }

  const openNewItemDialog = (line: POLineDraft) => {
    setCurrentLineForNewItem(line)
    setNewItemCategoryId('')
    setNewItemName('')
    setNewItemSku('')
    setNewItemDialogOpen(true)
  }

  const handlePurposeSelect = (value: number | string) => {
    if (value === 'create') {
      setNewPurposeName('')
      setNewPurposeDialogOpen(true)
      return
    }
    setPurposeId(Number(value))
  }

  const createNewPurpose = async () => {
    if (!newPurposeName.trim()) {
      setError('Enter purpose name.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await api.post<ApiResponse<PurposeRow>>('/procurement/payment-purposes', {
        name: newPurposeName.trim(),
      })
      // Перезагружаем весь список, чтобы получить актуальные данные
      await loadReferenceData()
      const newPurpose = response.data.data
      setPurposeId(newPurpose.id)
      setNewPurposeDialogOpen(false)
      setNewPurposeName('')
    } catch {
      setError('Failed to create purpose.')
    } finally {
      setLoading(false)
    }
  }

  const createNewItemAndAssign = async () => {
    if (!currentLineForNewItem || !newItemCategoryId || !newItemName.trim()) {
      setError('Fill category and name for new item.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const category = categories.find((c) => c.id === Number(newItemCategoryId))
      if (!category) {
        setError('Category not found.')
        setLoading(false)
        return
      }
      const skuPrefix = category.name.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6) || 'CAT'
      const existingItems = inventoryItems.filter((item) => item.sku_code.startsWith(skuPrefix))
      const maxNum = existingItems.reduce((max, item) => {
        const match = item.sku_code.match(new RegExp(`^${skuPrefix}-(\\d{6})$`))
        if (match) {
          const num = Number(match[1])
          return Math.max(max, num)
        }
        return max
      }, 0)
      const newSku = `${skuPrefix}-${String(maxNum + 1).padStart(6, '0')}`

      const response = await api.post<ApiResponse<{ id: number }>>('/items', {
        category_id: Number(newItemCategoryId),
        sku_code: newSku,
        name: newItemName.trim(),
        item_type: 'product',
        price_type: 'standard',
        price: 0,
      })

      const newItem: InventoryItemRow = {
        id: response.data.data.id,
        name: newItemName.trim(),
        sku_code: newSku,
        category_id: Number(newItemCategoryId),
        category_name: category.name,
      }
      setInventoryItems((prev) => [...prev, newItem])
      updateLine(currentLineForNewItem.id, {
        item_id: newItem.id,
        description: newItem.name,
        line_type: 'inventory',
      })
      setNewItemDialogOpen(false)
    } catch {
      setError('Failed to create item.')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!supplierName.trim() || !purposeId) {
      setError('Fill supplier name and purpose.')
      return
    }
    if (!lines.length) {
      setError('Add at least one line.')
      return
    }
    const invalidLine = lines.find((line) => {
      if (!line.description.trim()) return true
      if (line.quantity_expected <= 0) return true
      if (line.unit_price < 0) return true
      return false
    })
    if (invalidLine) {
      setError('All lines must have description, quantity > 0, and price >= 0.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const payload = {
        supplier_name: supplierName.trim(),
        supplier_contact: supplierContact.trim() || null,
        purpose_id: Number(purposeId),
        order_date: orderDate || null,
        expected_delivery_date: expectedDeliveryDate || null,
        track_to_warehouse: trackToWarehouse,
        notes: notes.trim() || null,
        lines: lines.map((line) => ({
          item_id: line.item_id,
          description: line.description.trim(),
          quantity_expected: line.quantity_expected,
          unit_price: line.unit_price,
        })),
      }

      if (isEdit && resolvedId) {
        await api.put(`/procurement/purchase-orders/${resolvedId}`, payload)
      } else {
        await api.post('/procurement/purchase-orders', payload)
      }
      navigate('/procurement/orders')
    } catch {
      setError('Failed to save purchase order.')
    } finally {
      setLoading(false)
    }
  }

  const totalExpected = useMemo(() => {
    return lines.reduce((sum, line) => sum + line.quantity_expected * line.unit_price, 0)
  }, [lines])

  const downloadLinesTemplate = async () => {
    setError(null)
    try {
      const response = await api.get('/procurement/purchase-orders/bulk-upload/template', {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'po_lines_template.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('Failed to download template.')
    }
  }

  const uploadLinesCsv = async () => {
    const file = bulkCsvInputRef.current?.files?.[0]
    if (!file) {
      setError('Select a CSV file.')
      return
    }
    setBulkCsvLoading(true)
    setError(null)
    setBulkCsvErrors([])
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await api.post<ApiResponse<{ lines: Array<{ item_id: number | null; description: string; quantity_expected: number; unit_price: number }>; errors: Array<{ row: number; message: string }> }>>(
        '/procurement/purchase-orders/bulk-upload/parse-lines',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      const { lines: parsedLines, errors: parseErrors } = response.data.data
      setBulkCsvErrors(parseErrors)
      if (parsedLines.length > 0) {
        const newLines: POLineDraft[] = parsedLines.map((line) => ({
          id: `${Date.now()}-${Math.random()}`,
          item_id: line.item_id,
          description: line.description,
          quantity_expected: line.quantity_expected,
          unit_price: line.unit_price,
          line_type: line.item_id ? 'inventory' : 'custom',
        }))
        setLines(newLines)
      }
      if (bulkCsvInputRef.current) bulkCsvInputRef.current.value = ''
    } catch (e: unknown) {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null
      setError(msg ?? 'Failed to parse CSV.')
    } finally {
      setBulkCsvLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        {isEdit ? 'Edit purchase order' : 'New purchase order'}
      </Typography>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gap: 2, maxWidth: 600, mb: 3 }}>
        <TextField
          label="Supplier name"
          value={supplierName}
          onChange={(event) => setSupplierName(event.target.value)}
          required
        />
        <TextField
          label="Supplier contact"
          value={supplierContact}
          onChange={(event) => setSupplierContact(event.target.value)}
        />
        <FormControl required>
          <InputLabel>Category / Purpose</InputLabel>
          <Select
            value={purposeId}
            label="Category / Purpose"
            onChange={(event) => handlePurposeSelect(event.target.value)}
          >
            {purposes.map((purpose) => (
              <MenuItem key={purpose.id} value={purpose.id}>
                {purpose.name}
              </MenuItem>
            ))}
            <MenuItem value="create" sx={{ fontStyle: 'italic', color: 'primary.main' }}>
              + Add new category
            </MenuItem>
          </Select>
        </FormControl>
        <TextField
          label="Order date"
          type="date"
          value={orderDate}
          onChange={(event) => setOrderDate(event.target.value)}
          InputLabelProps={{ shrink: true }}
          required
        />
        <TextField
          label="Expected delivery date"
          type="date"
          value={expectedDeliveryDate}
          onChange={(event) => setExpectedDeliveryDate(event.target.value)}
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          label="Notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          multiline
          minRows={2}
        />
      </Box>

      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 1 }}>
          <Typography variant="h6">Order lines</Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {!isEdit ? (
              <>
                <Button variant="outlined" size="small" onClick={downloadLinesTemplate}>
                  Download template
                </Button>
                <input
                  ref={bulkCsvInputRef}
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={() => uploadLinesCsv()}
                />
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => bulkCsvInputRef.current?.click()}
                  disabled={bulkCsvLoading}
                >
                  {bulkCsvLoading ? 'Parsing…' : 'Upload CSV'}
                </Button>
              </>
            ) : null}
            <Button size="small" onClick={() => addLine('inventory')}>
              Add from inventory
            </Button>
            <Button size="small" onClick={() => addLine('new_item')}>
              + New item
            </Button>
            <Button size="small" onClick={() => addLine('custom')}>
              Add custom line
            </Button>
          </Box>
        </Box>
        {bulkCsvErrors.length > 0 ? (
          <Alert severity="warning" sx={{ mt: 1, mb: 1 }}>
            {bulkCsvErrors.length} row(s) had errors:{' '}
            {bulkCsvErrors.slice(0, 5).map((e) => `Row ${e.row}: ${e.message}`).join('; ')}
            {bulkCsvErrors.length > 5 ? ` … and ${bulkCsvErrors.length - 5} more` : ''}
          </Alert>
        ) : null}

        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Item / Description</TableCell>
              <TableCell>Qty</TableCell>
              <TableCell>Unit price</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>
                  {line.line_type === 'inventory' ? (
                    <FormControl size="small" sx={{ minWidth: 240 }}>
                      <InputLabel>Item</InputLabel>
                      <Select
                        value={line.item_id ? String(line.item_id) : ''}
                        label="Item"
                        onChange={(event) => {
                          const itemId = event.target.value ? Number(event.target.value) : null
                          const item = itemId ? inventoryItems.find((i) => i.id === itemId) : null
                          updateLine(line.id, {
                            item_id: itemId,
                            description: item ? item.name : '',
                          })
                        }}
                      >
                        <MenuItem value="">Select item</MenuItem>
                        {inventoryItems.map((item) => (
                          <MenuItem key={item.id} value={item.id}>
                            {item.name} ({item.sku_code})
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : line.line_type === 'new_item' ? (
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => openNewItemDialog(line)}
                      >
                        Create item
                      </Button>
                      {line.item_id ? (
                        <Typography variant="body2">
                          {inventoryItems.find((i) => i.id === line.item_id)?.name ?? 'Item'}
                        </Typography>
                      ) : null}
                    </Box>
                  ) : (
                    <TextField
                      size="small"
                      value={line.description}
                      onChange={(event) => updateLine(line.id, { description: event.target.value })}
                      placeholder="Description"
                      sx={{ minWidth: 240 }}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    type="number"
                    value={line.quantity_expected === 0 ? '' : line.quantity_expected}
                    onChange={(event) =>
                      updateLine(line.id, {
                        quantity_expected: Number(event.target.value) || 0,
                      })
                    }
                    onFocus={(event) => event.currentTarget.select()}
                    onWheel={(event) => event.currentTarget.blur()}
                    inputProps={{ min: 1 }}
                    sx={{ width: 90 }}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    type="number"
                    value={line.unit_price === 0 ? '' : line.unit_price}
                    onChange={(event) =>
                      updateLine(line.id, { unit_price: Number(event.target.value) || 0 })
                    }
                    onFocus={(event) => event.currentTarget.select()}
                    onWheel={(event) => event.currentTarget.blur()}
                    inputProps={{ min: 0, step: 0.01 }}
                    sx={{ width: 120 }}
                  />
                </TableCell>
                <TableCell align="right">
                  {formatMoney(line.quantity_expected * line.unit_price)}
                </TableCell>
                <TableCell align="right">
                  <IconButton size="small" onClick={() => removeLine(line.id)}>
                    <DeleteOutlineIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
          <Typography variant="subtitle1">
            Total: {formatMoney(totalExpected)}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
        <Button onClick={() => navigate('/procurement/orders')}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={loading}>
          Save order
        </Button>
      </Box>

      <Dialog
        open={newItemDialogOpen}
        onClose={() => setNewItemDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Create new inventory item</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Category</InputLabel>
            <Select
              value={newItemCategoryId}
              label="Category"
              onChange={(event) => setNewItemCategoryId(Number(event.target.value))}
            >
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
            required
          />
          <TextField label="SKU" value={newItemSku} disabled helperText="Will be auto-generated" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewItemDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createNewItemAndAssign} disabled={loading}>
            Create & assign
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={newPurposeDialogOpen}
        onClose={() => setNewPurposeDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Create new category</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Category name"
            value={newPurposeName}
            onChange={(event) => setNewPurposeName(event.target.value)}
            fullWidth
            required
            autoFocus
            placeholder="e.g., Uniforms, Stationery, Furniture"
            InputLabelProps={{ shrink: true }}
            helperText="Category for classifying purchases and payments"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewPurposeDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createNewPurpose} disabled={loading || !newPurposeName.trim()}>
            Create & select
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
