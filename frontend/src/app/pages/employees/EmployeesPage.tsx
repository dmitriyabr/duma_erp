import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { isAccountant } from '../../utils/permissions'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  TablePagination,
} from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

type EmployeeStatus = 'active' | 'inactive' | 'terminated'

interface EmployeeImportResult {
  rows_processed: number
  employees_created: number
  employees_updated: number
  errors: Array<{ row: number; message: string }>
}

interface EmployeeRow {
  id: number
  employee_number: string
  surname: string
  first_name: string
  second_name?: string | null
  job_title?: string | null
  mobile_phone?: string | null
  email?: string | null
  status: EmployeeStatus
}

export const EmployeesPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(DEFAULT_PAGE_SIZE)
  const [statusFilter, setStatusFilter] = useState<'all' | EmployeeStatus>('all')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 400)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<EmployeeImportResult | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const { execute: importCsv, loading: importing } = useApiMutation<EmployeeImportResult>()

  const requestParams = useMemo(() => {
    const params: Record<string, string | number> = {
      page: page + 1,
      limit,
    }
    if (statusFilter !== 'all') {
      params.status = statusFilter
    }
    if (debouncedSearch.trim()) {
      params.search = debouncedSearch.trim()
    }
    return params
  }, [page, limit, statusFilter, debouncedSearch])

  const {
    data: employeesData,
    loading,
    error,
  } = useApi<PaginatedResponse<EmployeeRow>>('/employees', { params: requestParams }, [requestParams])

  const rows = employeesData?.items || []
  const total = employeesData?.total || 0

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleImportSubmit = async () => {
    const file = fileInputRef.current?.files?.[0]
    if (!file) {
      return
    }
    setImportResult(null)

    const formData = new FormData()
    formData.append('file', file)

    const result = await importCsv(() =>
      api.post<ApiResponse<EmployeeImportResult>>('/employees/import-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    )

    if (result) {
      setImportResult(result)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleExportCsv = async () => {
    setExportError(null)
    setExporting(true)
    try {
      const response = await api.get('/employees/export?format=csv', { responseType: 'blob' })
      const disposition = response.headers['content-disposition']
      const filenameMatch = disposition?.match(/filename="?([^";]+)"?/)
      const filename = filenameMatch?.[1] ?? 'employees.csv'
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: string }).message)
          : 'Export failed'
      setExportError(message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Employees
        </Typography>
        {!readOnly && (
          <div className="flex gap-2">
            <Button variant="contained" onClick={() => navigate('/employees/new')}>
              New employee
            </Button>
            <Button
              variant="outlined"
              onClick={handleExportCsv}
              disabled={exporting}
            >
              {exporting ? 'Exporting...' : 'Export CSV'}
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
            <Button variant="outlined" onClick={handleImportClick} disabled={importing}>
              {selectedFile ? `Import: ${selectedFile.name}` : 'Import from CSV'}
            </Button>
            {selectedFile && (
              <Button
                variant="contained"
                onClick={handleImportSubmit}
                disabled={importing}
              >
                {importing ? <Spinner size="small" /> : 'Upload'}
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, phone, ID, email"
          />
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | EmployeeStatus)}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="terminated">Terminated</option>
          </Select>
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}
      {exportError && (
        <Alert severity="error" className="mb-4" onClose={() => setExportError(null)}>
          {exportError}
        </Alert>
      )}
      {importResult && (
        <Alert severity="success" className="mb-4">
          Imported {importResult.rows_processed} rows, created {importResult.employees_created} employees,
          updated {importResult.employees_updated}.{' '}
          {importResult.errors.length > 0 && `Errors: ${importResult.errors.length} rows.`}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Employee #</TableHeaderCell>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Job title</TableHeaderCell>
              <TableHeaderCell>Phone</TableHeaderCell>
              <TableHeaderCell>Email</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={row.id}
                className="cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => navigate(`/employees/${row.id}`)}
              >
                <TableCell>{row.employee_number}</TableCell>
                <TableCell>
                  {row.first_name} {row.second_name ? `${row.second_name} ` : ''}{row.surname}
                </TableCell>
                <TableCell>{row.job_title || '—'}</TableCell>
                <TableCell>{row.mobile_phone || '—'}</TableCell>
                <TableCell>{row.email || '—'}</TableCell>
                <TableCell>
                  <Chip
                    label={row.status.charAt(0).toUpperCase() + row.status.slice(1)}
                    color={row.status === 'active' ? 'success' : 'default'}
                    size="small"
                  />
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!rows.length && !loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Typography color="secondary">No employees found</Typography>
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

