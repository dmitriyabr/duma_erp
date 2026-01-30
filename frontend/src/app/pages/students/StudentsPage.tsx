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
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { api } from '../../services/api'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { formatMoney } from '../../utils/format'

type Gender = 'male' | 'female'
type StudentStatus = 'active' | 'inactive'

interface StudentRow {
  id: number
  student_number: string
  full_name: string
  date_of_birth?: string | null
  gender: Gender
  grade_id: number
  grade_name?: string | null
  transport_zone_id?: number | null
  transport_zone_name?: string | null
  guardian_name: string
  guardian_phone: string
  guardian_email?: string | null
  status: StudentStatus
  enrollment_date?: string | null
  notes?: string | null
}

interface GradeOption {
  id: number
  name: string
  code: string
  is_active: boolean
}

interface TransportZoneOption {
  id: number
  zone_name: string
  is_active: boolean
}

interface StudentBalance {
  student_id: number
  available_balance: number
}

type DiscountValueType = 'fixed' | 'percentage'

const emptyForm = {
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: 'male' as Gender,
  grade_id: '',
  transport_zone_id: '',
  guardian_name: '',
  guardian_phone: '',
  guardian_email: '',
  enrollment_date: new Date().toISOString().slice(0, 10),
  notes: '',
}

const emptyDiscountForm = {
  enabled: false,
  value_type: 'percentage' as DiscountValueType,
  value: '',
  reason_text: '',
}

const parseNumber = (value: unknown) => {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? 0 : parsed
  }
  return 0
}

