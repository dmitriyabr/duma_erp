import {
  Alert,
  Box,
  Button,
  FormControl,
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
import { useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import { api, unwrapResponse } from '../../services/api'
import { formatMoney } from '../../utils/format'
import type { ItemOption, KitOption } from './types'

interface StudentResponse {
  id: number
  full_name: string
  student_number: string
}

interface StudentOption {
  id: number
  full_name: string
  student_number: string
}

interface InvoiceDetail {
  id: number
}

type DiscountType = 'percentage' | 'fixed'

interface LineComponentDraft {
  item_id: number | ''
  quantity: number
}

interface DraftLine {
  id: string
  kit_id: number | null
  quantity: number
  discount_type: DiscountType
  discount_value: number | ''
  components: LineComponentDraft[]
}

const emptyLine = (): DraftLine => ({
  id: `${Date.now()}-${Math.random()}`,
  kit_id: null,
  quantity: 1,
  discount_type: 'percentage',
  discount_value: '',
  components: [],
})

const getDefaultDueDate = () => {
  const date = new Date()
  date.setMonth(date.getMonth() + 1)
  return date.toISOString().slice(0, 10)
}

export const CreateInvoicePage = () => {
  const { studentId: paramStudentId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state as { studentId?: number } | null) ?? null
  const [selectedStudentId, setSelectedStudentId] = useState<number | ''>(state?.studentId ?? '')
  const resolvedId = paramStudentId
    ? Number(paramStudentId)
    : (state?.studentId ?? (selectedStudentId === '' ? 0 : selectedStudentId))
  const studentIdLocked = !!paramStudentId || (state?.studentId != null)
  const isStandalone = !paramStudentId

  const [lines, setLines] = useState<DraftLine[]>([emptyLine()])
  const [dueDate, setDueDate] = useState(getDefaultDueDate())
  const [notes, setNotes] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const kitsApi = useApi<KitOption[]>('/items/kits', { params: { include_inactive: false } })
  const inventoryApi = useApi<ItemOption[]>('/items', {
    params: { item_type: 'product', include_inactive: false },
  })
  const variantsApi = useApi<Array<{ id: number; name: string; items: Array<{ id: number; name: string; sku_code: string }> }>>('/items/variants', { params: { include_inactive: false } })
  const studentsListApi = useApi<{ items: StudentOption[]; total: number }>(
    isStandalone ? '/students' : null,
    isStandalone ? { params: { page: 1, limit: DEFAULT_PAGE_SIZE, status: 'active' } } : undefined,
    [isStandalone]
  )
  const studentApi = useApi<StudentResponse>(
    resolvedId && !Number.isNaN(resolvedId) ? `/students/${resolvedId}` : null
  )
  const createMutation = useApiMutation<InvoiceDetail>()
  const students = studentsListApi.data?.items ?? []
  const inventoryItems = inventoryApi.data ?? []

  const kits = useMemo(
    () => (kitsApi.data ?? []).filter((kit) => kit.price_type === 'standard'),
    [kitsApi.data]
  )
  const student = studentApi.data ?? null
  const error =
    validationError ??
    kitsApi.error ??
    inventoryApi.error ??
    studentApi.error ??
    studentsListApi.error ??
    createMutation.error
  const loading = createMutation.loading

  const updateLine = (lineId: string, updates: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line) => {
      if (line.id === lineId) {
        const updated = { ...line, ...updates }
        // If kit changed and it's editable, initialize components from kit's default items
        if (updates.kit_id !== undefined && updates.kit_id !== null) {
          const selectedKit = kits.find((k) => k.id === updates.kit_id)
          if (selectedKit?.is_editable_components && selectedKit.items && selectedKit.items.length > 0) {
            updated.components = selectedKit.items.map((ki) => {
              // Determine item_id based on source_type
              const itemId = ki.source_type === 'item' 
                ? ki.item_id 
                : ki.default_item_id
              return {
                item_id: itemId ?? '',
                quantity: ki.quantity,
              }
            })
          } else {
            updated.components = []
          }
        }
        return updated
      }
      return line
    }))
  }

  const removeLine = (lineId: string) => {
    setLines((prev) => prev.filter((line) => line.id !== lineId))
  }

  const unitPriceForLine = (line: DraftLine) => {
    const kit = line.kit_id ? kits.find((k) => k.id === line.kit_id) : null
    return kit?.price ?? 0
  }

  const discountAmountForLine = (line: DraftLine) => {
    const unitPrice = unitPriceForLine(line)
    const lineTotal = unitPrice * line.quantity
    const rawValue = line.discount_value === '' ? 0 : line.discount_value
    if (!rawValue) {
      return 0
    }
    if (line.discount_type === 'percentage') {
      const percent = Math.max(0, Math.min(100, rawValue))
      return Number(((lineTotal * percent) / 100).toFixed(2))
    }
    const fixed = Math.max(0, Math.min(lineTotal, rawValue))
    return Number(fixed.toFixed(2))
  }

  const normalizeDiscountValue = (line: DraftLine) => {
    if (line.discount_value === '') {
      return ''
    }
    const raw = Number.isNaN(line.discount_value) ? 0 : line.discount_value
    if (line.discount_type === 'percentage') {
      return Math.max(0, Math.min(100, raw))
    }
    const lineTotal = unitPriceForLine(line) * line.quantity
    return Math.max(0, Math.min(lineTotal, raw))
  }

  const lineTotalForLine = (line: DraftLine) => {
    const unitPrice = unitPriceForLine(line)
    const lineTotal = unitPrice * line.quantity
    return Math.max(0, lineTotal - discountAmountForLine(line))
  }

  const invoiceTotal = useMemo(() => lines.reduce((sum, line) => sum + lineTotalForLine(line), 0), [
    lines,
    kits,
  ])

  const updateLineComponents = (
    lineId: string,
    updater: (prev: LineComponentDraft[]) => LineComponentDraft[]
  ) => {
    setLines((prev) =>
      prev.map((line) =>
        line.id === lineId
          ? {
              ...line,
              components: updater(line.components),
            }
          : line
      )
    )
  }

  // Components are fixed by kit definition; we only allow changing the concrete item (model),
  // not removing components or changing their quantity.
  const updateComponentRow = (
    lineId: string,
    index: number,
    field: keyof LineComponentDraft,
    value: number | ''
  ) => {
    if (field !== 'item_id') {
      return
    }
    updateLineComponents(lineId, (prev) => {
      const next = [...prev]
      const current = next[index] ?? { item_id: '', quantity: 1 }
      current.item_id = value
      next[index] = current
      return next
    })
  }

  const submitInvoice = async () => {
    if (!resolvedId) return
    setValidationError(null)
    createMutation.reset()
    if (!lines.length) {
      setValidationError('Add at least one line.')
      return
    }
    if (lines.some((line) => !line.kit_id)) {
      setValidationError('Each line must have a catalog item selected.')
      return
    }
    // Optional basic validation for configurable kits: ensure at least one component if required
    const kitsById = new Map(kits.map((k) => [k.id, k]))
    for (const line of lines) {
      if (!line.kit_id) continue
      const kit = kitsById.get(line.kit_id)
      if (kit?.is_editable_components) {
        const effectiveComponents = line.components.filter((c) => c.item_id && c.quantity > 0)
        if (!effectiveComponents.length) {
          setValidationError('Configured kits must have at least one component item.')
          return
        }
      }
    }
    const result = await createMutation.execute(() =>
      api
        .post('/invoices', {
          student_id: resolvedId,
          due_date: dueDate || null,
          notes: notes.trim() || null,
          lines: lines.map((line) => {
            const kit = line.kit_id ? kitsById.get(line.kit_id) : null
            const base = {
              kit_id: line.kit_id,
              quantity: line.quantity,
              discount_amount: discountAmountForLine(line),
            }
            if (kit?.is_editable_components) {
              const components = line.components
                .filter((c) => c.item_id && c.quantity > 0)
                .map((c) => ({
                  item_id: c.item_id as number,
                  quantity: c.quantity,
                }))
              return { ...base, components }
            }
            return base
          }),
        })
        .then((r) => ({ data: { data: unwrapResponse<InvoiceDetail>(r) } }))
    )
    if (result != null) navigate(`/students/${resolvedId}?tab=invoices`)
  }

  if (isStandalone && !resolvedId) {
    return (
      <Box>
        <Button onClick={() => navigate(-1)} sx={{ mb: 2 }}>
          Back
        </Button>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
          Sell items to student
        </Typography>
        {studentsListApi.error ? (
          <Alert severity="error" sx={{ mb: 2 }}>
            {studentsListApi.error}
          </Alert>
        ) : null}
        <FormControl size="small" sx={{ minWidth: 280, display: 'block', mb: 2 }}>
          <Select
            value={selectedStudentId === '' ? '' : String(selectedStudentId)}
            onChange={(e) => setSelectedStudentId(e.target.value ? Number(e.target.value) : '')}
            displayEmpty
            renderValue={(v) => {
              if (!v) return 'Select student'
              const s = students.find((x) => String(x.id) === v)
              return s ? `${s.full_name} (#${s.student_number})` : 'Select student'
            }}
          >
            <MenuItem value="">Select student</MenuItem>
            {students.map((s) => (
              <MenuItem key={s.id} value={String(s.id)}>
                {s.full_name} · #{s.student_number}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
    )
  }

  return (
    <Box>
      <Button onClick={() => navigate(-1)} sx={{ mb: 2 }}>
        Back
      </Button>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        Sell item
      </Typography>
      {student ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {student.full_name} · Student #{student.student_number}
          {studentIdLocked ? null : (
            <Button size="small" sx={{ ml: 1 }} onClick={() => setSelectedStudentId('')}>
              Change student
            </Button>
          )}
        </Typography>
      ) : null}

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1">Invoice lines</Typography>
        <Button size="small" onClick={() => setLines((prev) => [...prev, emptyLine()])}>
          Add line
        </Button>
      </Box>
      {!kits.length ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          No sellable items available. Term invoices should be issued via the “Invoice term” button.
        </Alert>
      ) : null}
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Catalog item</TableCell>
            <TableCell>Qty</TableCell>
            <TableCell>Unit price</TableCell>
            <TableCell>Discount type</TableCell>
            <TableCell>Discount value</TableCell>
            <TableCell>Total</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lines.map((line) => {
            const unitPrice = unitPriceForLine(line)
            const kit = line.kit_id ? kits.find((k) => k.id === line.kit_id) : null
            const isConfigurable = Boolean(kit?.is_editable_components)
            return (
              <>
                <TableRow key={line.id}>
                  <TableCell>
                    <FormControl size="small" sx={{ minWidth: 240 }}>
                      <Select
                        value={line.kit_id ? String(line.kit_id) : ''}
                        onChange={(event) =>
                          updateLine(line.id, {
                            kit_id: event.target.value ? Number(event.target.value) : null,
                            components: [],
                          })
                        }
                        displayEmpty
                      >
                        <MenuItem value="">Select item</MenuItem>
                        {kits.map((k) => (
                          <MenuItem key={k.id} value={String(k.id)}>
                            {k.name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      type="number"
                      value={line.quantity}
                      onChange={(event) =>
                        updateLine(line.id, { quantity: Number(event.target.value) || 0 })
                      }
                      inputProps={{ min: 1 }}
                      sx={{ width: 90 }}
                    />
                  </TableCell>
                  <TableCell>{formatMoney(unitPrice)}</TableCell>
                  <TableCell>
                    <FormControl size="small" sx={{ minWidth: 140 }}>
                      <Select
                        value={line.discount_type}
                        onChange={(event) =>
                          updateLine(line.id, {
                            discount_type: event.target.value as DiscountType,
                            discount_value: '',
                          })
                        }
                      >
                        <MenuItem value="percentage">Percent</MenuItem>
                        <MenuItem value="fixed">Amount</MenuItem>
                      </Select>
                    </FormControl>
                  </TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      type="number"
                      value={line.discount_value}
                      placeholder="0"
                      onChange={(event) =>
                        updateLine(line.id, {
                          discount_value:
                            event.target.value === '' ? '' : Number(event.target.value),
                        })
                      }
                      onBlur={() =>
                        updateLine(line.id, { discount_value: normalizeDiscountValue(line) })
                      }
                      inputProps={{ min: 0 }}
                      sx={{ width: 110 }}
                    />
                  </TableCell>
                  <TableCell>{formatMoney(lineTotalForLine(line))}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => removeLine(line.id)}>
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
                {isConfigurable ? (
                  <TableRow key={`${line.id}-components`}>
                    <TableCell colSpan={7}>
                      <Box sx={{ mt: 1, p: 1, borderRadius: 1, bgcolor: 'grey.50' }}>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                          Components for {kit?.name}
                        </Typography>
                        {/* Components are fixed; user can only change the concrete inventory item (model). */}
                        {line.components.map((comp, index) => {
                          // Get variant_id from kit's default item at this index
                          const defaultKitItem = kit?.items?.[index]
                          
                          // Filter items: if kit item source_type is 'variant', show only items from that variant
                          // Otherwise show all product items
                          let availableItems = inventoryItems
                          if (defaultKitItem?.source_type === 'variant' && defaultKitItem.variant_id) {
                            const variant = variantsApi.data?.find(v => v.id === defaultKitItem.variant_id)
                            if (variant) {
                              const variantItemIds = new Set(variant.items.map(i => i.id))
                              availableItems = inventoryItems.filter((item) => variantItemIds.has(item.id))
                            }
                          }
                          
                          return (
                            <Box
                              key={`${line.id}-comp-${index}`}
                              sx={{
                                display: 'flex',
                                gap: 1,
                                alignItems: 'center',
                                mb: 1,
                                flexWrap: 'wrap',
                              }}
                            >
                              <FormControl size="small" sx={{ minWidth: 220 }}>
                                <Select
                                  value={comp.item_id === '' ? '' : String(comp.item_id)}
                                  onChange={(event) =>
                                    updateComponentRow(
                                      line.id,
                                      index,
                                      'item_id',
                                      event.target.value ? Number(event.target.value) : ''
                                    )
                                  }
                                  displayEmpty
                                >
                                  <MenuItem value="">Select inventory item</MenuItem>
                                  {availableItems.map((item) => (
                                    <MenuItem key={item.id} value={String(item.id)}>
                                      {item.name} · {item.sku_code}
                                    </MenuItem>
                                  ))}
                                </Select>
                              </FormControl>
                              <TextField
                                size="small"
                                type="number"
                                label="Qty"
                                value={comp.quantity}
                                disabled
                                inputProps={{ min: 1 }}
                                sx={{ width: 90 }}
                              />
                            </Box>
                          )
                        })}
                      </Box>
                    </TableCell>
                  </TableRow>
                ) : null}
              </>
            )
          })}
          {!lines.length ? (
            <TableRow>
              <TableCell colSpan={7} align="center">
                Add at least one line
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
        <Typography variant="subtitle1">Total: {formatMoney(invoiceTotal)}</Typography>
      </Box>

      <Box sx={{ display: 'grid', gap: 2, mt: 3, maxWidth: 420 }}>
        <TextField
          label="Due date"
          type="date"
          value={dueDate}
          onChange={(event) => setDueDate(event.target.value)}
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

      <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
        <Button onClick={() => navigate(-1)}>Cancel</Button>
        <Button variant="contained" onClick={submitInvoice} disabled={loading}>
          Create invoice
        </Button>
      </Box>
    </Box>
  )
}
