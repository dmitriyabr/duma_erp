import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
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
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { isAccountant } from '../../utils/permissions'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApi } from '../../hooks/useApi'
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

interface StudentBalance {
  student_id: number
  available_balance: number
  outstanding_debt: number
  balance: number // net: available_balance − outstanding_debt (computed on backend)
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
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(DEFAULT_PAGE_SIZE)
  const [statusFilter, setStatusFilter] = useState<'all' | StudentStatus>('all')
  const [gradeFilter, setGradeFilter] = useState<number | 'all'>('all')
  const [transportFilter, setTransportFilter] = useState<number | 'all'>('all')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 400)
  const [balanceMap, setBalanceMap] = useState<Record<number, number>>({}) // student_id -> net balance (from backend)

  const { grades, transportZones } = useReferencedData()

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
  } = useApi<PaginatedResponse<StudentRow>>('/students', { params: requestParams }, [requestParams])

  const rows = studentsData?.items || []
  const total = studentsData?.total || 0

  const fetchBalances = async (students: StudentRow[]) => {
    if (!students.length) {
      setBalanceMap({})
      return
    }
    const ids = students.map((s) => s.id)
    try {
      const res = await api.post<ApiResponse<{ balances: StudentBalance[] }>>(
        '/payments/students/balances-batch',
        { student_ids: ids }
      )
      const map = (res.data.data.balances || []).reduce<Record<number, number>>(
        (acc, b) => {
          acc[b.student_id] = parseNumber(b.balance)
          return acc
        },
        {}
      )
      setBalanceMap(map)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        return
      }
      console.error('Failed to load balances:', err)
    }
  }

  useEffect(() => {
    const list = studentsData?.items ?? []
    if (list.length) fetchBalances(list)
    else setBalanceMap({})
  }, [studentsData])

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Students
        </Typography>
        {!readOnly && (
          <Button variant="contained" onClick={() => navigate('/students/new')}>
            New student
          </Button>
        )}
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

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
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
            <TableCell>Balance</TableCell>
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
              <TableCell>{formatMoney(balanceMap[row.id] ?? 0)}</TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => navigate(`/students/${row.id}`)}>
                  Open
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {loading ? (
            <TableRow>
              <TableCell colSpan={8} align="center">
                Loading…
              </TableCell>
            </TableRow>
          ) : null}
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={8} align="center">
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
    </Box>
  )
}
