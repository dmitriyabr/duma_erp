import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download } from 'lucide-react'
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
import { TableSortLabel } from '../../components/ui/TableSortLabel'
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
  billing_account_name?: string | null
  // Balance fields (optional, included when include_balance=true)
  available_balance?: number | null
  outstanding_debt?: number | null
  balance?: number | null
}

type SortField =
  | 'student_number'
  | 'full_name'
  | 'grade_name'
  | 'transport_zone_name'
  | 'guardian_name'
  | 'status'
  | 'balance'

type SortDirection = 'asc' | 'desc'

const sortableColumns: Array<{ field: SortField; label: string }> = [
  { field: 'student_number', label: 'Student #' },
  { field: 'full_name', label: 'Name' },
  { field: 'grade_name', label: 'Grade' },
  { field: 'transport_zone_name', label: 'Transport zone' },
  { field: 'guardian_name', label: 'Guardian' },
  { field: 'status', label: 'Status' },
  { field: 'balance', label: 'Student balance' },
]

const getSortValue = (row: StudentRow, field: SortField) => {
  if (field === 'balance') {
    return row.balance ?? 0
  }
  return row[field] ?? ''
}

const escapeCsvValue = (value: string | number | null | undefined) => {
  const normalizedValue = value == null ? '' : String(value)
  return `"${normalizedValue.replace(/"/g, '""')}"`
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
  const [sortField, setSortField] = useState<SortField>('full_name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
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
  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const left = getSortValue(a, sortField)
      const right = getSortValue(b, sortField)

      const comparison = typeof left === 'number' && typeof right === 'number'
        ? left - right
        : String(left).localeCompare(String(right), undefined, {
            sensitivity: 'base',
            numeric: true,
          })

      return sortDirection === 'asc' ? comparison : -comparison
    })
  }, [rows, sortDirection, sortField])

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDirection((currentDirection) => currentDirection === 'asc' ? 'desc' : 'asc')
      return
    }

    setSortField(field)
    setSortDirection('asc')
  }

  const exportCsv = () => {
    const headers = [
      'Student #',
      'Name',
      'Grade',
      'Transport zone',
      'Guardian name',
      'Guardian phone',
      'Status',
      'Student balance',
    ]
    const body = sortedRows.map((row) => [
      formatStudentNumberShort(row.student_number),
      row.full_name,
      row.grade_name ?? '',
      row.transport_zone_name ?? '',
      row.guardian_name,
      row.guardian_phone,
      row.status === 'active' ? 'Active' : 'Inactive',
      row.balance ?? 0,
    ])
    const csv = [headers, ...body]
      .map((line) => line.map(escapeCsvValue).join(','))
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'students.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Students
        </Typography>
        <div className="flex items-center gap-2">
          <Button variant="outlined" onClick={exportCsv} disabled={!sortedRows.length}>
            <Download className="w-4 h-4 mr-2" />
            Export CSV
          </Button>
          {!readOnly && (
            <Button variant="contained" onClick={() => navigate('/students/new')}>
              New admission
            </Button>
          )}
        </div>
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
              {sortableColumns.map((column) => (
                <TableHeaderCell key={column.field}>
                  <TableSortLabel
                    active={sortField === column.field}
                    direction={sortDirection}
                    onClick={() => handleSort(column.field)}
                  >
                    {column.label}
                  </TableSortLabel>
                </TableHeaderCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedRows.map((row) => (
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
                <TableCell>
                  <Typography variant="body2">{formatMoney(row.balance ?? 0)}</Typography>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!sortedRows.length && !loading && (
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
