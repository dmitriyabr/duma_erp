import { Download } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { api } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'
import { isSuperAdmin } from '../../utils/permissions'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Card, CardContent } from '../../components/ui/Card'
import { Tooltip } from '../../components/ui/Tooltip'
import { Spinner } from '../../components/ui/Spinner'

interface ClaimRow {
  id: number
  claim_number: string
  employee_id: number
  amount: number
  description: string
  expense_date: string
  status: string
  paid_amount: number
  remaining_amount: number
  proof_attachment_id: number | null
}

interface UserRow {
  id: number
  full_name: string
}

interface BalanceResponse {
  employee_id: number
  total_approved: number
  total_paid: number
  balance: number
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'partially_paid', label: 'Partially Paid' },
  { value: 'paid', label: 'Paid' },
]

const statusColor = (status: string) => {
  if (status === 'approved' || status === 'paid') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'pending_approval' || status === 'partially_paid') return 'warning'
  return 'info'
}

export const ExpenseClaimsListPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const userIsSuperAdmin = isSuperAdmin(user)

  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [employeeFilter, setEmployeeFilter] = useState<number | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const claimsUrl = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    // Only USER role is restricted to own claims; Admin and Accountant see all
    if (user?.role === 'User' && user?.id) params.employee_id = user.id
    else if (userIsSuperAdmin && employeeFilter) params.employee_id = Number(employeeFilter)
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo

    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/compensations/claims?${sp.toString()}`
  }, [page, limit, statusFilter, employeeFilter, dateFrom, dateTo, userIsSuperAdmin, user])

  const { data: claimsData, loading, error } = useApi<PaginatedResponse<ClaimRow>>(claimsUrl)
  const { data: employeesData } = useApi<{ items: UserRow[] }>(
    userIsSuperAdmin ? '/users' : null,
    userIsSuperAdmin ? { params: { limit: USERS_LIST_LIMIT } } : undefined,
    [userIsSuperAdmin]
  )
  const { data: myBalance } = useApi<BalanceResponse>(
    user?.id && !userIsSuperAdmin ? `/compensations/payouts/employees/${user.id}/balance` : null
  )

  const claims = claimsData?.items || []
  const total = claimsData?.total || 0
  const employees = employeesData?.items || []

  const downloadAttachment = async (attachmentId: number) => {
    try {
      const res = await api.get(`/attachments/${attachmentId}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `attachment_${attachmentId}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // ignore
    }
  }

  const colSpan = userIsSuperAdmin ? 9 : 8

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Employee Expenses Claims
      </Typography>

      {!userIsSuperAdmin && myBalance && (
        <div className="mb-6">
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="secondary" className="mb-2">
                My Balance
              </Typography>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Total Approved
                  </Typography>
                  <Typography variant="h6" className="mt-1">{formatMoney(myBalance.total_approved)}</Typography>
                </div>
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Total Paid
                  </Typography>
                  <Typography variant="h6" className="mt-1">{formatMoney(myBalance.total_paid)}</Typography>
                </div>
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Balance
                  </Typography>
                  <Typography variant="h6" className={myBalance.balance > 0 ? 'text-error mt-1' : 'mt-1'}>
                    {formatMoney(myBalance.balance)}
                  </Typography>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex gap-4 mb-4 flex-wrap">
        {userIsSuperAdmin && (
          <div className="min-w-[200px]">
            <Select
              label="Employee"
              value={employeeFilter}
              onChange={(e) => {
                const val = e.target.value
                setEmployeeFilter(val === '' ? '' : Number(val))
              }}
            >
              <option value="">All employees</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.full_name}
                </option>
              ))}
            </Select>
          </div>
        )}
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
              <TableHeaderCell>Claim Number</TableHeaderCell>
              {userIsSuperAdmin && <TableHeaderCell>Employee</TableHeaderCell>}
              <TableHeaderCell>Description</TableHeaderCell>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell align="right">Paid</TableHeaderCell>
              <TableHeaderCell align="right">Remaining</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="center">File</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {claims.map((claim) => (
              <TableRow
                key={claim.id}
                onClick={() => navigate(`/compensations/claims/${claim.id}`)}
                className="cursor-pointer"
              >
                <TableCell>{claim.claim_number}</TableCell>
                {userIsSuperAdmin && (
                  <TableCell>
                    {employees.find((e) => e.id === claim.employee_id)?.full_name ?? '—'}
                  </TableCell>
                )}
                <TableCell>{claim.description}</TableCell>
                <TableCell>{formatDate(claim.expense_date)}</TableCell>
                <TableCell align="right">{formatMoney(claim.amount)}</TableCell>
                <TableCell align="right">{formatMoney(claim.paid_amount)}</TableCell>
                <TableCell align="right">{formatMoney(claim.remaining_amount)}</TableCell>
                <TableCell>
                  <Chip size="small" label={claim.status} color={statusColor(claim.status)} />
                </TableCell>
                <TableCell align="center">
                  {claim.proof_attachment_id != null && (
                    <Tooltip title="Download attachment">
                      <button
                        className="p-1 rounded-lg hover:bg-slate-100 transition-colors"
                        onClick={() => downloadAttachment(claim.proof_attachment_id!)}
                      >
                        <Download className="w-4 h-4 text-slate-600" />
                      </button>
                    </Tooltip>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={colSpan} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!claims.length && !loading && (
              <TableRow>
                <td colSpan={colSpan} className="px-4 py-8 text-center">
                  <Typography color="secondary">No expense claims found</Typography>
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
