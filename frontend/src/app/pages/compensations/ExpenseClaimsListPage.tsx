import { Download } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { api } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'
import { isSuperAdmin } from '../../utils/permissions'
import { Button } from '../../components/ui/Button'
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
  employee_name: string
  budget_number: string | null
  amount: number
  description: string
  expense_date: string
  status: string
  paid_amount: number
  remaining_amount: number
  proof_attachment_id: number | null
  funding_source: 'personal_funds' | 'budget'
}

interface UserRow {
  id: number
  full_name: string
}

interface ClaimTotalsResponse {
  employee_id: number
  total_submitted: number | string
  count_submitted: number
  total_pending_approval: number | string
  count_pending_approval: number
  total_approved: number | string
  total_paid: number | string
  balance: number | string
  total_rejected: number | string
  count_rejected: number
}

const statusOptions = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'needs_edit', label: 'Needs Edit' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'partially_paid', label: 'Partially Paid' },
  { value: 'paid', label: 'Paid' },
]

const fundingSourceOptions = [
  { value: 'all', label: 'All funding' },
  { value: 'personal_funds', label: 'Personal funds' },
  { value: 'budget', label: 'Budget advance' },
]

const statusColor = (status: string) => {
  if (status === 'approved' || status === 'paid') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'pending_approval' || status === 'partially_paid' || status === 'needs_edit') return 'warning'
  return 'info'
}

