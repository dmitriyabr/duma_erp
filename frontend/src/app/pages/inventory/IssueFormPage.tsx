import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

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
    params: { limit: 500 },
  })
  const { data: usersData } = useApi<PaginatedResponse<UserOption>>('/users', {
    params: { limit: 500 },
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
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Issue stock
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Issue multiple items to a recipient in one go. Select recipient and add lines (item + quantity).
      </Typography>

      {error || saveError ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error || saveError}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gap: 2, maxWidth: 560, mb: 3 }}>
        <Typography variant="subtitle2">
          Recipient <Box component="span" sx={{ color: 'error.main' }}>*</Box>
        </Typography>
        <FormControl component="fieldset">
          <RadioGroup
            row
            value={recipientType}
            onChange={(e) => {
              setRecipientType(e.target.value as RecipientTypeOption)
              setRecipientId('')
              setRecipientNameOther('')
            }}
          >
            <FormControlLabel value="student" control={<Radio />} label="Student" />
            <FormControlLabel value="employee" control={<Radio />} label="Employee" />
            <FormControlLabel value="other" control={<Radio />} label="Other" />
          </RadioGroup>
        </FormControl>
        {recipientType === 'student' && (
          <FormControl fullWidth size="small" required>
            <InputLabel>Student *</InputLabel>
            <Select
              value={recipientId}
              label="Student *"
              onChange={(e) => setRecipientId(e.target.value as string)}
              displayEmpty
            >
              <MenuItem value="">Select student</MenuItem>
              {(students || []).map((s) => (
                <MenuItem key={s.id} value={String(s.id)}>
                  {s.first_name} {s.last_name} ({s.student_number})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        {recipientType === 'employee' && (
          <FormControl fullWidth size="small" required>
            <InputLabel>Employee *</InputLabel>
            <Select
              value={recipientId}
              label="Employee *"
              onChange={(e) => setRecipientId(e.target.value as string)}
              displayEmpty
            >
              <MenuItem value="">Select employee</MenuItem>
              {(users || []).map((u) => (
                <MenuItem key={u.id} value={String(u.id)}>
                  {u.full_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        {recipientType === 'other' && (
          <TextField
            label="Recipient name *"
            value={recipientNameOther}
            onChange={(e) => setRecipientNameOther(e.target.value)}
            placeholder="e.g. Kitchen, Maintenance"
            InputLabelProps={{ shrink: true }}
            required
          />
        )}
        <TextField
          label="Notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          multiline
          minRows={2}
        />
      </Box>

      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="h6">Items to issue</Typography>
          <Button size="small" onClick={addLine}>
            Add line
          </Button>
        </Box>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Item</TableCell>
              <TableCell>Quantity</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>
                  <FormControl size="small" sx={{ minWidth: 260 }}>
                    <InputLabel>Item</InputLabel>
                    <Select
                      value={line.item_id ? String(line.item_id) : ''}
                      label="Item"
                      onChange={(e) =>
                        updateLine(line.id, {
                          item_id: e.target.value ? Number(e.target.value) : null,
                        })
                      }
                      displayEmpty
                    >
                      <MenuItem value="">Select item</MenuItem>
                      {(items || []).map((item) => (
                        <MenuItem key={item.id} value={String(item.id)}>
                          {item.name} ({item.sku_code})
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    type="number"
                    value={line.quantity === 0 ? '' : line.quantity}
                    onChange={(e) => {
                      updateLine(line.id, { quantity: Number(e.target.value) || 0 })
                      setLineErrors((prev) => ({ ...prev, [line.id]: '' }))
                    }}
                    onFocus={(e) => e.currentTarget.select()}
                    onWheel={(e) => (e.target as HTMLInputElement).blur()}
                    inputProps={{ min: 1 }}
                    sx={{ width: 100 }}
                    error={Boolean(lineErrors[line.id])}
                    helperText={lineErrors[line.id]}
                  />
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
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
        <Button onClick={() => navigate('/inventory/stock')}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={loading || !recipientValid || !lines.some((l) => l.item_id && l.quantity > 0)}
        >
          {loading ? 'Submitting…' : 'Issue stock'}
        </Button>
      </Box>
    </Box>
  )
}
