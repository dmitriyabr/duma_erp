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
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { isAccountant } from '../../utils/permissions'
import type { PaginatedResponse } from '../../types/api'
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
  // Balance fields (optional, included when include_balance=true)
  available_balance?: number | null
  outstanding_debt?: number | null
  balance?: number | null // net: available_balance - outstanding_debt
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

  const { grades, transportZones } = useReferencedData()

  const requestParams = useMemo(() => {
    const params: Record<string, string | number | boolean> = {
      page: page + 1,
      limit,
      include_balance: true, // Always include balance in response
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
              <TableCell>{formatMoney(row.balance ?? 0)}</TableCell>
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
