import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useAuth } from '../../auth/AuthContext'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TablePagination, TableRow } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { canManageActivities } from '../../utils/permissions'

interface ActivitySummaryRow {
  id: number
  activity_number: string
  code?: string | null
  name: string
  activity_date?: string | null
  due_date?: string | null
  status: string
  audience_type: string
  amount: string
  participants_total: number
  planned_count: number
  invoiced_count: number
  paid_count: number
  total_outstanding_amount: string
}

const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'published', label: 'Published' },
  { value: 'closed', label: 'Closed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const audienceLabels: Record<string, string> = {
  all_active: 'All active',
  grades: 'Selected grades',
  manual: 'Manual',
}

export const ActivitiesListPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = canManageActivities(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (search.trim()) params.search = search.trim()
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => sp.append(key, String(value)))
    return `/activities?${sp.toString()}`
  }, [page, limit, search, statusFilter])

  const { data, loading, error } = useApi<PaginatedResponse<ActivitySummaryRow>>(url)
  const rows = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
        <div>
          <Typography variant="h4">Paid activities</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            Create school events, snapshot the audience, and invoice students in bulk.
          </Typography>
        </div>
        {canManage && (
          <Button variant="contained" onClick={() => navigate('/billing/activities/new')}>
            New activity
          </Button>
        )}
      </div>

      <div className="flex gap-4 mb-4 flex-wrap items-center">
        <div className="flex-1 min-w-[220px]">
          <Input
            label="Search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(0)
            }}
            placeholder="Activity #, name, code"
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value)
              setPage(0)
            }}
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
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
              <TableHeaderCell>Activity</TableHeaderCell>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Due</TableHeaderCell>
              <TableHeaderCell>Audience</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell align="right">Participants</TableHeaderCell>
              <TableHeaderCell align="right">Invoiced</TableHeaderCell>
              <TableHeaderCell align="right">Paid</TableHeaderCell>
              <TableHeaderCell align="right">Outstanding</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">{row.name}</span>
                    <span className="text-xs text-slate-500">
                      {row.activity_number}
                      {row.code ? ` · ${row.code}` : ''}
                    </span>
                  </div>
                </TableCell>
                <TableCell>{row.activity_date ? formatDate(row.activity_date) : '—'}</TableCell>
                <TableCell>{row.due_date ? formatDate(row.due_date) : '—'}</TableCell>
                <TableCell>{audienceLabels[row.audience_type] ?? row.audience_type}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.amount))}</TableCell>
                <TableCell align="right">{row.participants_total}</TableCell>
                <TableCell align="right">{row.invoiced_count}</TableCell>
                <TableCell align="right">{row.paid_count}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.total_outstanding_amount))}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell align="right">
                  <div className="flex justify-end gap-2">
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => navigate(`/billing/activities/${row.id}`)}
                    >
                      View
                    </Button>
                    {canManage && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => navigate(`/billing/activities/${row.id}/edit`)}
                      >
                        Edit
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={11} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!loading && !rows.length && (
              <TableRow>
                <td colSpan={11} className="px-4 py-8 text-center">
                  <Typography color="secondary">No activities found</Typography>
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
          rowsPerPageOptions={[25, 50, 100]}
        />
      </div>
    </div>
  )
}
