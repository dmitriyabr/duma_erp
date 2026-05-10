import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { INVOICE_LIST_LIMIT } from '../../constants/pagination'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { formatDate, formatMoney } from '../../utils/format'
import { InvoicesTab } from './components/InvoicesTab'
import { ItemsToIssueTab } from './components/ItemsToIssueTab'
import { OverviewTab } from './components/OverviewTab'
import { PaymentsTab } from './components/PaymentsTab'
import { StatementTab } from './components/StatementTab'
import { StudentHeader } from './components/StudentHeader'
import type {
  InvoiceSummary,
  PaginatedResponse,
  ReservationResponse,
  StudentBalance,
  StudentResponse,
} from './types'
import { parseNumber } from './types'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { FileDropzone } from '../../components/ui/FileDropzone'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components/ui/Table'
import { Tabs, TabsList, Tab, TabPanel } from '../../components/ui/Tabs'
import { Textarea } from '../../components/ui/Textarea'
import { Typography } from '../../components/ui/Typography'

interface RefundAllocationOption {
  allocation_id: number
  invoice_id: number
  invoice_number: string
  student_id: number
  student_name?: string | null
  invoice_type: string
  invoice_status: string
  due_date?: string | null
  current_allocation_amount: number
  invoice_amount_due: number
}

interface WithdrawalInvoiceImpact {
  invoice_id: number
  invoice_number: string
  action: string
  amount: number
  amount_due_before: number
  amount_due_after: number
  status_before: string
  status_after: string
}

interface WithdrawalSettlementPreview {
  student_id: number
  billing_account_id: number
  total_paid: number
  current_outstanding_debt: number
  retained_amount: number
  deduction_amount: number
  write_off_amount: number
  cancelled_amount: number
  refund_amount: number
  remaining_collectible_debt_after: number
  invoice_impacts: WithdrawalInvoiceImpact[]
  reservation_impacts: Array<{
    reservation_id: number
    invoice_id: number
    invoice_number?: string | null
    action: string
    status_before: string
    status_after: string
    quantity_required: number
    quantity_issued: number
    quantity_remaining_before: number
    quantity_remaining_after: number
  }>
  warnings: string[]
}

interface WithdrawalSettlementResponse {
  id: number
  settlement_number: string
  settlement_date: string
  status: string
  refund_amount: number
  write_off_amount: number
  cancelled_amount: number
  remaining_collectible_debt: number
  refund_number?: string | null
}

type SettlementInvoiceAction = 'none' | 'cancel_unpaid' | 'write_off' | 'keep_charged'
type SettlementReservationAction = 'none' | 'cancel' | 'close'

