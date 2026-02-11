import { useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import { api, unwrapResponse } from '../../services/api'
import { formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Autocomplete } from '../../components/ui/Autocomplete'
import { Textarea } from '../../components/ui/Textarea'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Trash2 } from 'lucide-react'
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

type DiscountType = 'percentage' | 'fixed'

interface LineComponentDraft {
  unit_item_ids: Array<number | ''>
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
  const variantsApi = useApi<VariantRow[]>('/items/variants', { params: { include_inactive: false } })
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

  const kits = useMemo(
    () => (kitsApi.data ?? []).filter((kit) => kit.price_type === 'standard'),
    [kitsApi.data]
  )
  const student = studentApi.data ?? null
  const error =
    validationError ??
    kitsApi.error ??
    inventoryApi.error ??
    variantsApi.error ??
    studentApi.error ??
    studentsListApi.error ??
    createMutation.error
  const loading = createMutation.loading

  const [componentsDialog, setComponentsDialog] = useState<{ open: boolean; lineId: string | null }>({
    open: false,
    lineId: null,
  })

  const buildDefaultComponents = (kit: KitOption, lineQty: number): LineComponentDraft[] => {
    const kitItems = kit.items ?? []
    return kitItems.map((ki) => {
      const defaultItemId = ki.source_type === 'item' ? ki.item_id : ki.default_item_id
      const totalUnits = Math.max(1, ki.quantity) * Math.max(1, lineQty)
      return {
        unit_item_ids: Array.from({ length: totalUnits }, () => (defaultItemId ?? '') as number | ''),
      }
    })
  }

  const syncComponents = (
    kit: KitOption,
    lineQty: number,
    current: LineComponentDraft[]
  ): LineComponentDraft[] => {
    const kitItems = kit.items ?? []
    if (!kitItems.length) return []
    return kitItems.map((ki, index) => {
      const prev = current[index]
      const defaultItemId = ki.source_type === 'item' ? ki.item_id : ki.default_item_id
      const totalUnits = Math.max(1, ki.quantity) * Math.max(1, lineQty)
      const prevUnits = prev?.unit_item_ids ?? []
      const nextUnits = prevUnits.slice(0, totalUnits)
      while (nextUnits.length < totalUnits) {
        nextUnits.push((defaultItemId ?? '') as number | '')
      }
      return {
        unit_item_ids: nextUnits,
      }
    })
  }

