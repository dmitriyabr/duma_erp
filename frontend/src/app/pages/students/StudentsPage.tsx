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
import { formatStudentNumberShort } from '../../utils/studentNumber'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

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
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Students
        </Typography>
        {!readOnly && (
          <Button variant="contained" onClick={() => navigate('/students/new')}>
            New student
          </Button>
        )}
      </div>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, number, guardian"
          />
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | StudentStatus)}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </Select>
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Grade"
            value={gradeFilter}
            onChange={(e) => setGradeFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          >
            <option value="all">All</option>
            {(grades || []).map((grade) => (
              <option key={grade.id} value={grade.id}>
                {grade.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[200px]">
          <Select
            label="Transport zone"
            value={transportFilter}
            onChange={(e) => setTransportFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          >
            <option value="all">All</option>
            {(transportZones || []).map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.zone_name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Student #</TableHeaderCell>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Grade</TableHeaderCell>
              <TableHeaderCell>Transport zone</TableHeaderCell>
              <TableHeaderCell>Guardian</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Balance</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={row.id}
                className="cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => navigate(`/students/${row.id}`)}
              >
                <TableCell>{formatStudentNumberShort(row.student_number)}</TableCell>
                <TableCell>{row.full_name}</TableCell>
                <TableCell>{row.grade_name ?? '—'}</TableCell>
                <TableCell>{row.transport_zone_name ?? '—'}</TableCell>
                <TableCell>
                  <div>
                    <Typography variant="body2">{row.guardian_name}</Typography>
                    <Typography variant="caption" color="secondary">
                      {row.guardian_phone}
                    </Typography>
                  </div>
                </TableCell>
                <TableCell>
                  <Chip
                    label={row.status === 'active' ? 'Active' : 'Inactive'}
                    color={row.status === 'active' ? 'success' : 'default'}
                    size="small"
                  />
                </TableCell>
                <TableCell>{formatMoney(row.balance ?? 0)}</TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!rows.length && !loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Typography color="secondary">No students found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(newLimit) => {
            setLimit(newLimit)
            setPage(0)
          }}
        />
      </div>
    </div>
  )
}
