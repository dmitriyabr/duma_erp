import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

interface GRNRow {
  id: number
  grn_number: string
  po_id: number
  status: string
  received_date: string
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const GRNListPage = () => {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [poIdFilter, setPoIdFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (poIdFilter.trim()) params.po_id = Number(poIdFilter)
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo

    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/procurement/grns?${sp.toString()}`
  }, [page, limit, statusFilter, poIdFilter, dateFrom, dateTo])

  const { data, loading, error } = useApi<PaginatedResponse<GRNRow>>(url)

  const grns = data?.items || []
  const total = data?.total || 0

  const statusColor = (status: string) => {
    if (status === 'approved') return 'success'
    if (status === 'cancelled') return 'default'
    return 'warning'
  }

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Goods Received
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="min-w-[120px]">
          <Input
            label="PO ID"
            type="number"
            value={poIdFilter}
            onChange={(e) => setPoIdFilter(e.target.value)}
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[160px]">
          <Input
            label="Date from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div className="min-w-[160px]">
          <Input
            label="Date to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
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
              <TableHeaderCell>GRN Number</TableHeaderCell>
              <TableHeaderCell>PO ID</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Received date</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {grns.map((grn) => (
              <TableRow key={grn.id}>
                <TableCell>{grn.grn_number}</TableCell>
                <TableCell>{grn.po_id}</TableCell>
                <TableCell>
                  <Chip size="small" label={grn.status} color={statusColor(grn.status)} />
                </TableCell>
                <TableCell>{formatDate(grn.received_date)}</TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => navigate(`/procurement/grn/${grn.id}`)}>
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <TableCell colSpan={5} align="center" className="py-8">
                  <Spinner size="medium" />
                </TableCell>
              </TableRow>
            )}
            {!grns.length && !loading && (
              <TableRow>
                <TableCell colSpan={5} align="center" className="py-8">
                  <Typography color="secondary">No GRNs found</Typography>
                </TableCell>
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
