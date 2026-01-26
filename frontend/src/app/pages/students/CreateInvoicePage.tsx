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
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'

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

interface InvoiceDetail {
  id: number
}

interface ApiResponse<T> {
  success: boolean
  data: T
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
  const { studentId } = useParams()
  const navigate = useNavigate()
  const resolvedId = Number(studentId)
  const [kits, setKits] = useState<KitOption[]>([])
  const [student, setStudent] = useState<StudentResponse | null>(null)
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()])
  const [dueDate, setDueDate] = useState(getDefaultDueDate())
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadReferenceData = async () => {
    try {
      const kitsResponse = await api.get<ApiResponse<KitOption[]>>('/items/kits', {
        params: { include_inactive: false },
      })
      const standardKits = kitsResponse.data.data.filter((kit) => kit.price_type === 'standard')
      setKits(standardKits)
    } catch {
      setError('Failed to load catalog items.')
    }
  }

  const loadStudent = async () => {
    if (!resolvedId) {
      return
    }
    try {
      const response = await api.get<ApiResponse<StudentResponse>>(`/students/${resolvedId}`)
      setStudent(response.data.data)
    } catch {
      setStudent(null)
    }
  }

  useEffect(() => {
    loadReferenceData()
    loadStudent()
  }, [resolvedId])

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
    if (!resolvedId) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      if (!lines.length) {
        setError('Add at least one line.')
        setLoading(false)
        return
      }
      const invalidLine = lines.find((line) => {
        return !line.kit_id
      })
      if (invalidLine) {
        setError('Each line must have a catalog item selected.')
        setLoading(false)
        return
      }

      await api.post<ApiResponse<InvoiceDetail>>('/invoices', {
        student_id: resolvedId,
        due_date: dueDate || null,
        notes: notes.trim() || null,
        lines: lines.map((line) => ({
          kit_id: line.kit_id,
          quantity: line.quantity,
          discount_amount: discountAmountForLine(line),
        })),
      })
      navigate(`/students/${resolvedId}?tab=invoices`)
    } catch (err) {
      setError('Failed to create invoice.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Button onClick={() => navigate(`/students/${resolvedId}?tab=invoices`)} sx={{ mb: 2 }}>
        Back to student
      </Button>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        Sell item
      </Typography>
      {student ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {student.full_name} · Student #{student.student_number}
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
            return (
              <TableRow key={line.id}>
                <TableCell>
                  <FormControl size="small" sx={{ minWidth: 240 }}>
                    <Select
                      value={line.kit_id ? String(line.kit_id) : ''}
                      onChange={(event) =>
                        updateLine(line.id, {
                          kit_id: event.target.value ? Number(event.target.value) : null,
                        })
                      }
                      displayEmpty
                    >
                      <MenuItem value="">Select item</MenuItem>
                      {kits.map((kit) => (
                        <MenuItem key={kit.id} value={String(kit.id)}>
                          {kit.name}
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
                        discount_value: event.target.value === '' ? '' : Number(event.target.value),
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
        <Button onClick={() => navigate(`/students/${resolvedId}`)}>Cancel</Button>
        <Button variant="contained" onClick={submitInvoice} disabled={loading}>
          Create invoice
        </Button>
      </Box>
    </Box>
  )
}
