import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import type {
  BudgetAdvanceListResponse,
  BudgetAdvanceReturn,
  BudgetAdvanceSummary,
  BudgetAdvanceTransfer,
  BudgetClosureStatus,
  BudgetListResponse,
  BudgetSummary,
  BudgetTransferListResponse,
} from '../../types/budgets'
import { formatDate, formatMoney } from '../../utils/format'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
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
  TableRow,
  Textarea,
  Typography,
} from '../../components/ui'

interface UserRow {
  id: number
  full_name: string
}

interface PurposeRow {
  id: number
  name: string
}

interface DirectPaymentRow {
  id: number
  payment_number: string
  payment_date: string
  amount: number
  payee_name: string | null
  payment_method: string
  status: string
}

const statusColor = (status: string) => {
  if (status === 'active' || status === 'issued' || status === 'settled' || status === 'closed' || status === 'posted') return 'success'
  if (status === 'draft' || status === 'closing' || status === 'overdue') return 'warning'
  if (status === 'cancelled') return 'error'
  return 'default'
}

const today = () => new Date().toISOString().slice(0, 10)

export const BudgetDetailPage = () => {
  const navigate = useNavigate()
  const { budgetId } = useParams()
  const { user } = useAuth()
  const canManage = user?.role === 'SuperAdmin' || user?.role === 'Admin'
  const canEditBudget = user?.role === 'SuperAdmin'
  const resolvedBudgetId = budgetId ? Number(budgetId) : null

  const { data: budget, loading, error, refetch: refetchBudget } = useApi<BudgetSummary>(
    resolvedBudgetId ? `/budgets/${resolvedBudgetId}` : null
  )
  const { data: closure, refetch: refetchClosure } = useApi<BudgetClosureStatus>(
    resolvedBudgetId ? `/budgets/${resolvedBudgetId}/closure` : null
  )
  const { data: advancesData, refetch: refetchAdvances } = useApi<BudgetAdvanceListResponse>(
    resolvedBudgetId ? `/budgets/advances?budget_id=${resolvedBudgetId}&page=1&limit=100` : null
  )
  const { data: transfersData, refetch: refetchTransfers } = useApi<BudgetTransferListResponse>(
    resolvedBudgetId ? `/budgets/transfers?budget_id=${resolvedBudgetId}&page=1&limit=100` : null
  )
  const { data: directPaymentsData, refetch: refetchDirectPayments } = useApi<PaginatedResponse<DirectPaymentRow>>(
    resolvedBudgetId ? `/procurement/payments?budget_id=${resolvedBudgetId}&company_paid=true&page=1&limit=100` : null
  )
  const { data: employeesData } = useApi<{ items: UserRow[] }>(
    canManage ? '/users' : null,
    canManage ? { params: { page: 1, limit: 500, is_active: true } } : undefined,
    [canManage]
  )
  const { data: activeBudgetsData } = useApi<BudgetListResponse>(
    canManage ? '/budgets?page=1&limit=100&status=active' : null,
    undefined,
    [canManage]
  )
  const { data: purposesData } = useApi<PurposeRow[]>(
    canEditBudget ? '/procurement/payment-purposes' : null,
    canEditBudget ? { params: { include_inactive: true, purpose_type: 'expense' } } : undefined,
    [canEditBudget]
  )

  const advances = advancesData?.items || []
  const transfers = transfersData?.items || []
  const directPayments = directPaymentsData?.items || []
  const employees = employeesData?.items || []
  const transferBudgetOptions = (activeBudgetsData?.items || []).filter((row) => row.id !== resolvedBudgetId)
  const purposes = purposesData || []

  const [success, setSuccess] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const [editBudgetOpen, setEditBudgetOpen] = useState(false)
  const [editName, setEditName] = useState('')
  const [editPurposeId, setEditPurposeId] = useState<number | ''>('')
  const [editPeriodFrom, setEditPeriodFrom] = useState('')
  const [editPeriodTo, setEditPeriodTo] = useState('')
  const [editLimitAmount, setEditLimitAmount] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const [createAdvanceOpen, setCreateAdvanceOpen] = useState(false)
  const [createEmployeeId, setCreateEmployeeId] = useState<number | ''>('')
  const [createIssueDate, setCreateIssueDate] = useState(today())
  const [createAmount, setCreateAmount] = useState('')
  const [createPaymentMethod, setCreatePaymentMethod] = useState('bank')
  const [createReferenceNumber, setCreateReferenceNumber] = useState('')
  const [createProofText, setCreateProofText] = useState('')
  const [createNotes, setCreateNotes] = useState('')
  const [createSettlementDueDate, setCreateSettlementDueDate] = useState('')
  const [createIssueNow, setCreateIssueNow] = useState(true)

  const [issueAdvanceTarget, setIssueAdvanceTarget] = useState<BudgetAdvanceSummary | null>(null)
  const [issueReferenceNumber, setIssueReferenceNumber] = useState('')
  const [issueProofText, setIssueProofText] = useState('')
  const [issuePaymentMethod, setIssuePaymentMethod] = useState('')
  const [issueSettlementDueDate, setIssueSettlementDueDate] = useState('')

  const [returnAdvanceTarget, setReturnAdvanceTarget] = useState<BudgetAdvanceSummary | null>(null)
  const [returnDate, setReturnDate] = useState(today())
  const [returnAmount, setReturnAmount] = useState('')
  const [returnMethod, setReturnMethod] = useState('bank')
  const [returnReferenceNumber, setReturnReferenceNumber] = useState('')
  const [returnProofText, setReturnProofText] = useState('')
  const [returnNotes, setReturnNotes] = useState('')

  const [transferAdvanceTarget, setTransferAdvanceTarget] = useState<BudgetAdvanceSummary | null>(null)
  const [transferBudgetId, setTransferBudgetId] = useState<number | ''>('')
  const [transferEmployeeId, setTransferEmployeeId] = useState<number | ''>('')
  const [transferDate, setTransferDate] = useState(today())
  const [transferAmount, setTransferAmount] = useState('')
  const [transferType, setTransferType] = useState<'rollover' | 'reassignment' | 'reallocation'>('rollover')
  const [transferReason, setTransferReason] = useState('')
  const [transferSettlementDueDate, setTransferSettlementDueDate] = useState('')

  const [returnsViewerAdvance, setReturnsViewerAdvance] = useState<BudgetAdvanceSummary | null>(null)
  const { data: advanceReturnsData, loading: returnsLoading } = useApi<BudgetAdvanceReturn[]>(
    returnsViewerAdvance ? `/budgets/advances/${returnsViewerAdvance.id}/returns` : null,
    undefined,
    [returnsViewerAdvance?.id]
  )

  const budgetActionMutation = useApiMutation<BudgetSummary>()
  const updateBudgetMutation = useApiMutation<BudgetSummary>()
  const advanceActionMutation = useApiMutation<BudgetAdvanceSummary>()
  const createAdvanceMutation = useApiMutation<BudgetAdvanceSummary>()
  const returnMutation = useApiMutation<BudgetAdvanceReturn>()
  const transferMutation = useApiMutation<BudgetAdvanceTransfer>()

  const effectiveError =
    localError ||
    error ||
    budgetActionMutation.error ||
    updateBudgetMutation.error ||
    advanceActionMutation.error ||
    createAdvanceMutation.error ||
    returnMutation.error ||
    transferMutation.error

  const reloadAll = async () => {
    await Promise.all([refetchBudget(), refetchClosure(), refetchAdvances(), refetchTransfers(), refetchDirectPayments()])
  }

  const openEditBudgetDialog = () => {
    if (!budget) return
    setLocalError(null)
    setEditName(budget.name)
    setEditPurposeId(budget.purpose_id)
    setEditPeriodFrom(budget.period_from)
    setEditPeriodTo(budget.period_to)
    setEditLimitAmount(String(budget.limit_amount))
    setEditNotes(budget.notes ?? '')
    setEditBudgetOpen(true)
  }

  const handleUpdateBudget = async () => {
    if (!budget) return
    if (!editName.trim()) {
      setLocalError('Budget name is required.')
      return
    }

    const payload: Record<string, string | number | null> = {
      name: editName.trim(),
      notes: editNotes.trim() || null,
    }

    if (budget.status === 'draft') {
      if (!editPurposeId || !editPeriodFrom || !editPeriodTo || !editLimitAmount) {
        setLocalError('Fill purpose, period, and limit.')
        return
      }

      const limitAmount = Number(editLimitAmount)
      if (!limitAmount || limitAmount <= 0) {
        setLocalError('Limit amount must be greater than 0.')
        return
      }

      payload.purpose_id = Number(editPurposeId)
      payload.period_from = editPeriodFrom
      payload.period_to = editPeriodTo
      payload.limit_amount = limitAmount
    }

    setLocalError(null)
    const result = await updateBudgetMutation.execute(() => api.patch(`/budgets/${budget.id}`, payload))
    if (!result) return

    setSuccess(`Budget ${result.budget_number} updated.`)
    setEditBudgetOpen(false)
    await reloadAll()
  }

  const openCreateAdvanceDialog = () => {
    setLocalError(null)
    setCreateEmployeeId('')
    setCreateIssueDate(today())
    setCreateAmount('')
    setCreatePaymentMethod('bank')
    setCreateReferenceNumber('')
    setCreateProofText('')
    setCreateNotes('')
    setCreateSettlementDueDate(budget?.period_to ?? '')
    setCreateIssueNow(true)
    setCreateAdvanceOpen(true)
  }

  const handleBudgetAction = async (action: 'activate' | 'close' | 'cancel') => {
    if (!resolvedBudgetId) return
    setLocalError(null)
    const result = await budgetActionMutation.execute(() => api.post(`/budgets/${resolvedBudgetId}/${action}`))
    if (!result) return
    setSuccess(`Budget ${result.budget_number} ${action}d.`)
    await reloadAll()
  }

  const handleCreateAdvance = async () => {
    if (!resolvedBudgetId || !createEmployeeId || !createIssueDate || !createAmount) {
      setLocalError('Fill employee, issue date, and amount.')
      return
    }
    const amountValue = Number(createAmount)
    if (!amountValue || amountValue <= 0) {
      setLocalError('Advance amount must be greater than 0.')
      return
    }

    setLocalError(null)
    const created = await createAdvanceMutation.execute(() =>
      api.post('/budgets/advances', {
        budget_id: resolvedBudgetId,
        employee_id: Number(createEmployeeId),
        issue_date: createIssueDate,
        amount_issued: amountValue,
        payment_method: createPaymentMethod,
        reference_number: createReferenceNumber.trim() || null,
        proof_text: createProofText.trim() || null,
        notes: createNotes.trim() || null,
        settlement_due_date: createSettlementDueDate || null,
        issue_now: createIssueNow,
      })
    )
    if (!created) return

    setSuccess(`Advance ${created.advance_number} created.`)
    setCreateAdvanceOpen(false)
    await reloadAll()
  }

  const openIssueDialog = (advance: BudgetAdvanceSummary) => {
    setLocalError(null)
    setIssueAdvanceTarget(advance)
    setIssueReferenceNumber(advance.reference_number ?? '')
    setIssueProofText(advance.proof_text ?? '')
    setIssuePaymentMethod(advance.payment_method ?? '')
    setIssueSettlementDueDate(advance.settlement_due_date ?? '')
  }

  const handleIssueAdvance = async () => {
    if (!issueAdvanceTarget) return
    setLocalError(null)
    const result = await advanceActionMutation.execute(() =>
      api.post(`/budgets/advances/${issueAdvanceTarget.id}/issue`, {
        payment_method: issuePaymentMethod || null,
        reference_number: issueReferenceNumber.trim() || null,
        proof_text: issueProofText.trim() || null,
        settlement_due_date: issueSettlementDueDate || null,
      })
    )
    if (!result) return

    setSuccess(`Advance ${result.advance_number} issued.`)
    setIssueAdvanceTarget(null)
    await reloadAll()
  }

  const handleCancelAdvance = async (advance: BudgetAdvanceSummary) => {
    setLocalError(null)
    const result = await advanceActionMutation.execute(() => api.post(`/budgets/advances/${advance.id}/cancel`))
    if (!result) return
    setSuccess(`Advance ${result.advance_number} cancelled.`)
    await reloadAll()
  }

  const handleCloseAdvance = async (advance: BudgetAdvanceSummary) => {
    setLocalError(null)
    const result = await advanceActionMutation.execute(() => api.post(`/budgets/advances/${advance.id}/close`))
    if (!result) return
    setSuccess(`Advance ${result.advance_number} closed.`)
    await reloadAll()
  }

  const openReturnDialog = (advance: BudgetAdvanceSummary) => {
    setLocalError(null)
    setReturnAdvanceTarget(advance)
    setReturnDate(today())
    setReturnAmount(String(advance.available_unreserved_amount))
    setReturnMethod('bank')
    setReturnReferenceNumber('')
    setReturnProofText('')
    setReturnNotes('')
  }

  const handleCreateReturn = async () => {
    if (!returnAdvanceTarget || !returnDate || !returnAmount) {
      setLocalError('Fill return date and amount.')
      return
    }
    const amountValue = Number(returnAmount)
    if (!amountValue || amountValue <= 0) {
      setLocalError('Return amount must be greater than 0.')
      return
    }

    setLocalError(null)
    const result = await returnMutation.execute(() =>
      api.post(`/budgets/advances/${returnAdvanceTarget.id}/returns`, {
        return_date: returnDate,
        amount: amountValue,
        return_method: returnMethod,
        reference_number: returnReferenceNumber.trim() || null,
        proof_text: returnProofText.trim() || null,
        notes: returnNotes.trim() || null,
      })
    )
    if (!result) return

    setSuccess(`Return ${result.return_number} recorded.`)
    setReturnAdvanceTarget(null)
    await reloadAll()
  }

  const openTransferDialog = (advance: BudgetAdvanceSummary) => {
    setLocalError(null)
    setTransferAdvanceTarget(advance)
    setTransferBudgetId('')
    setTransferEmployeeId('')
    setTransferDate(today())
    setTransferAmount(String(advance.available_unreserved_amount))
    setTransferType('rollover')
    setTransferReason('')
    setTransferSettlementDueDate('')
  }

  const handleTransfer = async () => {
    if (!transferAdvanceTarget || !transferBudgetId || !transferDate || !transferAmount || !transferReason.trim()) {
      setLocalError('Fill target budget, transfer date, amount, and reason.')
      return
    }
    const amountValue = Number(transferAmount)
    if (!amountValue || amountValue <= 0) {
      setLocalError('Transfer amount must be greater than 0.')
      return
    }

    setLocalError(null)
    const result = await transferMutation.execute(() =>
      api.post(`/budgets/advances/${transferAdvanceTarget.id}/transfer`, {
        to_budget_id: Number(transferBudgetId),
        to_employee_id: transferEmployeeId ? Number(transferEmployeeId) : null,
        transfer_date: transferDate,
        amount: amountValue,
        transfer_type: transferType,
        reason: transferReason.trim(),
        settlement_due_date: transferSettlementDueDate || null,
      })
    )
    if (!result) return

    setSuccess(`Transfer ${result.transfer_number} created.`)
    setTransferAdvanceTarget(null)
    await reloadAll()
  }

  const summaryCards = useMemo(
    () =>
      budget
        ? [
            { label: 'Limit', value: formatMoney(budget.limit_amount) },
            { label: 'Available to issue', value: formatMoney(budget.available_to_issue) },
            { label: 'Direct company paid', value: formatMoney(budget.direct_company_paid_total) },
            { label: 'On hands', value: formatMoney(budget.open_on_hands_total) },
            { label: 'Available for claims', value: formatMoney(budget.available_unreserved_total) },
            { label: 'Settled', value: formatMoney(budget.settled_total) },
            { label: 'Overdue advances', value: String(budget.overdue_advances_count) },
          ]
        : [],
    [budget]
  )

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!budget || !resolvedBudgetId) {
    return <Alert severity="error">{effectiveError || 'Budget not found.'}</Alert>
  }

  return (
    <div>
      <div className="mb-4">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Back
        </Button>
      </div>

      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <Typography variant="h4">{budget.budget_number}</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {budget.name} · {budget.purpose_name ?? '—'} · {budget.period_from} - {budget.period_to}
          </Typography>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Chip label={budget.status} color={statusColor(budget.status)} />
          {canEditBudget ? (
            <Button variant="outlined" onClick={openEditBudgetDialog} disabled={updateBudgetMutation.loading}>
              Edit budget
            </Button>
          ) : null}
          {canManage && budget.status === 'draft' ? (
            <>
              <Button variant="contained" onClick={() => handleBudgetAction('activate')} disabled={budgetActionMutation.loading}>
                Activate
              </Button>
              <Button variant="outlined" color="error" onClick={() => handleBudgetAction('cancel')} disabled={budgetActionMutation.loading}>
                Cancel
              </Button>
            </>
          ) : null}
          {canManage && budget.status === 'active' ? (
            <Button onClick={openCreateAdvanceDialog}>New advance</Button>
          ) : null}
          {canManage && ['active', 'closing'].includes(budget.status) ? (
            <Button variant="contained" onClick={() => navigate(`/procurement/payments/new?budget_id=${budget.id}`)}>
              Record direct payment
            </Button>
          ) : null}
          {canManage && ['active', 'closing'].includes(budget.status) ? (
            <Button
              variant="outlined"
              onClick={() => handleBudgetAction('close')}
              disabled={budgetActionMutation.loading || closure?.can_close === false}
            >
              Close budget
            </Button>
          ) : null}
        </div>
      </div>

      <Dialog open={editBudgetOpen} onClose={() => setEditBudgetOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit budget</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input label="Name" value={editName} onChange={(e) => setEditName(e.target.value)} />
            {budget.status === 'draft' ? (
              <>
                <Select
                  label="Purpose"
                  value={editPurposeId}
                  onChange={(e) => setEditPurposeId(e.target.value ? Number(e.target.value) : '')}
                >
                  <option value="">Select purpose</option>
                  {purposes.map((purpose) => (
                    <option key={purpose.id} value={purpose.id}>
                      {purpose.name}
                    </option>
                  ))}
                </Select>
                <Input label="Period from" type="date" value={editPeriodFrom} onChange={(e) => setEditPeriodFrom(e.target.value)} />
                <Input label="Period to" type="date" value={editPeriodTo} onChange={(e) => setEditPeriodTo(e.target.value)} />
                <Input
                  label="Limit amount"
                  type="number"
                  min={0}
                  step={0.01}
                  value={editLimitAmount}
                  onChange={(e) => setEditLimitAmount(e.target.value)}
                />
              </>
            ) : (
              <Alert severity="warning">
                Purpose, period, and limit can only be edited while the budget is draft.
              </Alert>
            )}
            <Textarea label="Notes" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} rows={3} />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditBudgetOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleUpdateBudget} disabled={updateBudgetMutation.loading}>
            {updateBudgetMutation.loading ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

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

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-7 gap-4 mb-6">
        {summaryCards.map((card) => (
          <Card key={card.label}>
            <CardContent>
              <Typography variant="subtitle2" color="secondary">
                {card.label}
              </Typography>
              <Typography variant="h6" className="mt-1">
                {card.value}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </div>

      {closure ? (
        <Card className="mb-6">
          <CardContent>
            <Typography variant="subtitle1">Period closing</Typography>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-3">
              <div>
                <Typography variant="caption" color="secondary">Open advances</Typography>
                <Typography>{closure.open_advances_count}</Typography>
              </div>
              <div>
                <Typography variant="caption" color="secondary">Overdue advances</Typography>
                <Typography>{closure.overdue_advances_count}</Typography>
              </div>
              <div>
                <Typography variant="caption" color="secondary">Unresolved claims</Typography>
                <Typography>{closure.unresolved_claims_count}</Typography>
              </div>
              <div>
                <Typography variant="caption" color="secondary">Transferable</Typography>
                <Typography>{formatMoney(closure.transferable_amount_total)}</Typography>
              </div>
            </div>
            {!closure.can_close && closure.blocking_reasons.length ? (
              <div className="mt-4">
                <Typography variant="caption" color="secondary">
                  Blocking reasons
                </Typography>
                <div className="mt-2 space-y-1">
                  {closure.blocking_reasons.map((reason) => (
                    <Typography key={reason} variant="body2">
                      {reason}
                    </Typography>
                  ))}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <div className="mb-6">
        <Typography variant="h6" className="mb-2">Direct company payments</Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-6">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Payment</TableHeaderCell>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Payee</TableHeaderCell>
                <TableHeaderCell>Method</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {directPayments.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell>{payment.payment_number}</TableCell>
                  <TableCell>{formatDate(payment.payment_date)}</TableCell>
                  <TableCell>{payment.payee_name ?? '—'}</TableCell>
                  <TableCell>{payment.payment_method}</TableCell>
                  <TableCell align="right">{formatMoney(payment.amount)}</TableCell>
                  <TableCell>
                    <Chip label={payment.status} color={statusColor(payment.status)} />
                  </TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => navigate(`/procurement/payments/${payment.id}`)}>
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!directPayments.length ? (
                <TableRow>
                  <td colSpan={7} className="px-4 py-6 text-center text-sm text-slate-500">
                    No direct company-paid budget payments recorded yet.
                  </td>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="mb-6">
        <Typography variant="h6" className="mb-2">Advances</Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Advance</TableHeaderCell>
                <TableHeaderCell>Employee</TableHeaderCell>
                <TableHeaderCell>Issue</TableHeaderCell>
                <TableHeaderCell>Due</TableHeaderCell>
                <TableHeaderCell align="right">Issued</TableHeaderCell>
                <TableHeaderCell align="right">Returned</TableHeaderCell>
                <TableHeaderCell align="right">Settled</TableHeaderCell>
                <TableHeaderCell align="right">Open</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {advances.map((advance) => {
                const canReturnOrTransfer =
                  ['issued', 'overdue'].includes(advance.status) &&
                  Number(advance.available_unreserved_amount) > 0
                const canCloseAdvance =
                  !['draft', 'closed', 'cancelled'].includes(advance.status) &&
                  Number(advance.open_balance) === 0 &&
                  Number(advance.reserved_amount) === 0

                return (
                  <TableRow key={advance.id}>
                    <TableCell>
                      <div>
                        <Typography variant="body2" className="font-medium">
                          {advance.advance_number}
                        </Typography>
                        <Typography variant="caption" color="secondary">
                          {advance.payment_method}
                        </Typography>
                      </div>
                    </TableCell>
                    <TableCell>{advance.employee_name}</TableCell>
                    <TableCell>{formatDate(advance.issue_date)}</TableCell>
                    <TableCell>{formatDate(advance.settlement_due_date)}</TableCell>
                    <TableCell align="right">{formatMoney(advance.amount_issued)}</TableCell>
                    <TableCell align="right">{formatMoney(advance.returned_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(advance.settled_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(advance.open_balance)}</TableCell>
                    <TableCell>
                      <Chip size="small" label={advance.status} color={statusColor(advance.status)} />
                    </TableCell>
                    <TableCell align="right">
                      <div className="flex justify-end gap-2 flex-wrap">
                        <Button size="small" variant="outlined" onClick={() => setReturnsViewerAdvance(advance)}>
                          Returns
                        </Button>
                        {canManage && advance.status === 'draft' ? (
                          <>
                            <Button size="small" onClick={() => openIssueDialog(advance)}>Issue</Button>
                            <Button size="small" variant="outlined" color="error" onClick={() => handleCancelAdvance(advance)}>
                              Cancel
                            </Button>
                          </>
                        ) : null}
                        {canManage && canReturnOrTransfer ? (
                          <>
                            <Button size="small" onClick={() => openReturnDialog(advance)}>Return</Button>
                            <Button size="small" variant="outlined" onClick={() => openTransferDialog(advance)}>
                              Transfer
                            </Button>
                          </>
                        ) : null}
                        {canManage && canCloseAdvance ? (
                          <Button size="small" variant="outlined" onClick={() => handleCloseAdvance(advance)}>
                            Close
                          </Button>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
              {!advances.length ? (
                <TableRow>
                  <td colSpan={10} className="px-4 py-8 text-center">
                    <Typography color="secondary">No advances yet</Typography>
                  </td>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </div>

      <div>
        <Typography variant="h6" className="mb-2">Transfers</Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Transfer</TableHeaderCell>
                <TableHeaderCell>From advance</TableHeaderCell>
                <TableHeaderCell>To budget</TableHeaderCell>
                <TableHeaderCell>Employee</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
                <TableHeaderCell>Type</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {transfers.map((transfer) => (
                <TableRow key={transfer.id}>
                  <TableCell>{formatDate(transfer.transfer_date)}</TableCell>
                  <TableCell>{transfer.transfer_number}</TableCell>
                  <TableCell>{transfer.from_advance_number}</TableCell>
                  <TableCell>{transfer.to_budget_number}</TableCell>
                  <TableCell>{transfer.to_employee_name ?? '—'}</TableCell>
                  <TableCell align="right">{formatMoney(transfer.amount)}</TableCell>
                  <TableCell>{transfer.transfer_type}</TableCell>
                </TableRow>
              ))}
              {!transfers.length ? (
                <TableRow>
                  <td colSpan={7} className="px-4 py-8 text-center">
                    <Typography color="secondary">No transfers yet</Typography>
                  </td>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </div>

      <Dialog open={createAdvanceOpen} onClose={() => setCreateAdvanceOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New advance</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Select
              label="Employee"
              value={createEmployeeId}
              onChange={(e) => setCreateEmployeeId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">Select employee</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </Select>
            <Input label="Issue date" type="date" value={createIssueDate} onChange={(e) => setCreateIssueDate(e.target.value)} />
            <Input label="Settlement due date" type="date" value={createSettlementDueDate} onChange={(e) => setCreateSettlementDueDate(e.target.value)} />
            <Input label="Amount" type="number" min={0} step={0.01} value={createAmount} onChange={(e) => setCreateAmount(e.target.value)} />
            <Select label="Payment method" value={createPaymentMethod} onChange={(e) => setCreatePaymentMethod(e.target.value)}>
              <option value="bank">Bank transfer</option>
              <option value="cash">Cash</option>
              <option value="mpesa">M-Pesa</option>
              <option value="other">Other</option>
            </Select>
            <Input label="Reference number" value={createReferenceNumber} onChange={(e) => setCreateReferenceNumber(e.target.value)} />
            <Textarea label="Proof / note" value={createProofText} onChange={(e) => setCreateProofText(e.target.value)} rows={3} />
            <Textarea label="Notes" value={createNotes} onChange={(e) => setCreateNotes(e.target.value)} rows={3} />
            <Checkbox checked={createIssueNow} onChange={(e) => setCreateIssueNow(e.target.checked)} label="Issue immediately" />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateAdvanceOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateAdvance} disabled={createAdvanceMutation.loading}>
            {createAdvanceMutation.loading ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={issueAdvanceTarget !== null} onClose={() => setIssueAdvanceTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Issue advance</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input label="Payment method" value={issuePaymentMethod} onChange={(e) => setIssuePaymentMethod(e.target.value)} />
            <Input label="Reference number" value={issueReferenceNumber} onChange={(e) => setIssueReferenceNumber(e.target.value)} />
            <Input label="Settlement due date" type="date" value={issueSettlementDueDate} onChange={(e) => setIssueSettlementDueDate(e.target.value)} />
            <Textarea label="Proof / note" value={issueProofText} onChange={(e) => setIssueProofText(e.target.value)} rows={3} />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIssueAdvanceTarget(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleIssueAdvance} disabled={advanceActionMutation.loading}>
            {advanceActionMutation.loading ? 'Issuing…' : 'Issue'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={returnAdvanceTarget !== null} onClose={() => setReturnAdvanceTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Record return</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input label="Return date" type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)} />
            <Input label="Amount" type="number" min={0} step={0.01} value={returnAmount} onChange={(e) => setReturnAmount(e.target.value)} />
            <Select label="Return method" value={returnMethod} onChange={(e) => setReturnMethod(e.target.value)}>
              <option value="bank">Bank transfer</option>
              <option value="cash">Cash</option>
              <option value="mpesa">M-Pesa</option>
              <option value="other">Other</option>
            </Select>
            <Input label="Reference number" value={returnReferenceNumber} onChange={(e) => setReturnReferenceNumber(e.target.value)} />
            <Textarea label="Proof / note" value={returnProofText} onChange={(e) => setReturnProofText(e.target.value)} rows={3} />
            <Textarea label="Notes" value={returnNotes} onChange={(e) => setReturnNotes(e.target.value)} rows={3} />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReturnAdvanceTarget(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateReturn} disabled={returnMutation.loading}>
            {returnMutation.loading ? 'Saving…' : 'Save return'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={transferAdvanceTarget !== null} onClose={() => setTransferAdvanceTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Transfer balance</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Select label="Target budget" value={transferBudgetId} onChange={(e) => setTransferBudgetId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">Select target budget</option>
              {transferBudgetOptions.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.budget_number} · {row.name}
                </option>
              ))}
            </Select>
            <Select label="Target employee (optional)" value={transferEmployeeId} onChange={(e) => setTransferEmployeeId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">Keep same employee</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </Select>
            <Input label="Transfer date" type="date" value={transferDate} onChange={(e) => setTransferDate(e.target.value)} />
            <Input label="Settlement due date" type="date" value={transferSettlementDueDate} onChange={(e) => setTransferSettlementDueDate(e.target.value)} />
            <Input label="Amount" type="number" min={0} step={0.01} value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} />
            <Select label="Transfer type" value={transferType} onChange={(e) => setTransferType(e.target.value as typeof transferType)}>
              <option value="rollover">Rollover</option>
              <option value="reassignment">Reassignment</option>
              <option value="reallocation">Reallocation</option>
            </Select>
            <Textarea label="Reason" value={transferReason} onChange={(e) => setTransferReason(e.target.value)} rows={3} />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTransferAdvanceTarget(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleTransfer} disabled={transferMutation.loading}>
            {transferMutation.loading ? 'Transferring…' : 'Transfer'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={returnsViewerAdvance !== null} onClose={() => setReturnsViewerAdvance(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Advance returns</DialogTitle>
        <DialogContent>
          {returnsLoading ? (
            <div className="flex items-center gap-2 py-6">
              <Spinner size="small" />
              <Typography>Loading…</Typography>
            </div>
          ) : (
            <div className="space-y-3 mt-2">
              {(advanceReturnsData || []).map((row) => (
                <div key={row.id} className="rounded-lg border border-slate-200 p-3">
                  <Typography variant="body2" className="font-medium">
                    {row.return_number} · {formatDate(row.return_date)} · {formatMoney(row.amount)}
                  </Typography>
                  <Typography variant="caption" color="secondary">
                    {row.return_method}
                    {row.reference_number ? ` · ${row.reference_number}` : ''}
                  </Typography>
                  {row.proof_text ? (
                    <Typography variant="body2" className="mt-2">
                      {row.proof_text}
                    </Typography>
                  ) : null}
                </div>
              ))}
              {!advanceReturnsData?.length ? (
                <Typography color="secondary">No returns recorded.</Typography>
              ) : null}
            </div>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReturnsViewerAdvance(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
