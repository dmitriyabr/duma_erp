import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Trash2 } from 'lucide-react'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { MAX_DROPDOWN_SIZE } from '../../constants/pagination'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Radio, RadioGroup } from '../../components/ui/Radio'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'

interface ItemOption {
  id: number
  name: string
  sku_code: string
  category_id: number
}

interface StudentOption {
  id: number
  student_number: string
  first_name: string
  last_name: string
}

interface UserOption {
  id: number
  full_name: string
}

type RecipientTypeOption = 'student' | 'employee' | 'other'

interface IssueLineDraft {
  id: string
  item_id: number | null
  quantity: number
}

const emptyLine = (): IssueLineDraft => ({
  id: `${Date.now()}-${Math.random()}`,
  item_id: null,
  quantity: 1,
})

export const IssueFormPage = () => {
  const navigate = useNavigate()
  const [recipientType, setRecipientType] = useState<RecipientTypeOption>('employee')
  const [recipientId, setRecipientId] = useState<string>('')
  const [recipientNameOther, setRecipientNameOther] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<IssueLineDraft[]>([emptyLine()])
  const [error, setError] = useState<string | null>(null)
  const [lineErrors, setLineErrors] = useState<Record<string, string>>({})

  const { data: items } = useApi<ItemOption[]>('/items', {
    params: { item_type: 'product', include_inactive: false },
  })
  const { data: studentsData } = useApi<PaginatedResponse<StudentOption>>('/students', {
    params: { limit: MAX_DROPDOWN_SIZE },
  })
  const { data: usersData } = useApi<PaginatedResponse<UserOption>>('/users', {
    params: { limit: MAX_DROPDOWN_SIZE },
  })

  const students = studentsData?.items || []
  const users = usersData?.items || []

  const { execute: createIssuance, loading, error: saveError } = useApiMutation<{ issuance_number: string; id: number }>()

  const updateLine = (lineId: string, updates: Partial<IssueLineDraft>) => {
    setLines((prev) =>
      prev.map((line) => (line.id === lineId ? { ...line, ...updates } : line))
    )
  }

  const removeLine = (lineId: string) => {
    setLines((prev) => prev.filter((line) => line.id !== lineId))
  }

  const addLine = () => {
    setLines((prev) => [...prev, emptyLine()])
  }

  const recipientValid =
    recipientType === 'student'
      ? recipientId !== ''
      : recipientType === 'employee'
        ? recipientId !== ''
        : recipientNameOther.trim() !== ''

  const handleSubmit = async () => {
    if (!recipientValid) {
      setError(
        recipientType === 'other'
          ? 'Enter recipient name.'
          : recipientType === 'student'
            ? 'Select a student.'
            : 'Select an employee.'
      )
      return
    }
    const validLines = lines.filter((l) => l.item_id != null && l.quantity > 0)
    if (!validLines.length) {
      setError('Add at least one item with quantity.')
      return
    }

    let recipientName = ''
    let payloadRecipientId: number | undefined
    if (recipientType === 'other') {
      recipientName = recipientNameOther.trim()
    } else if (recipientType === 'student') {
      const idNum = Number(recipientId)
      const student = students.find((s) => s.id === idNum)
      recipientName = student
        ? `${student.first_name} ${student.last_name}`.trim()
        : ''
      payloadRecipientId = idNum
    } else {
      const idNum = Number(recipientId)
      const emp = users.find((u) => u.id === idNum)
      recipientName = emp?.full_name ?? ''
      payloadRecipientId = idNum
    }

    setError(null)
    setLineErrors({})

    const body: {
      recipient_type: string
      recipient_id?: number
      recipient_name: string
      items: Array<{ item_id: number; quantity: number }>
      notes?: string
    } = {
      recipient_type: recipientType,
      recipient_name: recipientName,
      items: validLines.map((l) => ({
        item_id: l.item_id!,
        quantity: l.quantity,
      })),
      notes: notes.trim() || undefined,
    }
    if (recipientType !== 'other' && payloadRecipientId != null) {
      body.recipient_id = payloadRecipientId
    }

    try {
      const result = await createIssuance(() =>
        api.post<ApiResponse<{ issuance_number: string; id: number }>>('/inventory/issuances', body)
      )
      if (result) {
        navigate('/inventory/issuances', {
          state: { message: `Issuance ${result.issuance_number} created.` },
        })
      }
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        return
      }
      const data =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { message?: string } } }).response?.data
          : null
      const message =
        data?.message ??
        (data && typeof (data as { detail?: string }).detail === 'string'
          ? (data as { detail: string }).detail
          : null) ??
        'Failed to create issuance.'
      const insufficientMatch = message.match(/Insufficient stock for item (\d+)/i)
      if (insufficientMatch) {
        const itemId = Number(insufficientMatch[1])
        const lineWithItem = lines.find((l) => l.item_id === itemId)
        if (lineWithItem) {
          setLineErrors((prev) => ({ ...prev, [lineWithItem.id]: message }))
        } else {
          setError(message)
        }
      } else {
        setError(message)
      }
    }
  }

  return (
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-4">
        Issue stock
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-4">
        Issue multiple items to a recipient in one go. Select recipient and add lines (item + quantity).
      </Typography>

      {(error || saveError) && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error || saveError}
        </Alert>
      )}

      <div className="grid gap-4 max-w-[560px] mb-6">
        <Typography variant="subtitle2">
          Recipient <span className="text-error">*</span>
        </Typography>
        <RadioGroup
          row
          value={recipientType}
          onChange={(value) => {
            setRecipientType(value as RecipientTypeOption)
            setRecipientId('')
            setRecipientNameOther('')
          }}
        >
          <Radio value="student" label="Student" />
          <Radio value="employee" label="Employee" />
          <Radio value="other" label="Other" />
        </RadioGroup>
        {recipientType === 'student' && (
          <Select
            value={recipientId}
            onChange={(e) => setRecipientId(e.target.value)}
            label="Student *"
            required
          >
            <option value="">Select student</option>
            {(students || []).map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.first_name} {s.last_name} ({s.student_number})
              </option>
            ))}
          </Select>
        )}
        {recipientType === 'employee' && (
          <Select
            value={recipientId}
            onChange={(e) => setRecipientId(e.target.value)}
            label="Employee *"
            required
          >
            <option value="">Select employee</option>
            {(users || []).map((u) => (
              <option key={u.id} value={String(u.id)}>
                {u.full_name}
              </option>
            ))}
          </Select>
        )}
        {recipientType === 'other' && (
          <Input
            label="Recipient name *"
            value={recipientNameOther}
            onChange={(e) => setRecipientNameOther(e.target.value)}
            placeholder="e.g. Kitchen, Maintenance"
            required
          />
        )}
        <Textarea
          label="Notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
        />
      </div>

      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <Typography variant="h6">Items to issue</Typography>
          <Button size="small" onClick={addLine}>
            Add line
          </Button>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Item</TableHeaderCell>
                <TableHeaderCell>Quantity</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>
                    <Select
                      value={line.item_id ? String(line.item_id) : ''}
                      onChange={(e) =>
                        updateLine(line.id, {
                          item_id: e.target.value ? Number(e.target.value) : null,
                        })
                      }
                      className="min-w-[260px]"
                    >
                      <option value="">Select item</option>
                      {(items || []).map((item) => (
                        <option key={item.id} value={String(item.id)}>
                          {item.name} ({item.sku_code})
                        </option>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell>
                    <div>
                      <Input
                        type="number"
                        value={line.quantity === 0 ? '' : line.quantity}
                        onChange={(e) => {
                          updateLine(line.id, { quantity: Number(e.target.value) || 0 })
                          setLineErrors((prev) => ({ ...prev, [line.id]: '' }))
                        }}
                        onFocus={(e) => e.currentTarget.select()}
                        onWheel={(e) => (e.target as HTMLInputElement).blur()}
                        min={1}
                        error={Boolean(lineErrors[line.id])}
                        className="w-24"
                      />
                      {lineErrors[line.id] && (
                        <Typography variant="caption" color="error" className="mt-1 block">
                          {lineErrors[line.id]}
                        </Typography>
                      )}
                    </div>
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => removeLine(line.id)}
                      className="min-w-0"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="flex gap-2 mt-6">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={loading || !recipientValid || !lines.some((l) => l.item_id && l.quantity > 0)}
        >
          {loading ? <Spinner size="small" /> : 'Issue stock'}
        </Button>
      </div>
    </div>
  )
}