  const updateLine = (lineId: string, updates: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line) => {
      if (line.id === lineId) {
        const updated = { ...line, ...updates }
        const kitId = updated.kit_id
        const selectedKit = kitId ? kits.find((k) => k.id === kitId) : null

        // If kit changed, (re)initialize components for editable kits.
        if (updates.kit_id !== undefined) {
          if (selectedKit?.is_editable_components) {
            updated.components = buildDefaultComponents(selectedKit, updated.quantity)
          } else {
            updated.components = []
          }
        }

        // If quantity changed and kit is editable, keep selections but sync quantities.
        if (updates.quantity !== undefined && selectedKit?.is_editable_components) {
          updated.components = syncComponents(selectedKit, updated.quantity, updated.components)
        }
        return updated
      }
      return line
    }))
  }

  const updateLineComponentUnitItem = (
    lineId: string,
    componentIndex: number,
    unitIndex: number,
    itemId: number | ''
  ) => {
    setLines((prev) =>
      prev.map((line) => {
        if (line.id !== lineId) return line
        const kit = line.kit_id ? kits.find((k) => k.id === line.kit_id) : null
        if (!kit?.is_editable_components) return line
        const nextComponents = syncComponents(kit, line.quantity, line.components).map((c, i) => {
          if (i !== componentIndex) return c
          return {
            ...c,
            unit_item_ids: c.unit_item_ids.map((v, vi) => (vi === unitIndex ? itemId : v)),
          }
        })
        return { ...line, components: nextComponents }
      })
    )
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

  const invoiceTotal = useMemo(() => {
    return lines.reduce((sum, line) => {
      const kit = line.kit_id ? kits.find((k) => k.id === line.kit_id) : null
      const unitPrice = kit?.price ?? 0
      const lineTotal = unitPrice * line.quantity
      const rawValue = line.discount_value === '' ? 0 : line.discount_value
      let discount = 0
      if (rawValue) {
        if (line.discount_type === 'percentage') {
          const percent = Math.max(0, Math.min(100, rawValue))
          discount = Number(((lineTotal * percent) / 100).toFixed(2))
        } else {
          const fixed = Math.max(0, Math.min(lineTotal, rawValue))
          discount = Number(fixed.toFixed(2))
        }
      }
      return sum + Math.max(0, lineTotal - discount)
    }, 0)
  }, [kits, lines])

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
        const kitItems = kit.items ?? []
        const synced = syncComponents(kit, line.quantity, line.components)
        if (!kitItems.length) {
          setValidationError('Configured kit has no default components.')
          return
        }
        if (synced.length !== kitItems.length) {
          setValidationError('Configured kit components are not initialized. Please re-select the kit.')
          return
        }
        if (synced.some((c) => c.unit_item_ids.some((v) => !v))) {
          setValidationError('Select a concrete inventory item for each component.')
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
              const components = syncComponents(kit, line.quantity, line.components).map((c) => {
                const counts = new Map<number, number>()
                for (const unit of c.unit_item_ids) {
                  const id = unit as number
                  counts.set(id, (counts.get(id) ?? 0) + 1)
                }
                return {
                  allocations: Array.from(counts.entries()).map(([item_id, quantity]) => ({
                    item_id,
                    quantity,
                  })),
                }
              })
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
      <div>
        <Button onClick={() => navigate(-1)} className="mb-4">
          Back
        </Button>
        <Typography variant="h4" className="mb-4">
          Sell items to student
        </Typography>
        {studentsListApi.error && (
          <Alert severity="error" className="mb-4" onClose={() => {}}>
            {studentsListApi.error}
          </Alert>
        )}
        <Select
          value={selectedStudentId === '' ? '' : String(selectedStudentId)}
          onChange={(e) => setSelectedStudentId(e.target.value ? Number(e.target.value) : '')}
          className="min-w-[280px] mb-4"
        >
          <option value="">Select student</option>
          {students.map((s) => (
            <option key={s.id} value={String(s.id)}>
              {s.full_name} · #{s.student_number}
            </option>
          ))}
        </Select>
      </div>
    )
  }

  return (
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-2">
        Sell item
      </Typography>
      {student && (
        <Typography variant="body2" color="secondary" className="mb-6">
          {student.full_name} · Student #{student.student_number}
          {!studentIdLocked && (
            <Button size="small" variant="text" className="ml-2" onClick={() => setSelectedStudentId('')}>
              Change student
            </Button>
          )}
        </Typography>
      )}

      {error && (
        <Alert severity="error" className="mb-4" onClose={() => {}}>
          {error}
        </Alert>
      )}

      <div className="flex justify-between items-center mb-2">
        <Typography variant="subtitle1">Invoice lines</Typography>
        <Button size="small" onClick={() => setLines((prev) => [...prev, emptyLine()])}>
          Add line
        </Button>
      </div>
      {!kits.length && (
        <Alert severity="warning" className="mb-4" onClose={() => {}}>
          No sellable items available. Term invoices should be issued via the "Invoice term" button.
        </Alert>
      )}
      <Table className="mb-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Catalog item</TableHeaderCell>
            <TableHeaderCell>Qty</TableHeaderCell>
            <TableHeaderCell>Unit price</TableHeaderCell>
            <TableHeaderCell>Discount type</TableHeaderCell>
            <TableHeaderCell>Discount value</TableHeaderCell>
            <TableHeaderCell>Total</TableHeaderCell>
            <TableHeaderCell align="right">Actions</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lines.map((line) => {
            const unitPrice = unitPriceForLine(line)
            const kit = line.kit_id ? kits.find((k) => k.id === line.kit_id) : null
            const canConfigure = Boolean(kit?.is_editable_components)
            return (
              <TableRow key={line.id}>
                <TableCell>
                  <Autocomplete
                    options={kits}
                    getOptionLabel={(kit) => kit.name}
                    getOptionValue={(kit) => kit.id}
                    value={kits.find((kit) => kit.id === line.kit_id) || null}
                    onChange={(kit) =>
                      updateLine(line.id, {
                        kit_id: kit ? kit.id : null,
                      })
                    }
                    placeholder="Type to search items..."
                    className="min-w-[240px]"
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    value={line.quantity}
                    onChange={(event) =>
                      updateLine(line.id, { quantity: Number(event.target.value) || 0 })
                    }
                    min={1}
                    className="w-[90px]"
                  />
                </TableCell>
                <TableCell>{formatMoney(unitPrice)}</TableCell>
                <TableCell>
                  <Select
                    value={line.discount_type}
                    onChange={(event) =>
                      updateLine(line.id, {
                        discount_type: event.target.value as DiscountType,
                        discount_value: '',
                      })
                    }
                    className="min-w-[140px]"
                  >
                    <option value="percentage">Percent</option>
                    <option value="fixed">Amount</option>
                  </Select>
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    value={line.discount_value}
                    placeholder="0"
                    onChange={(event) =>
                      updateLine(line.id, {
                        discount_value: event.target.value === '' ? '' : Number(event.target.value),
                      })
                    }
                    onBlur={() =>
                      updateLine(line.id, { discount_value: normalizeDiscountValue(line) })
                    }
                    min={0}
                    className="w-[110px]"
                  />
                </TableCell>
                <TableCell>{formatMoney(lineTotalForLine(line))}</TableCell>
                <TableCell align="right">
                  <div className="flex justify-end gap-2">
                    {canConfigure && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => setComponentsDialog({ open: true, lineId: line.id })}
                      >
                        Components
                      </Button>
                    )}
                    <Button size="small" variant="text" onClick={() => removeLine(line.id)}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )
          })}
          {!lines.length && (
            <TableRow>
              <td colSpan={7} className="px-4 py-8 text-center">
                Add at least one line
              </td>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <div className="flex justify-end mb-4">
        <Typography variant="subtitle1">Total: {formatMoney(invoiceTotal)}</Typography>
      </div>

      <div className="grid gap-4 mt-6 max-w-[420px]">
        <Input
          label="Due date"
          type="date"
          value={dueDate}
          onChange={(event) => setDueDate(event.target.value)}
        />
        <Textarea
          label="Notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={3}
        />
      </div>

      <div className="flex gap-2 mt-6">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submitInvoice} disabled={loading}>
          {loading ? <Spinner size="small" /> : 'Create invoice'}
        </Button>
      </div>

      <Dialog
        open={componentsDialog.open}
        onClose={() => setComponentsDialog({ open: false, lineId: null })}
        maxWidth="lg"
      >
        <DialogCloseButton onClose={() => setComponentsDialog({ open: false, lineId: null })} />
        <DialogTitle>Configure components</DialogTitle>
        <DialogContent>
          {(() => {
            const line = componentsDialog.lineId ? lines.find((l) => l.id === componentsDialog.lineId) : null
            const kit = line?.kit_id ? kits.find((k) => k.id === line.kit_id) : null
            if (!line || !kit) {
              return <Alert severity="error">Line not found.</Alert>
            }
            if (!kit.is_editable_components) {
              return <Alert severity="warning">This item does not support editable components.</Alert>
            }
            const kitItems = kit.items ?? []
            if (!kitItems.length) {
              return <Alert severity="warning">This kit has no default components configured.</Alert>
            }

            const synced = syncComponents(kit, line.quantity, line.components)
            const variants = variantsApi.data ?? []

            return (
              <div className="grid gap-4 mt-2">
                <Typography variant="body2" color="secondary">
                  Quantities are calculated automatically based on line quantity ({line.quantity}).
                </Typography>

                {variantsApi.loading && (
                  <div className="flex items-center gap-2">
                    <Spinner size="small" />
                    <Typography variant="body2" color="secondary">
                      Loading variants...
                    </Typography>
                  </div>
                )}

                {kitItems.map((ki, index) => {
                  const qty = Math.max(1, ki.quantity) * Math.max(1, line.quantity)
                  if (ki.source_type === 'variant') {
                    const variantItems = variants.find((v) => v.id === ki.variant_id)?.items ?? []
                    return (
                      <div key={`${kit.id}-comp-${index}`} className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="grid gap-3 sm:grid-cols-[1fr_140px] items-end">
                          <div className="grid gap-3">
                            <Typography variant="body2" className="font-medium">
                              {ki.variant_name ? `Variant: ${ki.variant_name}` : 'Variant'}
                            </Typography>
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                              {synced[index]?.unit_item_ids.map((unitId, unitIndex) => (
                                <Select
                                  key={`${kit.id}-comp-${index}-${unitIndex}`}
                                  value={unitId === '' ? '' : String(unitId)}
                                  onChange={(event) =>
                                    updateLineComponentUnitItem(
                                      line.id,
                                      index,
                                      unitIndex,
                                      event.target.value ? Number(event.target.value) : ''
                                    )
                                  }
                                  label={`Item ${unitIndex + 1} of ${qty}`}
                                  disabled={variantsApi.loading}
                                  required
                                >
                                  <option value="">Select item</option>
                                  {variantItems.map((it) => (
                                    <option key={it.id} value={it.id}>
                                      {`${it.name} (${it.sku_code})`}
                                    </option>
                                  ))}
                                </Select>
                              ))}
                            </div>
                          </div>
                          <Input label="Total qty" type="number" value={qty} disabled />
                        </div>
                      </div>
                    )
                  }

                  const invOptions = inventoryApi.data ?? []
                  const defaultItemId = ki.source_type === 'item' ? ki.item_id : null
                  const selected = invOptions.find((it) => it.id === defaultItemId) ?? null
                  return (
                    <div key={`${kit.id}-comp-${index}`} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="grid gap-3 sm:grid-cols-[1fr_140px] items-end">
                        <Select
                          value={selected?.id ? String(selected.id) : ''}
                          onChange={() => {}}
                          label={ki.item_name ? `Item: ${ki.item_name}` : 'Item'}
                          disabled
                        >
                          <option value="">
                            {selected ? `${selected.name} (${selected.sku_code})` : '—'}
                          </option>
                        </Select>
                        <Input label="Total qty" type="number" value={qty} disabled />
                      </div>
                    </div>
                  )
                })}
              </div>
            )
          })()}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setComponentsDialog({ open: false, lineId: null })}>Close</Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
