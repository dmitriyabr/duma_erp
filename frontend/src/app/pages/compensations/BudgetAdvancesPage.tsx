import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import { useApi } from '../../hooks/useApi'
import type { PaginatedResponse } from '../../types/api'
import type { BudgetAdvanceSummary } from '../../types/budgets'
import { formatDate, formatMoney } from '../../utils/format'
import {
  Alert,
  Card,
  CardContent,
  Input,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TablePagination,
  TableRow,
  Typography,
  Chip,
} from '../../components/ui'

interface UserRow {
  id: number
  full_name: string
}

const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'issued', label: 'Issued' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'settled', label: 'Settled' },
  { value: 'closed', label: 'Closed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const statusColor = (status: string) => {
  if (status === 'issued' || status === 'settled' || status === 'closed') return 'success'
  if (status === 'overdue' || status === 'draft') return 'warning'
  if (status === 'cancelled') return 'error'
  return 'default'
}

export const BudgetAdvancesPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const ownOnly = user?.role === 'User'

  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState('all')
  const [employeeFilter, setEmployeeFilter] = useState<number | ''>('')
  const [budgetIdFilter, setBudgetIdFilter] = useState('')

  const { data: employeesData } = useApi<{ items: UserRow[] }>(
    !ownOnly ? '/users' : null,
    !ownOnly ? { params: { limit: USERS_LIST_LIMIT, is_active: true } } : undefined,
    [ownOnly]
  )

  const advancesUrl = useMemo(() => {
    const params = new URLSearchParams()
    params.set('page', String(page + 1))
    params.set('limit', String(limit))
    if (statusFilter !== 'all') params.set('status', statusFilter)

    if (ownOnly) {
      return `/budgets/my/advances?${params.toString()}`
    }

    if (employeeFilter) params.set('employee_id', String(employeeFilter))
    if (budgetIdFilter.trim()) params.set('budget_id', budgetIdFilter.trim())
    return `/budgets/advances?${params.toString()}`
  }, [page, limit, statusFilter, ownOnly, employeeFilter, budgetIdFilter])

  const { data, loading, error } = useApi<PaginatedResponse<BudgetAdvanceSummary>>(advancesUrl, undefined, [advancesUrl])

  const advances = data?.items || []
  const total = data?.total || 0

  return (
    <div>
      <div className="mb-4">
        <Typography variant="h4">Budget advances</Typography>
        <Typography variant="body2" color="secondary" className="mt-1">
          {ownOnly ? 'Money currently issued to you and still on hand.' : 'Issued advances, balances, and settlement status.'}
        </Typography>
      </div>

      {error ? (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      ) : null}

      <div className="flex flex-wrap gap-4 mb-4">
        <div className="min-w-[220px]">
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} label="Status">
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>

        {!ownOnly ? (
          <div className="min-w-[240px]">
            <Select
              label="Employee"
              value={employeeFilter}
              onChange={(e) => setEmployeeFilter(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">All employees</option>
              {(employeesData?.items || []).map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </Select>
          </div>
        ) : null}

        {!ownOnly ? (
          <div className="min-w-[180px]">
            <Input
              label="Budget ID"
              value={budgetIdFilter}
              onChange={(e) => setBudgetIdFilter(e.target.value)}
              inputMode="numeric"
            />
          </div>
        ) : null}
      </div>

      <div className="md:hidden space-y-3">
        {advances.map((advance) => (
          <Card
            key={advance.id}
            className={!ownOnly ? 'cursor-pointer' : undefined}
            onClick={!ownOnly ? () => navigate(`/compensations/budgets/${advance.budget_id}`) : undefined}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Typography variant="subtitle1">{advance.advance_number}</Typography>
                  <Typography variant="body2" color="secondary">
                    {advance.budget_number} · {advance.budget_name}
                  </Typography>
                </div>
                <Chip size="small" label={advance.status} color={statusColor(advance.status)} />
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div>
                  <Typography variant="caption" color="secondary">Issued</Typography>
                  <Typography>{formatMoney(advance.amount_issued)}</Typography>
                </div>
                <div>
                  <Typography variant="caption" color="secondary">Open balance</Typography>
                  <Typography>{formatMoney(advance.open_balance)}</Typography>
                </div>
                <div>
                  <Typography variant="caption" color="secondary">Issue date</Typography>
                  <Typography>{formatDate(advance.issue_date)}</Typography>
                </div>
                <div>
                  <Typography variant="caption" color="secondary">Due</Typography>
                  <Typography>{formatDate(advance.settlement_due_date)}</Typography>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner size="medium" />
          </div>
        ) : null}

        {!advances.length && !loading ? (
          <Card>
            <CardContent className="p-6 text-center">
              <Typography color="secondary">No advances found</Typography>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div className="hidden md:block bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Advance</TableHeaderCell>
              <TableHeaderCell>Budget</TableHeaderCell>
              {!ownOnly ? <TableHeaderCell>Employee</TableHeaderCell> : null}
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Due</TableHeaderCell>
              <TableHeaderCell align="right">Issued</TableHeaderCell>
              <TableHeaderCell align="right">Open Balance</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {advances.map((advance) => (
              <TableRow
                key={advance.id}
                className={!ownOnly ? 'cursor-pointer' : undefined}
                onClick={!ownOnly ? () => navigate(`/compensations/budgets/${advance.budget_id}`) : undefined}
              >
                <TableCell>
                  <div>
                    <Typography variant="body2" className="font-medium">
                      {advance.advance_number}
                    </Typography>
                    <Typography variant="caption" color="secondary">
                      {advance.source_type}
                    </Typography>
                  </div>
                </TableCell>
                <TableCell>
                  <div>
                    <Typography variant="body2">{advance.budget_number}</Typography>
                    <Typography variant="caption" color="secondary">
                      {advance.budget_name}
                    </Typography>
                  </div>
                </TableCell>
                {!ownOnly ? <TableCell>{advance.employee_name}</TableCell> : null}
                <TableCell>{formatDate(advance.issue_date)}</TableCell>
                <TableCell>{formatDate(advance.settlement_due_date)}</TableCell>
                <TableCell align="right">{formatMoney(advance.amount_issued)}</TableCell>
                <TableCell align="right">{formatMoney(advance.open_balance)}</TableCell>
                <TableCell>
                  <Chip size="small" label={advance.status} color={statusColor(advance.status)} />
                </TableCell>
              </TableRow>
            ))}

            {loading ? (
              <TableRow>
                <td colSpan={ownOnly ? 7 : 8} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            ) : null}

            {!advances.length && !loading ? (
              <TableRow>
                <td colSpan={ownOnly ? 7 : 8} className="px-4 py-8 text-center">
                  <Typography color="secondary">No advances found</Typography>
                </td>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(rowsPerPage) => {
            setLimit(rowsPerPage)
            setPage(0)
          }}
        />
      </div>
    </div>
  )
}
