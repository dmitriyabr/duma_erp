import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import type { PaginatedResponse } from '../../types/api'
import type { BudgetSummary } from '../../types/budgets'
import { formatMoney } from '../../utils/format'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
  Textarea,
} from '../../components/ui'

interface PurposeRow {
  id: number
  name: string
}

const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'closing', label: 'Closing' },
  { value: 'closed', label: 'Closed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const statusColor = (status: string) => {
  if (status === 'active' || status === 'closed') return 'success'
  if (status === 'cancelled') return 'error'
  if (status === 'draft' || status === 'closing') return 'warning'
  return 'default'
}

const today = () => new Date().toISOString().slice(0, 10)

export const BudgetsPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.role === 'SuperAdmin' || user?.role === 'Admin'
  const ownOnly = user?.role === 'User'

  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState('all')
  const [purposeFilter, setPurposeFilter] = useState<number | ''>('')
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [formName, setFormName] = useState('')
  const [formPurposeId, setFormPurposeId] = useState<number | ''>('')
  const [formPeriodFrom, setFormPeriodFrom] = useState(today())
  const [formPeriodTo, setFormPeriodTo] = useState(today())
  const [formLimitAmount, setFormLimitAmount] = useState('')
  const [formNotes, setFormNotes] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const { data: purposes } = useApi<PurposeRow[]>(
    '/procurement/payment-purposes',
    { params: { include_inactive: true, purpose_type: 'expense' } },
    []
  )

  const budgetsUrl = useMemo(() => {
    if (ownOnly) return '/budgets/my/budgets'

    const params = new URLSearchParams()
    params.set('page', String(page + 1))
    params.set('limit', String(limit))
    if (statusFilter !== 'all') params.set('status', statusFilter)
    if (purposeFilter) params.set('purpose_id', String(purposeFilter))
    return `/budgets?${params.toString()}`
  }, [ownOnly, page, limit, statusFilter, purposeFilter])

  const { data: budgetsData, loading, error, refetch } = useApi<
    PaginatedResponse<BudgetSummary> | BudgetSummary[]
  >(budgetsUrl, undefined, [budgetsUrl])

  const budgets = useMemo(() => {
    if (!budgetsData) return []
    const rows = Array.isArray(budgetsData) ? budgetsData : budgetsData.items
    if (!ownOnly) return rows

    return rows.filter((budget) => {
      if (statusFilter !== 'all' && budget.status !== statusFilter) return false
      if (purposeFilter && budget.purpose_id !== purposeFilter) return false
      return true
    })
  }, [budgetsData, ownOnly, statusFilter, purposeFilter])

  const total = useMemo(() => {
    if (!budgetsData) return 0
    if (Array.isArray(budgetsData)) return budgets.length
    return budgetsData.total
  }, [budgetsData, budgets.length])

  const createBudgetMutation = useApiMutation<BudgetSummary>()

  const openCreateDialog = () => {
    setLocalError(null)
    setFormName('')
    setFormPurposeId('')
    const now = today()
    setFormPeriodFrom(now)
    setFormPeriodTo(now)
    setFormLimitAmount('')
    setFormNotes('')
    setCreateDialogOpen(true)
  }

  const handleCreateBudget = async () => {
    if (!formName.trim() || !formPurposeId || !formPeriodFrom || !formPeriodTo || !formLimitAmount) {
      setLocalError('Fill name, purpose, period, and limit.')
      return
    }

    const limitAmount = Number(formLimitAmount)
    if (!limitAmount || limitAmount <= 0) {
      setLocalError('Limit amount must be greater than 0.')
      return
    }

    setLocalError(null)
    const created = await createBudgetMutation.execute(() =>
      import('../../services/api').then(({ api }) =>
        api.post('/budgets', {
          name: formName.trim(),
          purpose_id: Number(formPurposeId),
          period_from: formPeriodFrom,
          period_to: formPeriodTo,
          limit_amount: limitAmount,
          notes: formNotes.trim() || null,
        })
      )
    )

    if (!created) return

    setSuccess(`Budget ${created.budget_number} created.`)
    setCreateDialogOpen(false)
    await refetch()
    navigate(`/compensations/budgets/${created.id}`)
  }

  const effectiveError = localError || error || createBudgetMutation.error

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <Typography variant="h4">Budgets</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {ownOnly ? 'Budgets with available balance assigned to you.' : 'Operational budgets and period control.'}
          </Typography>
        </div>
        {canManage ? (
          <Button onClick={openCreateDialog}>New budget</Button>
        ) : null}
      </div>

      {effectiveError ? (
        <Alert severity="error" className="mb-4">
          {effectiveError}
        </Alert>
      ) : null}
      {success ? (
        <Alert severity="success" className="mb-4">
          {success}
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
        <div className="min-w-[240px]">
          <Select
            value={purposeFilter}
            onChange={(e) => setPurposeFilter(e.target.value ? Number(e.target.value) : '')}
            label="Purpose"
          >
            <option value="">All purposes</option>
            {(purposes || []).map((purpose) => (
              <option key={purpose.id} value={purpose.id}>
                {purpose.name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="md:hidden space-y-3">
        {budgets.map((budget) => (
          <Card
            key={budget.id}
            className={!ownOnly ? 'cursor-pointer' : undefined}
            onClick={!ownOnly ? () => navigate(`/compensations/budgets/${budget.id}`) : undefined}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Typography variant="subtitle1">{budget.budget_number}</Typography>
                  <Typography variant="body2" color="secondary">
                    {budget.name}
                  </Typography>
                </div>
                <Chip size="small" label={budget.status} color={statusColor(budget.status)} />
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div>
                  <Typography variant="caption" color="secondary">Limit</Typography>
                  <Typography>{formatMoney(budget.limit_amount)}</Typography>
                </div>
                <div>
                  <Typography variant="caption" color="secondary">Available</Typography>
                  <Typography>{formatMoney(budget.available_unreserved_total)}</Typography>
                </div>
                <div>
                  <Typography variant="caption" color="secondary">On hands</Typography>
                  <Typography>{formatMoney(budget.open_on_hands_total)}</Typography>
                </div>
                <div>
                  <Typography variant="caption" color="secondary">Overdue</Typography>
                  <Typography>{budget.overdue_advances_count}</Typography>
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

        {!budgets.length && !loading ? (
          <Card>
            <CardContent className="p-6 text-center">
              <Typography color="secondary">No budgets found</Typography>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div className="hidden md:block bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Budget</TableHeaderCell>
              <TableHeaderCell>Purpose</TableHeaderCell>
              <TableHeaderCell>Period</TableHeaderCell>
              <TableHeaderCell align="right">Limit</TableHeaderCell>
              <TableHeaderCell align="right">Available to Issue</TableHeaderCell>
              <TableHeaderCell align="right">On Hands</TableHeaderCell>
              <TableHeaderCell align="right">Available for Claims</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {budgets.map((budget) => (
              <TableRow
                key={budget.id}
                className={!ownOnly ? 'cursor-pointer' : undefined}
                onClick={!ownOnly ? () => navigate(`/compensations/budgets/${budget.id}`) : undefined}
              >
                <TableCell>
                  <div>
                    <Typography variant="body2" className="font-medium">
                      {budget.budget_number}
                    </Typography>
                    <Typography variant="caption" color="secondary">
                      {budget.name}
                    </Typography>
                  </div>
                </TableCell>
                <TableCell>{budget.purpose_name ?? '—'}</TableCell>
                <TableCell>
                  {budget.period_from} - {budget.period_to}
                </TableCell>
                <TableCell align="right">{formatMoney(budget.limit_amount)}</TableCell>
                <TableCell align="right">{formatMoney(budget.available_to_issue)}</TableCell>
                <TableCell align="right">{formatMoney(budget.open_on_hands_total)}</TableCell>
                <TableCell align="right">{formatMoney(budget.available_unreserved_total)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Chip size="small" label={budget.status} color={statusColor(budget.status)} />
                    {budget.overdue_advances_count > 0 ? (
                      <Typography variant="caption" color="secondary">
                        overdue: {budget.overdue_advances_count}
                      </Typography>
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ))}

            {loading ? (
              <TableRow>
                <td colSpan={8} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            ) : null}

            {!budgets.length && !loading ? (
              <TableRow>
                <td colSpan={8} className="px-4 py-8 text-center">
                  <Typography color="secondary">No budgets found</Typography>
                </td>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
        {!ownOnly ? (
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
        ) : null}
      </div>

      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New budget</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input label="Name" value={formName} onChange={(e) => setFormName(e.target.value)} required />
            <Select
              label="Purpose"
              value={formPurposeId}
              onChange={(e) => setFormPurposeId(e.target.value ? Number(e.target.value) : '')}
              required
            >
              <option value="">Select purpose</option>
              {(purposes || []).map((purpose) => (
                <option key={purpose.id} value={purpose.id}>
                  {purpose.name}
                </option>
              ))}
            </Select>
            <Input
              label="Period from"
              type="date"
              value={formPeriodFrom}
              onChange={(e) => setFormPeriodFrom(e.target.value)}
              required
            />
            <Input
              label="Period to"
              type="date"
              value={formPeriodTo}
              onChange={(e) => setFormPeriodTo(e.target.value)}
              required
            />
            <Input
              label="Limit amount"
              type="number"
              value={formLimitAmount}
              onChange={(e) => setFormLimitAmount(e.target.value)}
              min={0}
              step={0.01}
              required
            />
            <Textarea label="Notes" value={formNotes} onChange={(e) => setFormNotes(e.target.value)} rows={3} />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateBudget} disabled={createBudgetMutation.loading}>
            {createBudgetMutation.loading ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
