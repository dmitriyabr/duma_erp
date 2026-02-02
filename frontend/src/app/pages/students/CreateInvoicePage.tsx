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
import { Textarea } from '../../components/ui/Textarea'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'
import { Trash2 } from 'lucide-react'

interface KitOption {
  id: number
  name: string
  price: number
  price_type: string
}

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

interface DraftLine {
  id: string
  kit_id: number | null
  quantity: number
  discount_type: DiscountType
  discount_value: number | ''
}

const emptyLine = (): DraftLine => ({
  id: `${Date.now()}-${Math.random()}`,
  kit_id: null,
  quantity: 1,
  discount_type: 'percentage',
  discount_value: '',
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
    studentApi.error ??
    studentsListApi.error ??
    createMutation.error
  const loading = createMutation.loading

  const updateLine = (lineId: string, updates: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? { ...line, ...updates } : line)))
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
    const result = await createMutation.execute(() =>
      api
        .post('/invoices', {
          student_id: resolvedId,
          due_date: dueDate || null,
          notes: notes.trim() || null,
          lines: lines.map((line) => ({
            kit_id: line.kit_id,
            quantity: line.quantity,
            discount_amount: discountAmountForLine(line),
          })),
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
            return (
              <TableRow key={line.id}>
                <TableCell>
                  <Select
                    value={line.kit_id ? String(line.kit_id) : ''}
                    onChange={(event) =>
                      updateLine(line.id, {
                        kit_id: event.target.value ? Number(event.target.value) : null,
                      })
                    }
                    className="min-w-[240px]"
                  >
                    <option value="">Select item</option>
                    {kits.map((kit) => (
                      <option key={kit.id} value={String(kit.id)}>
                        {kit.name}
                      </option>
                    ))}
                  </Select>
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
                  <Button size="small" variant="text" onClick={() => removeLine(line.id)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            )
          })}
          {!lines.length && (
            <TableRow>
              <TableCell colSpan={7} align="center">
                Add at least one line
              </TableCell>
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
    </div>
  )
}
