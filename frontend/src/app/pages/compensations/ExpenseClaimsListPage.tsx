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
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'
import { isSuperAdmin } from '../../utils/permissions'

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
    if (!userIsSuperAdmin && user?.id) params.employee_id = user.id
    else if (userIsSuperAdmin && employeeFilter) params.employee_id = Number(employeeFilter)
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo

    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/compensations/claims?${sp.toString()}`
  }, [page, limit, statusFilter, employeeFilter, dateFrom, dateTo, userIsSuperAdmin, user?.id])

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

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Expense Claims
      </Typography>

      {!userIsSuperAdmin && myBalance ? (
        <Box sx={{ mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, boxShadow: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            My Balance
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Total Approved
              </Typography>
              <Typography variant="h6">{formatMoney(myBalance.total_approved)}</Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Total Paid
              </Typography>
              <Typography variant="h6">{formatMoney(myBalance.total_paid)}</Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Balance
              </Typography>
              <Typography variant="h6" color={myBalance.balance > 0 ? 'error' : 'inherit'}>
                {formatMoney(myBalance.balance)}
              </Typography>
            </Box>
          </Box>
        </Box>
      ) : null}

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        {userIsSuperAdmin ? (
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Employee</InputLabel>
            <Select
              value={employeeFilter}
              label="Employee"
              onChange={(event) => {
                const val = String(event.target.value)
                setEmployeeFilter(val === '' ? '' : Number(val))
              }}
            >
              <MenuItem value="">All employees</MenuItem>
              {employees.map((emp) => (
                <MenuItem key={emp.id} value={emp.id}>
                  {emp.full_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : null}
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            {statusOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label="Date from"
          type="date"
          value={dateFrom}
          onChange={(event) => setDateFrom(event.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          label="Date to"
          type="date"
          value={dateTo}
          onChange={(event) => setDateTo(event.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
        />
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Claim Number</TableCell>
            {userIsSuperAdmin ? <TableCell>Employee</TableCell> : null}
            <TableCell>Description</TableCell>
            <TableCell>Date</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell align="right">Paid</TableCell>
            <TableCell align="right">Remaining</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {claims.map((claim) => (
            <TableRow key={claim.id}>
              <TableCell>{claim.claim_number}</TableCell>
              {userIsSuperAdmin ? (
                <TableCell>
                  {employees.find((e) => e.id === claim.employee_id)?.full_name ?? '—'}
                </TableCell>
              ) : null}
              <TableCell>{claim.description}</TableCell>
              <TableCell>{formatDate(claim.expense_date)}</TableCell>
              <TableCell align="right">{formatMoney(claim.amount)}</TableCell>
              <TableCell align="right">{formatMoney(claim.paid_amount)}</TableCell>
              <TableCell align="right">{formatMoney(claim.remaining_amount)}</TableCell>
              <TableCell>
                <Chip size="small" label={claim.status} color={statusColor(claim.status)} />
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => navigate(`/compensations/claims/${claim.id}`)}>
                  View
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {loading ? (
            <TableRow>
              <TableCell colSpan={userIsSuperAdmin ? 9 : 8} align="center">
                Loading…
              </TableCell>
            </TableRow>
          ) : null}
          {!claims.length && !loading ? (
            <TableRow>
              <TableCell colSpan={userIsSuperAdmin ? 9 : 8} align="center">
                No expense claims found
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