export const ExpenseClaimsListPage = () => {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const userIsSuperAdmin = isSuperAdmin(user)
  const canCreateClaim = user?.role !== 'Accountant'
  const showMyTotals = user?.role !== 'Accountant'

  const initialPage = Math.max((Number(searchParams.get('page')) || 1) - 1, 0)
  const initialLimit = Number(searchParams.get('limit')) || 50
  const initialStatus = searchParams.get('status') || 'all'
  const initialEmployee = searchParams.get('employee_id')
  const initialDateFrom = searchParams.get('date_from') || ''
  const initialDateTo = searchParams.get('date_to') || ''
  const initialFundingSource = searchParams.get('funding_source') || 'all'

  const [page, setPage] = useState(initialPage)
  const [limit, setLimit] = useState(initialLimit)
  const [statusFilter, setStatusFilter] = useState<string>(initialStatus)
  const [employeeFilter, setEmployeeFilter] = useState<number | ''>(
    initialEmployee ? Number(initialEmployee) : ''
  )
  const [dateFrom, setDateFrom] = useState(initialDateFrom)
  const [dateTo, setDateTo] = useState(initialDateTo)
  const [fundingSourceFilter, setFundingSourceFilter] = useState<string>(initialFundingSource)

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('page', String(page + 1))
    params.set('limit', String(limit))
    if (statusFilter !== 'all') params.set('status', statusFilter)
    if (userIsSuperAdmin && employeeFilter) params.set('employee_id', String(employeeFilter))
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    if (fundingSourceFilter !== 'all') params.set('funding_source', fundingSourceFilter)
    setSearchParams(params, { replace: true })
  }, [page, limit, statusFilter, employeeFilter, dateFrom, dateTo, fundingSourceFilter, userIsSuperAdmin, setSearchParams])

  const claimsUrl = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    // Only USER role is restricted to own claims; Admin and Accountant see all
    if (user?.role === 'User' && user?.id) params.employee_id = user.id
    else if (userIsSuperAdmin && employeeFilter) params.employee_id = Number(employeeFilter)
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    if (fundingSourceFilter !== 'all') params.funding_source = fundingSourceFilter

    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/compensations/claims?${sp.toString()}`
  }, [page, limit, statusFilter, employeeFilter, dateFrom, dateTo, fundingSourceFilter, userIsSuperAdmin, user])

  const { data: claimsData, loading, error } = useApi<PaginatedResponse<ClaimRow>>(claimsUrl)
  const { data: employeesData } = useApi<{ items: UserRow[] }>(
    userIsSuperAdmin ? '/users' : null,
    userIsSuperAdmin ? { params: { limit: USERS_LIST_LIMIT } } : undefined,
    [userIsSuperAdmin]
  )
  const { data: myTotals } = useApi<ClaimTotalsResponse>(
    user?.id && showMyTotals ? `/compensations/claims/employees/${user.id}/totals` : null
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

  const colSpan = 10

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <Typography variant="h4">Employee Expenses Claims</Typography>
        {canCreateClaim && (
          <Button onClick={() => navigate('/compensations/claims/new')} className="w-full sm:w-auto">
            New claim
          </Button>
        )}
      </div>

      {showMyTotals && myTotals && (
        <div className="mb-6">
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="secondary" className="mb-2">
                My Totals
              </Typography>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Pending Approval
                  </Typography>
                  <Typography variant="h6" className="mt-1">
                    {formatMoney(myTotals.total_pending_approval)} ({myTotals.count_pending_approval})
                  </Typography>
                </div>
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Owed (Approved Unpaid)
                  </Typography>
                  <Typography variant="h6" className={Number(myTotals.balance) > 0 ? 'text-error mt-1' : 'mt-1'}>
                    {formatMoney(myTotals.balance)}
                  </Typography>
                </div>
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Total Claimed
                  </Typography>
                  <Typography variant="h6" className="mt-1">
                    {formatMoney(myTotals.total_submitted)} ({myTotals.count_submitted})
                  </Typography>
                </div>
                <div>
                  <Typography variant="subtitle2" color="secondary">
                    Total Paid
                  </Typography>
                  <Typography variant="h6" className="mt-1">{formatMoney(myTotals.total_paid)}</Typography>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-4 mb-4 flex-wrap">
        {userIsSuperAdmin && (
          <div className="w-full sm:min-w-[200px]">
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
        <div className="w-full sm:min-w-[180px]">
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
        <div className="w-full sm:min-w-[160px]">
          <Input
            label="Date from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div className="w-full sm:min-w-[160px]">
          <Input
            label="Date to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
        <div className="w-full sm:min-w-[180px]">
          <Select label="Funding" value={fundingSourceFilter} onChange={(e) => setFundingSourceFilter(e.target.value)}>
            {fundingSourceOptions.map((option) => (
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

      {/* Mobile: cards */}
      <div className="md:hidden space-y-3">
        {claims.map((claim) => (
          <Card key={claim.id} className="cursor-pointer" onClick={() => navigate(`/compensations/claims/${claim.id}`)}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Typography variant="subtitle1" className="truncate">
                    {claim.claim_number}
                  </Typography>
                  <Typography variant="body2" color="secondary" className="mt-0.5">
                    {claim.employee_name || '—'} · {formatDate(claim.expense_date)}
                  </Typography>
                  <Typography variant="caption" color="secondary" className="mt-1 block">
                    {claim.funding_source === 'budget' ? `Budget · ${claim.budget_number ?? 'unassigned'}` : 'Personal funds'}
                  </Typography>
                </div>
                <Chip size="small" label={claim.status} color={statusColor(claim.status)} />
              </div>

              <Typography variant="body2" className="mt-3">
                {claim.description}
              </Typography>

              <div className="mt-3 flex items-center justify-between gap-3">
                <div>
                  <Typography variant="caption" color="secondary">
                    Amount
                  </Typography>
                  <Typography className="font-semibold">{formatMoney(claim.amount)}</Typography>
                </div>
                {claim.proof_attachment_id != null && (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={(e) => {
                      e.stopPropagation()
                      downloadAttachment(claim.proof_attachment_id!)
                    }}
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {loading && (
          <div className="flex justify-center py-8">
            <Spinner size="medium" />
          </div>
        )}
        {!claims.length && !loading && (
          <Card>
            <CardContent className="p-6 text-center">
              <Typography color="secondary">No expense claims found</Typography>
            </CardContent>
          </Card>
        )}

        <div className="pt-2">
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

      {/* Desktop: table */}
      <div className="hidden md:block bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Claim Number</TableHeaderCell>
              <TableHeaderCell>Employee</TableHeaderCell>
              <TableHeaderCell>Description</TableHeaderCell>
              <TableHeaderCell>Funding</TableHeaderCell>
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
                <TableCell>{claim.employee_name || '—'}</TableCell>
                <TableCell>{claim.description}</TableCell>
                <TableCell>
                  {claim.funding_source === 'budget' ? `Budget · ${claim.budget_number ?? '—'}` : 'Personal'}
                </TableCell>
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
                        onClick={(e) => {
                          e.stopPropagation()
                          downloadAttachment(claim.proof_attachment_id!)
                        }}
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
