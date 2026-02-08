import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatMoney } from '../../utils/format'
import {
  Typography,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  Input,
  Textarea,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Spinner,
} from '../../components/ui'
import { Trash2, Plus } from 'lucide-react'

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

  const [error, setError] = useState<string | null>(null)

  const [newItemDialogOpen, setNewItemDialogOpen] = useState(false)
  const [newItemCategoryId, setNewItemCategoryId] = useState<number | ''>('')
  const [newItemName, setNewItemName] = useState('')
  const [newItemSku, setNewItemSku] = useState('')
  const [currentLineForNewItem, setCurrentLineForNewItem] = useState<POLineDraft | null>(null)
  const [creatingItem, setCreatingItem] = useState(false)

  const [newPurposeDialogOpen, setNewPurposeDialogOpen] = useState(false)
  const [newPurposeName, setNewPurposeName] = useState('')

  const [bulkCsvLoading, setBulkCsvLoading] = useState(false)
  const [bulkCsvErrors, setBulkCsvErrors] = useState<Array<{ row: number; message: string }>>([])
  const bulkCsvInputRef = useRef<HTMLInputElement>(null)

  const { data: purposesData } = useApi<PurposeRow[]>(
    '/procurement/payment-purposes',
    { params: { include_inactive: true } }
  )
  const { data: itemsData, refetch: refetchItems } = useApi<InventoryItemRow[]>(
    '/items',
    { params: { item_type: 'product', include_inactive: false } }
  )
  const { data: categoriesData } = useApi<CategoryRow[]>(
    '/items/categories',
    { params: { include_inactive: true } }
  )
  const { data: poData, loading: poLoading } = useApi<POResponse>(
    resolvedId ? `/procurement/purchase-orders/${resolvedId}` : null
  )
  const { execute: savePO, loading: saving } = useApiMutation<POResponse>()

  const purposes = purposesData || []
  const [inventoryItems, setInventoryItems] = useState<InventoryItemRow[]>([])
  const categories = categoriesData || []

  useEffect(() => {
    setInventoryItems(itemsData || [])
  }, [itemsData])

  useEffect(() => {
    if (poData && isEdit) {
      setSupplierName(poData.supplier_name)
      setSupplierContact(poData.supplier_contact ?? '')
      setPurposeId(poData.purpose_id)
      setOrderDate(poData.order_date)
      setExpectedDeliveryDate(poData.expected_delivery_date ?? '')
      setNotes(poData.notes ?? '')
      setLines(
        poData.lines.map((line) => ({
          id: `${line.id}`,
          item_id: line.item_id,
          description: line.description,
          quantity_expected: line.quantity_expected,
          unit_price: Number(line.unit_price),
          line_type: line.item_id ? 'inventory' : 'custom',
        }))
      )
    }
  }, [poData, isEdit])

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
    setError(null)
    try {
      const response = await api.post<ApiResponse<PurposeRow>>('/procurement/payment-purposes', {
        name: newPurposeName.trim(),
      })
      const newPurpose = response.data.data
      setPurposeId(newPurpose.id)
      setNewPurposeDialogOpen(false)
      setNewPurposeName('')
    } catch {
      setError('Failed to create purpose.')
    }
  }

  const createNewItemAndAssign = async () => {
    if (!currentLineForNewItem || !newItemCategoryId || !newItemName.trim()) {
      setError('Fill category and name for new item.')
      return
    }
    setError(null)
    try {
      const category = categories.find((c) => c.id === Number(newItemCategoryId))
      if (!category) {
        setError('Category not found.')
        return
      }
      setCreatingItem(true)
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
      setNewItemSku(newSku)

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
      void refetchItems()
      setNewItemDialogOpen(false)
      setCurrentLineForNewItem(null)
      setNewItemCategoryId('')
      setNewItemName('')
      setNewItemSku('')
    } catch {
      setError('Failed to create item.')
    } finally {
      setCreatingItem(false)
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

    setError(null)
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

    const result = isEdit && resolvedId
      ? await savePO(() => api.put(`/procurement/purchase-orders/${resolvedId}`, payload))
      : await savePO(() => api.post('/procurement/purchase-orders', payload))

    if (result) {
      navigate('/procurement/orders')
    } else {
      setError('Failed to save purchase order.')
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
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-4">
        {isEdit ? 'Edit purchase order' : 'New purchase order'}
      </Typography>

      {error && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <div className="grid gap-4 max-w-[600px] mb-6">
        <Input
          label="Supplier name"
          value={supplierName}
          onChange={(event) => setSupplierName(event.target.value)}
          required
        />
        <Input
          label="Supplier contact"
          value={supplierContact}
          onChange={(event) => setSupplierContact(event.target.value)}
        />
        <Select
          value={purposeId === '' ? '' : String(purposeId)}
          onChange={(event) => handlePurposeSelect(event.target.value)}
          label="Category / Purpose"
          required
        >
          <option value="">Select purpose</option>
          {purposes.map((purpose) => (
            <option key={purpose.id} value={purpose.id}>
              {purpose.name}
            </option>
          ))}
          <option value="create" className="italic text-primary">
            + Add new category
          </option>
        </Select>
        <Input
          label="Order date"
          type="date"
          value={orderDate}
          onChange={(event) => setOrderDate(event.target.value)}
          required
        />
        <Input
          label="Expected delivery date"
          type="date"
          value={expectedDeliveryDate}
          onChange={(event) => setExpectedDeliveryDate(event.target.value)}
        />
        <Textarea
          label="Notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={3}
        />
      </div>

      <div className="mb-4">
        <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
          <Typography variant="h6">Order lines</Typography>
          <div className="flex gap-2 flex-wrap">
            {!isEdit && (
              <>
                <Button variant="outlined" size="small" onClick={downloadLinesTemplate}>
                  Download template
                </Button>
                <input
                  ref={bulkCsvInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={() => uploadLinesCsv()}
                />
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => bulkCsvInputRef.current?.click()}
                  disabled={bulkCsvLoading}
                >
                  {bulkCsvLoading ? <Spinner size="small" /> : 'Upload CSV'}
                </Button>
              </>
            )}
            <Button size="small" onClick={() => addLine('inventory')}>
              Add from inventory
            </Button>
            <Button size="small" onClick={() => addLine('new_item')}>
              <Plus className="w-4 h-4 mr-1" />
              New item
            </Button>
            <Button size="small" onClick={() => addLine('custom')}>
              Add custom line
            </Button>
          </div>
        </div>
        {bulkCsvErrors.length > 0 && (
          <Alert severity="warning" className="mt-2 mb-2" onClose={() => {}}>
            {bulkCsvErrors.length} row(s) had errors:{' '}
            {bulkCsvErrors.slice(0, 5).map((e) => `Row ${e.row}: ${e.message}`).join('; ')}
            {bulkCsvErrors.length > 5 ? ` … and ${bulkCsvErrors.length - 5} more` : ''}
          </Alert>
        )}

        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Item / Description</TableHeaderCell>
              <TableHeaderCell>Qty</TableHeaderCell>
              <TableHeaderCell>Unit price</TableHeaderCell>
              <TableHeaderCell align="right">Total</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>
                  {line.line_type === 'inventory' ? (
                    <Select
                      value={line.item_id ? String(line.item_id) : ''}
                      onChange={(event) => {
                        const itemId = event.target.value ? Number(event.target.value) : null
                        const item = itemId ? inventoryItems.find((i) => i.id === itemId) : null
                        updateLine(line.id, {
                          item_id: itemId,
                          description: item ? item.name : '',
                        })
                      }}
                      label="Item"
                      className="min-w-[240px]"
                    >
                      <option value="">Select item</option>
                      {inventoryItems.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} ({item.sku_code})
                        </option>
                      ))}
                    </Select>
                  ) : line.line_type === 'new_item' ? (
                    <div className="flex gap-2 items-center">
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => openNewItemDialog(line)}
                      >
                        Create item
                      </Button>
                      {line.item_id && (
                        <Typography variant="body2">
                          {inventoryItems.find((i) => i.id === line.item_id)?.name ?? 'Item'}
                        </Typography>
                      )}
                    </div>
                  ) : (
                    <Input
                      value={line.description}
                      onChange={(event) => updateLine(line.id, { description: event.target.value })}
                      placeholder="Description"
                      className="min-w-[240px]"
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    value={line.quantity_expected === 0 ? '' : line.quantity_expected}
                    onChange={(event) =>
                      updateLine(line.id, {
                        quantity_expected: Number(event.target.value) || 0,
                      })
                    }
                    onFocus={(event) => event.currentTarget.select()}
                    onWheel={(event) => (event.currentTarget as HTMLInputElement).blur()}
                    min={1}
                    className="w-[90px]"
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    value={line.unit_price === 0 ? '' : line.unit_price}
                    onChange={(event) =>
                      updateLine(line.id, { unit_price: Number(event.target.value) || 0 })
                    }
                    onFocus={(event) => event.currentTarget.select()}
                    onWheel={(event) => (event.currentTarget as HTMLInputElement).blur()}
                    min={0}
                    step={0.01}
                    className="w-[120px]"
                  />
                </TableCell>
                <TableCell align="right">
                  {formatMoney(line.quantity_expected * line.unit_price)}
                </TableCell>
                <TableCell align="right">
                  <button
                    type="button"
                    onClick={() => removeLine(line.id)}
                    className="p-1 hover:bg-slate-100 rounded transition-colors"
                  >
                    <Trash2 className="w-5 h-5 text-slate-500" />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <div className="flex justify-end mt-4">
          <Typography variant="subtitle1">
            Total: {formatMoney(totalExpected)}
          </Typography>
        </div>
      </div>

      <div className="flex gap-2 mt-6">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSubmit} disabled={saving || poLoading}>
          {saving || poLoading ? <Spinner size="small" /> : 'Save order'}
        </Button>
      </div>

      <Dialog
        open={newItemDialogOpen}
        onClose={() => setNewItemDialogOpen(false)}
        maxWidth="sm"
      >
        <DialogTitle>Create new inventory item</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Select
              value={newItemCategoryId === '' ? '' : String(newItemCategoryId)}
              onChange={(event) => setNewItemCategoryId(Number(event.target.value))}
              label="Category"
            >
              <option value="">Select category</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
            <Input
              label="Name"
              value={newItemName}
              onChange={(event) => setNewItemName(event.target.value)}
              required
            />
            <Input
              label="SKU"
              value={newItemSku}
              disabled
              helperText="Will be auto-generated"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewItemDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={createNewItemAndAssign}
            disabled={creatingItem || !newItemCategoryId || !newItemName.trim()}
          >
            {creatingItem ? <Spinner size="small" /> : 'Create & assign'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={newPurposeDialogOpen}
        onClose={() => setNewPurposeDialogOpen(false)}
        maxWidth="sm"
      >
        <DialogTitle>Create new category</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Category name"
              value={newPurposeName}
              onChange={(event) => setNewPurposeName(event.target.value)}
              required
              placeholder="e.g., Uniforms, Stationery, Furniture"
              helperText="Category for classifying purchases and payments"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewPurposeDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createNewPurpose} disabled={saving || !newPurposeName.trim()}>
            {saving ? <Spinner size="small" /> : 'Create & select'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