export const StudentsPage = () => {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(25)
  const [statusFilter, setStatusFilter] = useState<'all' | StudentStatus>('all')
  const [gradeFilter, setGradeFilter] = useState<number | 'all'>('all')
  const [transportFilter, setTransportFilter] = useState<number | 'all'>('all')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 400)
  const [balanceMap, setBalanceMap] = useState<Record<number, number>>({})
  const [debtMap, setDebtMap] = useState<Record<number, number>>({})
  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })
  const [discountForm, setDiscountForm] = useState({ ...emptyDiscountForm })

  const { data: grades } = useApi<GradeOption[]>('/students/grades', { params: { include_inactive: true } })
  const { data: transportZones } = useApi<TransportZoneOption[]>('/terms/transport-zones', {
    params: { include_inactive: true },
  })

  const requestParams = useMemo(() => {
    const params: Record<string, string | number> = {
      page: page + 1,
      limit,
    }
    if (statusFilter !== 'all') {
      params.status = statusFilter
    }
    if (gradeFilter !== 'all') {
      params.grade_id = gradeFilter
    }
    if (transportFilter !== 'all') {
      params.transport_zone_id = transportFilter
    }
    if (debouncedSearch.trim()) {
      params.search = debouncedSearch.trim()
    }
    return params
  }, [page, limit, statusFilter, gradeFilter, transportFilter, debouncedSearch])

  const {
    data: studentsData,
    loading,
    error,
    refetch: refetchStudents,
  } = useApi<PaginatedResponse<StudentRow>>('/students', { params: requestParams }, [requestParams])

  const rows = studentsData?.items || []
  const total = studentsData?.total || 0

  const fetchBalancesAndDebts = async (students: StudentRow[]) => {
    if (!students.length) {
      setBalanceMap({})
      setDebtMap({})
      return
    }
    const ids = students.map((s) => s.id)
    try {
      const [balanceRes, totalsRes] = await Promise.all([
        api.post<ApiResponse<{ balances: StudentBalance[] }>>('/payments/students/balances-batch', {
          student_ids: ids,
        }),
        api.get<ApiResponse<{ totals: Array<{ student_id: number; total_due: number }> }>>(
          '/invoices/outstanding-totals',
          { params: { student_ids: ids } }
        ),
      ])
      const balances = (balanceRes.data.data.balances || []).reduce<Record<number, number>>(
        (acc, b) => {
          acc[b.student_id] = parseNumber(b.available_balance)
          return acc
        },
        {}
      )
      setBalanceMap(balances)
      const debts = (totalsRes.data.data.totals || []).reduce<Record<number, number>>(
        (acc, t) => {
          acc[t.student_id] = parseNumber(t.total_due)
          return acc
        },
        {}
      )
      setDebtMap(debts)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        return
      }
      console.error('Failed to load balances/debts:', err)
    }
  }

  useEffect(() => {
    const list = studentsData?.items ?? []
    if (list.length) fetchBalancesAndDebts(list)
    else {
      setBalanceMap({})
      setDebtMap({})
    }
  }, [studentsData])

  const { execute: createStudent, loading: saving, error: saveError } = useApiMutation<StudentRow>()

  const openCreate = () => {
    setForm({ ...emptyForm })
    setDiscountForm({ ...emptyDiscountForm })
    setDialogOpen(true)
  }

  const submitCreate = async () => {
    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      date_of_birth: form.date_of_birth || null,
      gender: form.gender,
      grade_id: Number(form.grade_id),
      transport_zone_id: form.transport_zone_id ? Number(form.transport_zone_id) : null,
      guardian_name: form.guardian_name.trim(),
      guardian_phone: form.guardian_phone.trim(),
      guardian_email: form.guardian_email.trim() || null,
      enrollment_date: form.enrollment_date || null,
      notes: form.notes.trim() || null,
    }

    const student = await createStudent(() => api.post<ApiResponse<StudentRow>>('/students', payload))
    if (!student) return

    if (discountForm.enabled && discountForm.value) {
      try {
        await api.post('/discounts/student', {
          student_id: student.id,
          value_type: discountForm.value_type,
          value: Number(discountForm.value),
          reason_text: discountForm.reason_text.trim() || null,
        })
      } catch (err) {
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          return
        }
        console.error('Failed to create student discount:', err)
      }
    }

    setDialogOpen(false)
    await refetchStudents()
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Students
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New student
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          size="small"
          placeholder="Name, number, guardian"
          InputLabelProps={{ shrink: true }}
        />
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => setStatusFilter(event.target.value as 'all' | StudentStatus)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="inactive">Inactive</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Grade</InputLabel>
          <Select
            value={gradeFilter}
            label="Grade"
            onChange={(event) => setGradeFilter(event.target.value as number | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            {(grades || []).map((grade) => (
              <MenuItem key={grade.id} value={grade.id}>
                {grade.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Transport zone</InputLabel>
          <Select
            value={transportFilter}
            label="Transport zone"
            onChange={(event) => setTransportFilter(event.target.value as number | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            {(transportZones || []).map((zone) => (
              <MenuItem key={zone.id} value={zone.id}>
                {zone.zone_name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {error || saveError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || saveError}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Student #</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>Grade</TableCell>
            <TableCell>Transport zone</TableCell>
            <TableCell>Guardian</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Debt</TableCell>
            <TableCell>Credit</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} hover>
              <TableCell>{row.student_number}</TableCell>
              <TableCell>{row.full_name}</TableCell>
              <TableCell>{row.grade_name ?? '—'}</TableCell>
              <TableCell>{row.transport_zone_name ?? '—'}</TableCell>
              <TableCell>
                <Box>
                  <Typography variant="body2">{row.guardian_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {row.guardian_phone}
                  </Typography>
                </Box>
              </TableCell>
              <TableCell>
                <Chip
                  size="small"
                  label={row.status === 'active' ? 'Active' : 'Inactive'}
                  color={row.status === 'active' ? 'success' : 'default'}
                />
              </TableCell>
              <TableCell>{formatMoney(debtMap[row.id])}</TableCell>
              <TableCell>{formatMoney(balanceMap[row.id])}</TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => navigate(`/students/${row.id}`)}>
                  Open
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={9} align="center">
                No students found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
      />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Create student</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <TextField
              label="First name"
              value={form.first_name}
              onChange={(event) => setForm({ ...form, first_name: event.target.value })}
              required
            />
            <TextField
              label="Last name"
              value={form.last_name}
              onChange={(event) => setForm({ ...form, last_name: event.target.value })}
              required
            />
            <TextField
              label="Date of birth"
              type="date"
              value={form.date_of_birth}
              onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            <FormControl>
              <InputLabel>Gender</InputLabel>
              <Select
                value={form.gender}
                label="Gender"
                onChange={(event) => setForm({ ...form, gender: event.target.value as Gender })}
              >
                <MenuItem value="male">Male</MenuItem>
                <MenuItem value="female">Female</MenuItem>
              </Select>
            </FormControl>
            <FormControl>
              <InputLabel>Grade</InputLabel>
              <Select
                value={form.grade_id}
                label="Grade"
                onChange={(event) => setForm({ ...form, grade_id: event.target.value as string })}
              >
                {(grades || []).map((grade) => (
                  <MenuItem key={grade.id} value={String(grade.id)}>
                    {grade.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <InputLabel>Transport zone</InputLabel>
              <Select
                value={form.transport_zone_id}
                label="Transport zone"
                onChange={(event) => setForm({ ...form, transport_zone_id: event.target.value as string })}
              >
                <MenuItem value="">None</MenuItem>
                {(transportZones || []).map((zone) => (
                  <MenuItem key={zone.id} value={String(zone.id)}>
                    {zone.zone_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Enrollment date"
              type="date"
              value={form.enrollment_date}
              onChange={(event) => setForm({ ...form, enrollment_date: event.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Box>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            <TextField
              label="Guardian name"
              value={form.guardian_name}
              onChange={(event) => setForm({ ...form, guardian_name: event.target.value })}
              required
            />
            <TextField
              label="Guardian phone"
              value={form.guardian_phone}
              onChange={(event) => setForm({ ...form, guardian_phone: event.target.value })}
              placeholder="+254..."
              InputLabelProps={{ shrink: true }}
              required
            />
            <TextField
              label="Guardian email"
              value={form.guardian_email}
              onChange={(event) => setForm({ ...form, guardian_email: event.target.value })}
            />
          </Box>
          <TextField
            label="Notes"
            value={form.notes}
            onChange={(event) => setForm({ ...form, notes: event.target.value })}
            multiline
            minRows={2}
          />

          <Box>
            <FormControlLabel
              control={
                <Switch
                  checked={discountForm.enabled}
                  onChange={(event) =>
                    setDiscountForm({ ...discountForm, enabled: event.target.checked })
                  }
                />
              }
              label="Add student discount"
            />
            {discountForm.enabled ? (
              <Box
                sx={{
                  mt: 1,
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                }}
              >
                <FormControl>
                  <InputLabel>Value type</InputLabel>
                  <Select
                    value={discountForm.value_type}
                    label="Value type"
                    onChange={(event) =>
                      setDiscountForm({
                        ...discountForm,
                        value_type: event.target.value as DiscountValueType,
                      })
                    }
                  >
                    <MenuItem value="percentage">Percentage</MenuItem>
                    <MenuItem value="fixed">Fixed</MenuItem>
                  </Select>
                </FormControl>
                <TextField
                  label={discountForm.value_type === 'percentage' ? 'Percent' : 'Amount'}
                  value={discountForm.value}
                  onChange={(event) =>
                    setDiscountForm({ ...discountForm, value: event.target.value })
                  }
                  type="number"
                />
                <TextField
                  label="Reason (optional)"
                  value={discountForm.reason_text}
                  onChange={(event) =>
                    setDiscountForm({ ...discountForm, reason_text: event.target.value })
                  }
                />
              </Box>
            ) : null}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitCreate} disabled={saving}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