export const StudentDetailPage = () => {
  const { studentId } = useParams()
  // const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const resolvedId = Number(studentId)

  const { data: student, error: studentError, refetch: refetchStudent } = useApi<StudentResponse>(
    resolvedId ? `/students/${resolvedId}` : null
  )
  const { data: balance, refetch: refetchBalance } = useApi<StudentBalance>(
    resolvedId ? `/payments/students/${resolvedId}/balance` : null
  )
  const { grades, transportZones } = useReferencedData()

  const invoicesApi = useApi<PaginatedResponse<InvoiceSummary>>(
    resolvedId ? '/invoices' : null,
    {
      params: { student_id: resolvedId, limit: INVOICE_LIST_LIMIT, page: 1 },
    },
    [resolvedId]
  )
  const settlementHistoryApi = useApi<WithdrawalSettlementResponse[]>(
    resolvedId ? `/students/${resolvedId}/withdrawal-settlements` : null,
    undefined,
    [resolvedId]
  )
  const refundAllocationOptionsApi = useApi<RefundAllocationOption[]>(
    student?.billing_account_id ? `/billing-accounts/${student.billing_account_id}/refunds/allocation-options` : null,
    undefined,
    [student?.billing_account_id]
  )
  const reservationsApi = useApi<PaginatedResponse<ReservationResponse>>(
    resolvedId ? `/reservations?student_id=${resolvedId}&limit=100&page=1` : null,
    undefined,
    [resolvedId]
  )
  const previewSettlementMutation = useApiMutation<WithdrawalSettlementPreview>()
  const createSettlementMutation = useApiMutation<WithdrawalSettlementResponse>()

  const debt = balance != null ? parseNumber(balance.outstanding_debt) : 0

  const [error, setError] = useState<string | null>(null)
  const tabParam = searchParams.get('tab') ?? 'overview'
  const tab = ['overview', 'invoices', 'payments', 'items', 'statement'].includes(tabParam)
    ? tabParam
    : 'overview'
  const [allocationResult, setAllocationResult] = useState<string | null>(null)
  const [withdrawDialogOpen, setWithdrawDialogOpen] = useState(false)
  const [withdrawPreview, setWithdrawPreview] = useState<WithdrawalSettlementPreview | null>(null)
  const [withdrawErrors, setWithdrawErrors] = useState<Record<string, string>>({})
  const [uploadingWithdrawRefundProof, setUploadingWithdrawRefundProof] = useState(false)
  const [settlementForm, setSettlementForm] = useState({
    settlement_date: new Date().toISOString().slice(0, 10),
    reason: '',
    retained_amount: '',
    deduction_amount: '',
    notes: '',
    refund_amount: '',
    refund_method: 'bank_transfer',
    refund_reference_number: '',
    refund_proof_text: '',
    refund_proof_attachment_id: null as number | null,
    refund_proof_file_name: null as string | null,
    refund_reason: 'Withdrawal settlement refund',
  })
  const [invoiceActions, setInvoiceActions] = useState<
    Record<number, { action: SettlementInvoiceAction; amount: string; notes: string }>
  >({})
  const [reservationActions, setReservationActions] = useState<
    Record<number, { action: SettlementReservationAction; notes: string }>
  >({})
  const [refundReversals, setRefundReversals] = useState<Record<number, string>>({})

  const loadStudent = useCallback(async () => {
    refetchStudent()
  }, [refetchStudent])

  const loadBalance = useCallback(async () => {
    refetchBalance()
  }, [refetchBalance])

  useEffect(() => {
    if (studentError) {
      setError('Failed to load student.')
    }
  }, [studentError])

  const handleBalanceChange = useCallback(() => {
    loadBalance()
    invoicesApi.refetch()
  }, [loadBalance, invoicesApi.refetch])

  useEffect(() => {
    loadStudent()
    loadBalance()
  }, [resolvedId, loadStudent, loadBalance])

  const handleTabChange = (value: string) => {
    if (value === 'overview') {
      setSearchParams({})
    } else {
      setSearchParams({ tab: value })
    }
  }

  const handleError = (message: string) => {
    setError(message)
  }

  const handleDebtChange = () => {
    handleBalanceChange()
  }

  const handleAllocationResult = (message: string) => {
    setAllocationResult(message)
    setTimeout(() => setAllocationResult(null), 5000)
  }

  const openWithdrawDialog = () => {
    setWithdrawDialogOpen(true)
    setWithdrawPreview(null)
    setWithdrawErrors({})
    setInvoiceActions({})
    setReservationActions(
      (reservationsApi.data?.items ?? []).reduce<Record<number, { action: SettlementReservationAction; notes: string }>>(
        (acc, reservation) => {
          const issued = reservation.items.reduce((sum, item) => sum + Number(item.quantity_issued), 0)
          const required = reservation.items.reduce((sum, item) => sum + Number(item.quantity_required), 0)
          if (reservation.status === 'partial' && issued > 0 && required > issued) {
            acc[reservation.id] = { action: 'close', notes: 'Close outstanding demand after withdrawal' }
          }
          return acc
        },
        {}
      )
    )
    setRefundReversals({})
    setSettlementForm({
      settlement_date: new Date().toISOString().slice(0, 10),
      reason: '',
      retained_amount: '',
      deduction_amount: '',
      notes: '',
      refund_amount: '',
      refund_method: 'bank_transfer',
      refund_reference_number: '',
      refund_proof_text: '',
      refund_proof_attachment_id: null,
      refund_proof_file_name: null,
      refund_reason: 'Withdrawal settlement refund',
    })
  }

  const buildSettlementPayload = () => {
    const actions = Object.entries(invoiceActions)
      .map(([invoiceId, action]) => ({
        invoice_id: Number(invoiceId),
        action: action.action,
        amount: Number(action.amount),
        notes: action.notes.trim() || null,
      }))
      .filter((item) => item.action !== 'none' && Number.isFinite(item.amount) && item.amount > 0)
    const reservation_actions = Object.entries(reservationActions)
      .map(([reservationId, action]) => ({
        reservation_id: Number(reservationId),
        action: action.action,
        notes: action.notes.trim() || null,
      }))
      .filter((item) => item.action !== 'none')

    const refundAmount = Number(settlementForm.refund_amount)
    const payload: Record<string, unknown> = {
      settlement_date: settlementForm.settlement_date,
      reason: settlementForm.reason.trim(),
      retained_amount: Number(settlementForm.retained_amount || 0),
      deduction_amount: Number(settlementForm.deduction_amount || 0),
      notes: settlementForm.notes.trim() || null,
      invoice_actions: actions,
      reservation_actions,
    }
    if (Number.isFinite(refundAmount) && refundAmount > 0) {
      const allocation_reversals = Object.entries(refundReversals)
        .map(([allocationId, amount]) => ({
          allocation_id: Number(allocationId),
          amount: Number(amount),
        }))
        .filter((item) => Number.isFinite(item.amount) && item.amount > 0)
      payload.refund = {
        amount: refundAmount,
        refund_date: settlementForm.settlement_date,
        refund_method: settlementForm.refund_method || null,
        reference_number: settlementForm.refund_reference_number.trim() || null,
        proof_text: settlementForm.refund_proof_text.trim() || null,
        proof_attachment_id: settlementForm.refund_proof_attachment_id,
        reason: settlementForm.refund_reason.trim() || settlementForm.reason.trim(),
        notes: settlementForm.notes.trim() || null,
        ...(allocation_reversals.length ? { allocation_reversals } : {}),
      }
    }
    return payload
  }

  const validateSettlementForm = (mode: 'preview' | 'submit') => {
    const nextErrors: Record<string, string> = {}
    if (!settlementForm.settlement_date) {
      nextErrors.settlement_date = 'Settlement date is required.'
    }
    if (settlementForm.reason.trim().length < 3) {
      nextErrors.reason = 'Reason must be at least 3 characters.'
    }
    const refundAmount = Number(settlementForm.refund_amount || 0)
    if (refundAmount > 0) {
      if (
        mode === 'submit' &&
        !settlementForm.refund_reference_number.trim() &&
        !settlementForm.refund_proof_text.trim() &&
        settlementForm.refund_proof_attachment_id == null
      ) {
        nextErrors.refund_proof = 'Refund reference, proof text or confirmation file is required.'
      }
      if (settlementForm.refund_reason.trim().length < 3) {
        nextErrors.refund_reason = 'Refund reason must be at least 3 characters.'
      }
    }
    const reservationsById = new Map((reservationsApi.data?.items ?? []).map((reservation) => [reservation.id, reservation]))
    const invalidReservationAction = Object.entries(reservationActions).find(([reservationId, action]) => {
      if (action.action === 'none') return false
      const reservation = reservationsById.get(Number(reservationId))
      if (!reservation) return true
      const issued = reservation.items.reduce((sum, item) => sum + Number(item.quantity_issued), 0)
      if (['cancelled', 'closed', 'fulfilled'].includes(reservation.status)) return true
      return action.action === 'cancel' && issued > 0
    })
    if (invalidReservationAction) {
      nextErrors.reservation_actions = 'Partially issued reservations must be closed, not cancelled.'
    }
    setWithdrawErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const previewWithdrawalSettlement = async () => {
    if (!validateSettlementForm('preview')) return
    previewSettlementMutation.reset()
    const result = await previewSettlementMutation.execute(() =>
      api.post(`/students/${resolvedId}/withdrawal-settlements/preview`, buildSettlementPayload())
    )
    if (result) {
      setWithdrawPreview(result)
    } else if (previewSettlementMutation.error) {
      setError(previewSettlementMutation.error)
    }
  }

  const submitWithdrawalSettlement = async () => {
    if (!validateSettlementForm('submit')) return
    createSettlementMutation.reset()
    const result = await createSettlementMutation.execute(() =>
      api.post(`/students/${resolvedId}/withdrawal-settlements`, buildSettlementPayload())
    )
    if (result) {
      setWithdrawDialogOpen(false)
      setWithdrawPreview(null)
      refetchStudent()
      refetchBalance()
      invoicesApi.refetch()
      reservationsApi.refetch()
      settlementHistoryApi.refetch()
      setAllocationResult('Withdrawal settlement posted.')
    } else if (createSettlementMutation.error) {
      setError(createSettlementMutation.error)
    }
  }

  const updateReservationAction = (
    reservation: ReservationResponse,
    next: Partial<{ action: SettlementReservationAction; notes: string }>
  ) => {
    setWithdrawPreview(null)
    setReservationActions((current) => {
      const existing = current[reservation.id] ?? {
        action: 'none' as SettlementReservationAction,
        notes: '',
      }
      return { ...current, [reservation.id]: { ...existing, ...next } }
    })
  }

  const uploadWithdrawRefundProofFile = useCallback(async (file: File) => {
    setUploadingWithdrawRefundProof(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setSettlementForm((current) => ({
        ...current,
        refund_proof_attachment_id: response.data.data.id,
        refund_proof_file_name: file.name,
      }))
      setWithdrawErrors((current) => ({ ...current, refund_proof: '' }))
    } catch {
      setSettlementForm((current) => ({
        ...current,
        refund_proof_attachment_id: null,
        refund_proof_file_name: null,
      }))
      setWithdrawErrors((current) => ({
        ...current,
        refund_proof: 'Failed to upload refund proof file.',
      }))
    } finally {
      setUploadingWithdrawRefundProof(false)
    }
  }, [])

  const updateInvoiceAction = (
    invoice: InvoiceSummary,
    next: Partial<{ action: SettlementInvoiceAction; amount: string; notes: string }>
  ) => {
    setWithdrawPreview(null)
    setInvoiceActions((current) => {
      const existing = current[invoice.id] ?? {
        action: 'none' as SettlementInvoiceAction,
        amount: '',
        notes: '',
      }
      const updated = { ...existing, ...next }
      if (next.action && next.action !== 'none' && !updated.amount) {
        updated.amount = String(invoice.amount_due)
      }
      return { ...current, [invoice.id]: updated }
    })
  }

  if (!student) {
    return (
      <div>
        {error && <Alert severity="error">{error}</Alert>}
      </div>
    )
  }

  return (
    <div>
      {error && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {allocationResult && (
        <Alert severity="success" className="mb-4" onClose={() => setAllocationResult(null)}>
          {allocationResult}
        </Alert>
      )}

      <StudentHeader
        student={student}
        balance={balance}
        debt={debt}
        grades={grades}
        transportZones={transportZones}
        onStudentUpdate={loadStudent}
        onError={handleError}
        onWithdraw={openWithdrawDialog}
      />

      {(settlementHistoryApi.data ?? []).length > 0 && (
        <section className="mt-6">
          <Typography variant="h6" className="mb-3">Withdrawal settlements</Typography>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Date</TableHeaderCell>
                  <TableHeaderCell>Settlement #</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Refund</TableHeaderCell>
                  <TableHeaderCell align="right">Write-off</TableHeaderCell>
                  <TableHeaderCell align="right">Cancelled</TableHeaderCell>
                  <TableHeaderCell align="right">Remaining debt</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(settlementHistoryApi.data ?? []).map((settlement) => (
                  <TableRow key={settlement.id}>
                    <TableCell>{formatDate(settlement.settlement_date)}</TableCell>
                    <TableCell>{settlement.settlement_number}</TableCell>
                    <TableCell>{settlement.status}</TableCell>
                    <TableCell>{settlement.refund_number ?? formatMoney(settlement.refund_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(settlement.write_off_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(settlement.cancelled_amount)}</TableCell>
                    <TableCell align="right">{formatMoney(settlement.remaining_collectible_debt)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      )}

      <Tabs value={tab} onChange={handleTabChange} className="mt-6">
        <TabsList>
          <Tab value="overview">Overview</Tab>
          <Tab value="invoices">Invoices</Tab>
          <Tab value="payments">Payments</Tab>
          <Tab value="items">Items to issue</Tab>
          <Tab value="statement">Statement</Tab>
        </TabsList>

        <TabPanel value="overview">
          <OverviewTab student={student} studentId={resolvedId} onError={handleError} />
        </TabPanel>

        <TabPanel value="invoices">
          <InvoicesTab
            studentId={resolvedId}
            transportZoneId={student.transport_zone_id}
            onError={handleError}
            onDebtChange={handleDebtChange}
            initialInvoices={invoicesApi.data?.items ?? null}
            invoicesLoading={invoicesApi.loading}
          />
        </TabPanel>

        <TabPanel value="payments">
          <PaymentsTab
            studentId={resolvedId}
            onError={handleError}
            onBalanceChange={handleBalanceChange}
            onAllocationResult={handleAllocationResult}
            initialInvoices={invoicesApi.data?.items ?? null}
            invoicesLoading={invoicesApi.loading}
          />
        </TabPanel>

        <TabPanel value="items">
          <ItemsToIssueTab studentId={resolvedId} onError={handleError} />
        </TabPanel>

        <TabPanel value="statement">
          <StatementTab studentId={resolvedId} onError={handleError} />
        </TabPanel>
      </Tabs>

      <Dialog open={withdrawDialogOpen} onClose={() => setWithdrawDialogOpen(false)} maxWidth="xl" fullWidth>
        <DialogCloseButton onClose={() => setWithdrawDialogOpen(false)} />
        <DialogTitle>Withdraw student</DialogTitle>
        <DialogContent>
          <div className="space-y-5 mt-4">
            {(withdrawErrors.reason ||
              withdrawErrors.settlement_date ||
              withdrawErrors.refund_proof ||
              withdrawErrors.refund_reason ||
              withdrawErrors.reservation_actions ||
              previewSettlementMutation.error ||
              createSettlementMutation.error) && (
              <Alert severity="error">
                {withdrawErrors.reason ||
                  withdrawErrors.settlement_date ||
                  withdrawErrors.refund_proof ||
                  withdrawErrors.refund_reason ||
                  withdrawErrors.reservation_actions ||
                  previewSettlementMutation.error ||
                  createSettlementMutation.error}
              </Alert>
            )}

            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Student balance</Typography>
                <Typography variant="body2" className="font-semibold">{formatMoney(balance?.balance ?? -debt)}</Typography>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Outstanding debt</Typography>
                <Typography variant="body2" className="font-semibold">{formatMoney(debt)}</Typography>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Account credit</Typography>
                <Typography variant="body2" className="font-semibold">{formatMoney(balance?.available_balance ?? 0)}</Typography>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Paid total</Typography>
                <Typography variant="body2" className="font-semibold">
                  {withdrawPreview ? formatMoney(withdrawPreview.total_paid) : '—'}
                </Typography>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Settlement date"
                type="date"
                value={settlementForm.settlement_date}
                error={withdrawErrors.settlement_date}
                onChange={(event) => {
                  setWithdrawPreview(null)
                  setSettlementForm((current) => ({ ...current, settlement_date: event.target.value }))
                }}
              />
              <Input
                label="Reason"
                value={settlementForm.reason}
                error={withdrawErrors.reason}
                onChange={(event) => {
                  setWithdrawPreview(null)
                  setSettlementForm((current) => ({ ...current, reason: event.target.value }))
                }}
              />
              <Input
                label="Retained amount"
                type="number"
                value={settlementForm.retained_amount}
                onChange={(event) => setSettlementForm((current) => ({ ...current, retained_amount: event.target.value }))}
              />
              <Input
                label="Deduction amount"
                type="number"
                value={settlementForm.deduction_amount}
                onChange={(event) => setSettlementForm((current) => ({ ...current, deduction_amount: event.target.value }))}
              />
            </div>

            <div>
              <Typography variant="body2" className="font-semibold mb-2">Invoice actions</Typography>
              <div className="overflow-hidden rounded-lg border border-slate-200">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Invoice</TableHeaderCell>
                      <TableHeaderCell>Status</TableHeaderCell>
                      <TableHeaderCell align="right">Paid</TableHeaderCell>
                      <TableHeaderCell align="right">Due</TableHeaderCell>
                      <TableHeaderCell>Action</TableHeaderCell>
                      <TableHeaderCell align="right">Amount</TableHeaderCell>
                      <TableHeaderCell>Notes</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(invoicesApi.data?.items ?? []).map((invoice) => {
                      const action = invoiceActions[invoice.id] ?? { action: 'none', amount: '', notes: '' }
                      return (
                        <TableRow key={invoice.id}>
                          <TableCell>
                            <div className="font-medium">{invoice.invoice_number}</div>
                            <div className="text-xs text-slate-500">
                              {invoice.invoice_type.replace(/_/g, ' ')}
                              {invoice.due_date ? ` · due ${formatDate(invoice.due_date)}` : ''}
                            </div>
                          </TableCell>
                          <TableCell>{invoice.status}</TableCell>
                          <TableCell align="right">{formatMoney(invoice.paid_total)}</TableCell>
                          <TableCell align="right">{formatMoney(invoice.amount_due)}</TableCell>
                          <TableCell>
                            <Select
                              value={action.action}
                              onChange={(event) =>
                                updateInvoiceAction(invoice, {
                                  action: event.target.value as SettlementInvoiceAction,
                                })
                              }
                            >
                              <option value="none">None</option>
                              <option value="cancel_unpaid">Cancel unpaid</option>
                              <option value="write_off">Write off</option>
                              <option value="keep_charged">Keep charged</option>
                            </Select>
                          </TableCell>
                          <TableCell align="right">
                            <Input
                              type="number"
                              min="0"
                              step="0.01"
                              value={action.amount}
                              containerClassName="min-w-28"
                              onChange={(event) => updateInvoiceAction(invoice, { amount: event.target.value })}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              value={action.notes}
                              onChange={(event) => updateInvoiceAction(invoice, { notes: event.target.value })}
                            />
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>

            {(reservationsApi.data?.items ?? []).some((reservation) =>
              ['pending', 'partial'].includes(reservation.status)
            ) && (
              <div>
                <Typography variant="body2" className="font-semibold mb-2">Reservation actions</Typography>
                <div className="overflow-hidden rounded-lg border border-slate-200">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeaderCell>Reservation</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell>Items</TableHeaderCell>
                        <TableHeaderCell>Action</TableHeaderCell>
                        <TableHeaderCell>Notes</TableHeaderCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(reservationsApi.data?.items ?? [])
                        .filter((reservation) => ['pending', 'partial'].includes(reservation.status))
                        .map((reservation) => {
                          const action = reservationActions[reservation.id] ?? { action: 'none', notes: '' }
                          const issued = reservation.items.reduce((sum, item) => sum + Number(item.quantity_issued), 0)
                          return (
                            <TableRow key={reservation.id}>
                              <TableCell>
                                <div className="font-medium">#{reservation.id}</div>
                                <div className="text-xs text-slate-500">Invoice #{reservation.invoice_id}</div>
                              </TableCell>
                              <TableCell>{reservation.status}</TableCell>
                              <TableCell>
                                <div className="space-y-1">
                                  {reservation.items.map((item) => (
                                    <div key={item.id} className="text-sm">
                                      {item.item_name ?? `Item #${item.item_id}`} · {item.quantity_issued}/{item.quantity_required}
                                    </div>
                                  ))}
                                </div>
                              </TableCell>
                              <TableCell>
                                <Select
                                  value={action.action}
                                  onChange={(event) =>
                                    updateReservationAction(reservation, {
                                      action: event.target.value as SettlementReservationAction,
                                    })
                                  }
                                >
                                  <option value="none">None</option>
                                  {issued === 0 && <option value="cancel">Cancel</option>}
                                  <option value="close">Close as is</option>
                                </Select>
                              </TableCell>
                              <TableCell>
                                <Input
                                  value={action.notes}
                                  onChange={(event) => updateReservationAction(reservation, { notes: event.target.value })}
                                />
                              </TableCell>
                            </TableRow>
                          )
                        })}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            <div className="space-y-3 rounded-lg border border-slate-200 p-4">
              <Typography variant="body2" className="font-semibold">Refund</Typography>
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="Refund amount"
                  type="number"
                  value={settlementForm.refund_amount}
                  onChange={(event) => {
                    setWithdrawPreview(null)
                    setSettlementForm((current) => ({ ...current, refund_amount: event.target.value }))
                  }}
                />
                <Select
                  label="Refund method"
                  value={settlementForm.refund_method}
                  onChange={(event) => setSettlementForm((current) => ({ ...current, refund_method: event.target.value }))}
                >
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="mpesa">M-Pesa</option>
                  <option value="cash">Cash</option>
                  <option value="other">Other</option>
                </Select>
                <Input
                  label="Refund reference"
                  value={settlementForm.refund_reference_number}
                  error={withdrawErrors.refund_proof}
                  onChange={(event) => setSettlementForm((current) => ({ ...current, refund_reference_number: event.target.value }))}
                />
                <Input
                  label="Refund reason"
                  value={settlementForm.refund_reason}
                  error={withdrawErrors.refund_reason}
                  onChange={(event) => setSettlementForm((current) => ({ ...current, refund_reason: event.target.value }))}
                />
              </div>
              <Textarea
                label="Refund proof text"
                value={settlementForm.refund_proof_text}
                onChange={(event) => {
                  setWithdrawErrors((current) => ({ ...current, refund_proof: '' }))
                  setSettlementForm((current) => ({ ...current, refund_proof_text: event.target.value }))
                }}
                rows={2}
              />
              <FileDropzone
                title="Upload refund confirmation (image/PDF)"
                accept="image/*,.pdf,application/pdf"
                fileName={settlementForm.refund_proof_file_name}
                disabled={uploadingWithdrawRefundProof}
                loading={uploadingWithdrawRefundProof}
                onFileSelected={uploadWithdrawRefundProofFile}
              />

              {(refundAllocationOptionsApi.data ?? []).length > 0 && (
                <div>
                  <Typography variant="body2" className="font-semibold mb-2">Manual refund allocation impact</Typography>
                  <div className="overflow-hidden rounded-lg border border-slate-200">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Invoice</TableHeaderCell>
                          <TableHeaderCell align="right">Allocated</TableHeaderCell>
                          <TableHeaderCell align="right">Due now</TableHeaderCell>
                          <TableHeaderCell align="right">Reverse</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {(refundAllocationOptionsApi.data ?? []).map((option) => (
                          <TableRow key={option.allocation_id}>
                            <TableCell>
                              <div className="font-medium">{option.invoice_number}</div>
                              <div className="text-xs text-slate-500">
                                {option.student_name ?? `Student #${option.student_id}`}
                              </div>
                            </TableCell>
                            <TableCell align="right">{formatMoney(option.current_allocation_amount)}</TableCell>
                            <TableCell align="right">{formatMoney(option.invoice_amount_due)}</TableCell>
                            <TableCell align="right">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={refundReversals[option.allocation_id] ?? ''}
                                containerClassName="min-w-28"
                                onChange={(event) => {
                                  setWithdrawPreview(null)
                                  setRefundReversals((current) => ({
                                    ...current,
                                    [option.allocation_id]: event.target.value,
                                  }))
                                }}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </div>

            <Textarea
              label="Settlement notes"
              value={settlementForm.notes}
              onChange={(event) => setSettlementForm((current) => ({ ...current, notes: event.target.value }))}
              rows={3}
            />

            {withdrawPreview && (
              <div className="space-y-4 rounded-lg border border-slate-200 p-4">
                <div className="grid gap-3 md:grid-cols-5">
                  <div>
                    <Typography variant="body2" color="secondary">Refund</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.refund_amount)}</Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Write-off</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.write_off_amount)}</Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Cancelled</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.cancelled_amount)}</Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Retained</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.retained_amount)}</Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Remaining debt</Typography>
                    <Typography variant="body2" className="font-semibold">
                      {formatMoney(withdrawPreview.remaining_collectible_debt_after)}
                    </Typography>
                  </div>
                </div>
                {withdrawPreview.warnings.length > 0 && (
                  <Alert severity="warning">{withdrawPreview.warnings.join(' ')}</Alert>
                )}
                {withdrawPreview.invoice_impacts.length > 0 && (
                  <div className="overflow-hidden rounded-lg border border-slate-200">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Invoice</TableHeaderCell>
                          <TableHeaderCell>Action</TableHeaderCell>
                          <TableHeaderCell align="right">Amount</TableHeaderCell>
                          <TableHeaderCell align="right">Due before</TableHeaderCell>
                          <TableHeaderCell align="right">Due after</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {withdrawPreview.invoice_impacts.map((impact) => (
                          <TableRow key={`${impact.invoice_id}-${impact.action}`}>
                            <TableCell>{impact.invoice_number}</TableCell>
                            <TableCell>{impact.action.replace(/_/g, ' ')}</TableCell>
                            <TableCell align="right">{formatMoney(impact.amount)}</TableCell>
                            <TableCell align="right">{formatMoney(impact.amount_due_before)}</TableCell>
                            <TableCell align="right">{formatMoney(impact.amount_due_after)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
                {withdrawPreview.reservation_impacts.length > 0 && (
                  <div className="overflow-hidden rounded-lg border border-slate-200">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Reservation</TableHeaderCell>
                          <TableHeaderCell>Action</TableHeaderCell>
                          <TableHeaderCell>Status</TableHeaderCell>
                          <TableHeaderCell align="right">Issued</TableHeaderCell>
                          <TableHeaderCell align="right">Remaining after</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {withdrawPreview.reservation_impacts.map((impact) => (
                          <TableRow key={`${impact.reservation_id}-${impact.action}`}>
                            <TableCell>
                              #{impact.reservation_id}
                              {impact.invoice_number ? ` · ${impact.invoice_number}` : ''}
                            </TableCell>
                            <TableCell>{impact.action}</TableCell>
                            <TableCell>{impact.status_before} → {impact.status_after}</TableCell>
                            <TableCell align="right">{impact.quantity_issued}/{impact.quantity_required}</TableCell>
                            <TableCell align="right">{impact.quantity_remaining_after}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            )}
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setWithdrawDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="outlined"
            onClick={previewWithdrawalSettlement}
            disabled={previewSettlementMutation.loading || createSettlementMutation.loading}
          >
            {previewSettlementMutation.loading ? <Spinner size="small" /> : 'Preview'}
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={submitWithdrawalSettlement}
            disabled={createSettlementMutation.loading}
          >
            {createSettlementMutation.loading ? <Spinner size="small" /> : 'Post settlement'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
