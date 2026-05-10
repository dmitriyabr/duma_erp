import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { canCancelPayment, canInvoiceTerm, canManageBillingAccounts } from '../../utils/permissions'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import { formatStudentNumberShort } from '../../utils/studentNumber'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { FileDropzone } from '../../components/ui/FileDropzone'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components/ui/Table'
import { Textarea } from '../../components/ui/Textarea'
import { ToggleButton, ToggleButtonGroup } from '../../components/ui/ToggleButton'
import { Typography } from '../../components/ui/Typography'
import type { InvoiceDetail, InvoiceLine } from '../students/types'
import { BillingAccountChildEditor } from './components/BillingAccountChildEditor'
import {
  buildBillingChildPayload,
  createEmptyBillingChildDraft,
  type BillingAccountChildDraft,
  type BillingAccountChildErrors,
  validateBillingChildDraft,
} from './components/billingAccountChildForm'

interface BillingAccountMember {
  student_id: number
  student_number: string
  student_name: string
  grade_name?: string | null
  guardian_name: string
  guardian_phone: string
  status: string
}

interface BillingAccountDetail {
  id: number
  account_number: string
  display_name: string
  primary_guardian_name?: string | null
  primary_guardian_phone?: string | null
  primary_guardian_email?: string | null
  notes?: string | null
  member_count: number
  available_balance: number
  outstanding_debt: number
  balance: number
  members: BillingAccountMember[]
}

interface BillingStudent {
  id: number
  full_name: string
  student_number: string
  grade_name?: string | null
  billing_account_id?: number | null
  billing_account_member_count?: number | null
}

interface InvoiceRow {
  id: number
  invoice_number: string
  student_id: number
  student_name?: string | null
  invoice_type: string
  status: string
  total: number
  paid_total: number
  amount_due: number
  issue_date?: string | null
  due_date?: string | null
}

interface PaymentRow {
  id: number
  payment_number: string
  receipt_number?: string | null
  student_id: number
  student_name?: string | null
  amount: number
  payment_method: string
  payment_date: string
  reference?: string | null
  status: string
  refunded_amount?: number
  refundable_amount?: number
  refund_status?: string
}

interface StatementEntry {
  date: string
  entry_type: string
  description: string
  reference?: string | null
  payment_id?: number | null
  refund_id?: number | null
  allocation_id?: number | null
  invoice_id?: number | null
  credit?: number | null
  debit?: number | null
  balance: number
}

interface StatementResponse {
  opening_balance: number
  closing_balance: number
  total_credits: number
  total_debits: number
  entries: StatementEntry[]
}

interface RefundPaymentSourceImpact {
  payment_id: number
  payment_number: string
  receipt_number?: string | null
  payment_date: string
  payment_amount: number
  already_refunded_amount: number
  source_amount: number
}

interface RefundAllocationImpact {
  allocation_id: number
  invoice_id: number
  invoice_number: string
  student_id: number
  student_name?: string | null
  invoice_type?: string | null
  invoice_status?: string | null
  issue_date?: string | null
  due_date?: string | null
  current_allocation_amount: number
  reversal_amount: number
  invoice_paid_total_before: number
  invoice_amount_due_before: number
  invoice_paid_total_after: number
  invoice_amount_due_after: number
}

interface RefundAllocationOption {
  allocation_id: number
  invoice_id: number
  invoice_number: string
  student_id: number
  student_name?: string | null
  invoice_type: string
  invoice_status: string
  issue_date?: string | null
  due_date?: string | null
  current_allocation_amount: number
  invoice_paid_total: number
  invoice_amount_due: number
  invoice_total: number
}

interface BillingAccountRefundPreview {
  billing_account_id: number
  amount: number
  completed_payments_total: number
  posted_refunds_total: number
  current_allocated_total: number
  available_credit: number
  refundable_total: number
  amount_to_reopen: number
  allocation_reversals: RefundAllocationImpact[]
  payment_sources: RefundPaymentSourceImpact[]
}

interface BillingAccountRefund {
  id: number
  refund_number?: string | null
  payment_id?: number | null
  billing_account_id: number
  amount: number
  refund_date: string
  refund_method?: string | null
  reference_number?: string | null
  proof_attachment_id?: number | null
  reason: string
  notes?: string | null
  payment_sources: Array<{
    id: number
    payment_id: number
    payment_number?: string | null
    receipt_number?: string | null
    amount: number
  }>
  allocation_reversals: RefundAllocationImpact[]
}

interface WithdrawalInvoiceImpact {
  invoice_id: number
  invoice_number: string
  student_id: number
  student_name?: string | null
  action: string
  amount: number
  amount_due_before: number
  amount_due_after: number
  status_before: string
  status_after: string
}

interface WithdrawalSettlementPreview {
  billing_account_id: number
  student_ids: number[]
  student_names: string[]
  current_outstanding_debt: number
  retained_amount: number
  deduction_amount: number
  write_off_amount: number
  cancelled_amount: number
  refund_amount: number
  remaining_collectible_debt_after: number
  invoice_impacts: WithdrawalInvoiceImpact[]
  refund_preview?: BillingAccountRefundPreview | null
  warnings: string[]
}

interface WithdrawalSettlement {
  id: number
  settlement_number: string
  settlement_date: string
  status: string
  refund_id?: number | null
  refund_number?: string | null
  write_off_amount: number
  cancelled_amount: number
  refund_amount: number
  remaining_collectible_debt: number
  reason: string
  students: Array<{
    student_id: number
    student_name?: string | null
    status_before: string
    status_after: string
  }>
}

interface GenerationResult {
  school_fee_invoices_created: number
  transport_invoices_created: number
  students_skipped: number
  total_students_processed: number
}

export const BillingAccountDetailPage = () => {
  const { accountId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { grades, transportZones, error: referencedError } = useReferencedData()
  const canManage = canManageBillingAccounts(user)
  const canRefund = canCancelPayment(user)
  const resolvedId = Number(accountId)

  const { data: account, error: accountError, loading: accountLoading, refetch } = useApi<BillingAccountDetail>(
    resolvedId ? `/billing-accounts/${resolvedId}` : null
  )
  const invoicesApi = useApi<PaginatedResponse<InvoiceRow>>(
    resolvedId ? '/invoices' : null,
    {
      params: { billing_account_id: resolvedId, page: 1, limit: 100 },
    },
    [resolvedId]
  )
  const paymentsApi = useApi<PaginatedResponse<PaymentRow>>(
    resolvedId ? '/payments' : null,
    {
      params: { billing_account_id: resolvedId, page: 1, limit: 100 },
    },
    [resolvedId]
  )
  const refundsApi = useApi<BillingAccountRefund[]>(
    resolvedId ? `/billing-accounts/${resolvedId}/refunds` : null,
    undefined,
    [resolvedId]
  )
  const withdrawalSettlementsApi = useApi<WithdrawalSettlement[]>(
    resolvedId ? `/billing-accounts/${resolvedId}/withdrawal-settlements` : null,
    undefined,
    [resolvedId]
  )
  const refundAllocationOptionsApi = useApi<RefundAllocationOption[]>(
    resolvedId ? `/billing-accounts/${resolvedId}/refunds/allocation-options` : null,
    undefined,
    [resolvedId]
  )
  const studentsApi = useApi<PaginatedResponse<BillingStudent>>('/students', {
    params: { status: 'active', page: 1, limit: 500 },
  }, [])
  const activeTermApi = useApi<{ id: number } | null>('/terms/active')

  const addMembersMutation = useApiMutation<BillingAccountDetail>()
  const addChildMutation = useApiMutation<BillingAccountDetail>()
  const generateTermMutation = useApiMutation<GenerationResult>()
  const statementMutation = useApiMutation<StatementResponse>()
  const autoAllocateMutation = useApiMutation<{
    total_allocated: number
    invoices_fully_paid: number
    invoices_partially_paid: number
    remaining_balance: number
  }>()
  const deleteAllocationMutation = useApiMutation<boolean>()
  const manualAllocationMutation = useApiMutation<unknown>()
  const refundPaymentMutation = useApiMutation<unknown>()
  const accountRefundPreviewMutation = useApiMutation<BillingAccountRefundPreview>()
  const accountRefundMutation = useApiMutation<BillingAccountRefund>()
  const withdrawalPreviewMutation = useApiMutation<WithdrawalSettlementPreview>()
  const withdrawalMutation = useApiMutation<WithdrawalSettlement>()

  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addChildDialogOpen, setAddChildDialogOpen] = useState(false)
  const [sellItemDialogOpen, setSellItemDialogOpen] = useState(false)
  const [allocationDialogOpen, setAllocationDialogOpen] = useState(false)
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | null>(null)
  const [selectedSellStudentId, setSelectedSellStudentId] = useState<number | ''>('')
  const [selectedStudentIds, setSelectedStudentIds] = useState<number[]>([])
  const [childDraft, setChildDraft] = useState<BillingAccountChildDraft>(createEmptyBillingChildDraft())
  const [childErrors, setChildErrors] = useState<BillingAccountChildErrors>({})
  const [allocationForm, setAllocationForm] = useState({
    invoice_id: '',
    invoice_line_id: '',
    amount: '',
  })
  const [allocationLines, setAllocationLines] = useState<InvoiceLine[]>([])
  const [statementForm, setStatementForm] = useState(() => {
    const now = new Date()
    const start = new Date(now.getFullYear(), now.getMonth(), 1)
    return {
      date_from: start.toISOString().slice(0, 10),
      date_to: now.toISOString().slice(0, 10),
    }
  })
  const [statement, setStatement] = useState<StatementResponse | null>(null)
  const [refundDialogPayment, setRefundDialogPayment] = useState<PaymentRow | null>(null)
  const [accountRefundDialogOpen, setAccountRefundDialogOpen] = useState(false)
  const [accountRefundPreview, setAccountRefundPreview] = useState<BillingAccountRefundPreview | null>(null)
  const [accountRefundValidationErrors, setAccountRefundValidationErrors] = useState<Record<string, string>>({})
  const [withdrawDialogOpen, setWithdrawDialogOpen] = useState(false)
  const [withdrawPreview, setWithdrawPreview] = useState<WithdrawalSettlementPreview | null>(null)
  const [withdrawValidationErrors, setWithdrawValidationErrors] = useState<Record<string, string>>({})
  const [withdrawStudentIds, setWithdrawStudentIds] = useState<number[]>([])
  const [withdrawInvoiceActions, setWithdrawInvoiceActions] = useState<
    Record<number, { action: 'none' | 'cancel_unpaid' | 'write_off' | 'keep_charged'; amount: string; notes: string }>
  >({})
  const [withdrawManualReversals, setWithdrawManualReversals] = useState<Record<number, string>>({})
  const [withdrawForm, setWithdrawForm] = useState({
    settlement_date: new Date().toISOString().slice(0, 10),
    reason: '',
    retained_amount: '0',
    deduction_amount: '0',
    notes: '',
    refund_amount: '',
    refund_method: 'mpesa',
    reference_number: '',
    proof_text: '',
    refund_reason: '',
    refund_notes: '',
  })
  const [refundAllocationMode, setRefundAllocationMode] = useState<'auto' | 'manual'>('auto')
  const [manualRefundReversals, setManualRefundReversals] = useState<Record<number, string>>({})
  const [refundForm, setRefundForm] = useState({
    amount: '',
    refund_date: new Date().toISOString().slice(0, 10),
    refund_method: 'mpesa',
    reference_number: '',
    proof_text: '',
    proof_attachment_id: null as number | null,
    proof_file_name: null as string | null,
    reason: '',
    notes: '',
  })
  const [uploadingRefundProof, setUploadingRefundProof] = useState(false)
  const [refundValidationError, setRefundValidationError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const invoiceDetailApi = useApi<InvoiceDetail>(
    selectedInvoiceId ? `/invoices/${selectedInvoiceId}` : null,
    undefined,
    [selectedInvoiceId]
  )

  const currentMemberIds = useMemo(
    () => new Set(account?.members.map((member) => member.student_id) ?? []),
    [account]
  )
  const eligibleStudents = useMemo(
    () =>
      (studentsApi.data?.items ?? []).filter((student) => !currentMemberIds.has(student.id)),
    [currentMemberIds, studentsApi.data?.items]
  )

  const toggleStudent = (studentId: number) => {
    setSelectedStudentIds((current) =>
      current.includes(studentId)
        ? current.filter((id) => id !== studentId)
        : [...current, studentId]
    )
  }

  const openAddChildDialog = () => {
    setChildDraft(createEmptyBillingChildDraft())
    setChildErrors({})
    setAddChildDialogOpen(true)
  }

  const getRefundableAmount = (payment: PaymentRow | null | undefined) =>
    Number(payment?.refundable_amount ?? payment?.amount ?? 0)

  const getPaymentStatusLabel = (payment: PaymentRow) => {
    if (payment.refund_status === 'full') return 'completed / refunded'
    if (payment.refund_status === 'partial') return 'completed / partially refunded'
    return payment.status
  }

  const formatInvoiceTypeLabel = (value?: string | null) =>
    value ? value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()) : 'Invoice'

  const formatInvoiceStatusLabel = (value?: string | null) =>
    value ? value.replace(/_/g, ' ') : 'unknown'

  const getRefundAmountToReopen = () =>
    Math.max(0, Number(refundForm.amount || 0) - Math.max(Number(account?.available_balance ?? 0), 0))

  const getManualReversalTotal = () =>
    Object.values(manualRefundReversals).reduce((sum, value) => {
      const amount = Number(value)
      return sum + (Number.isFinite(amount) && amount > 0 ? amount : 0)
    }, 0)

  const buildManualAllocationReversals = () =>
    Object.entries(manualRefundReversals)
      .map(([allocationId, amountValue]) => ({
        allocation_id: Number(allocationId),
        amount: Number(amountValue),
      }))
      .filter((item) => Number.isFinite(item.amount) && item.amount > 0)

  const getAllocationInvoiceLabel = (
    allocation: RefundAllocationOption | RefundAllocationImpact
  ) => `${allocation.invoice_number} · ${formatInvoiceTypeLabel(allocation.invoice_type)}`

  const openRefundDialog = (payment: PaymentRow) => {
    setRefundDialogPayment(payment)
    setRefundForm({
      amount: String(getRefundableAmount(payment)),
      refund_date: new Date().toISOString().slice(0, 10),
      refund_method: 'mpesa',
      reference_number: '',
      proof_text: '',
      proof_attachment_id: null,
      proof_file_name: null,
      reason: '',
      notes: '',
    })
    setUploadingRefundProof(false)
    setRefundValidationError(null)
  }

  const openAccountRefundDialog = () => {
    setRefundDialogPayment(null)
    setAccountRefundDialogOpen(true)
    setAccountRefundPreview(null)
    setAccountRefundValidationErrors({})
    setRefundAllocationMode('auto')
    setManualRefundReversals({})
    setRefundForm({
      amount: String(Math.max(Number(account?.available_balance ?? 0), 0)),
      refund_date: new Date().toISOString().slice(0, 10),
      refund_method: 'mpesa',
      reference_number: '',
      proof_text: '',
      proof_attachment_id: null,
      proof_file_name: null,
      reason: '',
      notes: '',
    })
    setUploadingRefundProof(false)
    setRefundValidationError(null)
  }

  const openWithdrawDialog = () => {
    const activeIds = activeMembers.map((member) => member.student_id)
    const nextActions: Record<number, { action: 'none' | 'cancel_unpaid' | 'write_off' | 'keep_charged'; amount: string; notes: string }> = {}
    invoices
      .filter((invoice) => activeIds.includes(invoice.student_id) && Number(invoice.amount_due) > 0)
      .forEach((invoice) => {
        nextActions[invoice.id] = {
          action: Number(invoice.paid_total) > 0 ? 'write_off' : 'cancel_unpaid',
          amount: String(invoice.amount_due),
          notes: '',
        }
      })
    setWithdrawStudentIds(activeIds)
    setWithdrawInvoiceActions(nextActions)
    setWithdrawManualReversals({})
    setWithdrawPreview(null)
    setWithdrawValidationErrors({})
    setWithdrawForm({
      settlement_date: new Date().toISOString().slice(0, 10),
      reason: '',
      retained_amount: '0',
      deduction_amount: '0',
      notes: '',
      refund_amount: '',
      refund_method: 'mpesa',
      reference_number: '',
      proof_text: '',
      refund_reason: '',
      refund_notes: '',
    })
    setWithdrawDialogOpen(true)
  }

  const selectedWithdrawInvoiceRows = () =>
    invoices.filter((invoice) => withdrawStudentIds.includes(invoice.student_id))

  const getWithdrawRefundAmount = () => {
    const amount = Number(withdrawForm.refund_amount)
    return Number.isFinite(amount) && amount > 0 ? amount : 0
  }

  const getWithdrawRefundAmountToReopen = () =>
    Math.max(0, getWithdrawRefundAmount() - Math.max(Number(account?.available_balance ?? 0), 0))

  const getWithdrawManualReversalTotal = () =>
    Object.values(withdrawManualReversals).reduce((sum, value) => {
      const amount = Number(value)
      return sum + (Number.isFinite(amount) && amount > 0 ? amount : 0)
    }, 0)

  const getWithdrawRefundReopenByInvoice = (
    reversals: Record<number, string> = withdrawManualReversals
  ) => {
    const optionsByAllocation = new Map(
      (refundAllocationOptionsApi.data ?? []).map((option) => [option.allocation_id, option])
    )
    return Object.entries(reversals).reduce<Record<number, number>>((acc, [allocationId, value]) => {
      const amount = Number(value)
      const option = optionsByAllocation.get(Number(allocationId))
      if (!option || !Number.isFinite(amount) || amount <= 0) return acc
      acc[option.invoice_id] = (acc[option.invoice_id] ?? 0) + amount
      return acc
    }, {})
  }

  const getWithdrawInvoiceAmountToClose = (
    invoice: InvoiceRow,
    reopenByInvoice: Record<number, number> = getWithdrawRefundReopenByInvoice()
  ) => Number(invoice.amount_due) + Number(reopenByInvoice[invoice.id] ?? 0)

  const buildWithdrawManualAllocationReversals = () =>
    Object.entries(withdrawManualReversals)
      .map(([allocationId, amountValue]) => ({
        allocation_id: Number(allocationId),
        amount: Number(amountValue),
      }))
      .filter((item) => Number.isFinite(item.amount) && item.amount > 0)

  const validateWithdrawForm = (mode: 'preview' | 'submit' = 'submit') => {
    const nextErrors: Record<string, string> = {}
    if (!withdrawStudentIds.length) {
      nextErrors.students = 'Select at least one student.'
    }
    if (!withdrawForm.settlement_date) {
      nextErrors.settlement_date = 'Settlement date is required.'
    }
    if (!withdrawForm.reason.trim() || withdrawForm.reason.trim().length < 3) {
      nextErrors.reason = 'Reason must be at least 3 characters.'
    }
    const refundAmount = getWithdrawRefundAmount()
    if (withdrawForm.refund_amount && refundAmount <= 0) {
      nextErrors.refund_amount = 'Refund amount must be greater than zero.'
    }
    const hasRefundProof =
      Boolean(withdrawForm.reference_number.trim()) || Boolean(withdrawForm.proof_text.trim())
    if (mode === 'submit' && refundAmount > 0 && !hasRefundProof) {
      nextErrors.refund_proof = 'Reference or proof text is required for refund.'
    }
    if (refundAmount > 0) {
      const amountToReopen = getWithdrawRefundAmountToReopen()
      const selectedTotal = getWithdrawManualReversalTotal()
      const selectedTotalCents = Math.round(selectedTotal * 100)
      const amountToReopenCents = Math.round(amountToReopen * 100)
      const selectedStudentSet = new Set(withdrawStudentIds)
      const optionsById = new Map(
        (refundAllocationOptionsApi.data ?? [])
          .filter((option) => selectedStudentSet.has(option.student_id))
          .map((option) => [option.allocation_id, option])
      )
      const hasInvalidAmount = buildWithdrawManualAllocationReversals().some((item) => {
        const option = optionsById.get(item.allocation_id)
        return !option || Math.round(item.amount * 100) > Math.round(option.current_allocation_amount * 100)
      })
      if (hasInvalidAmount) {
        nextErrors.refund_allocations = 'Selected reversal exceeds the current invoice allocation.'
      } else if (amountToReopenCents > 0 && selectedTotalCents !== amountToReopenCents) {
        nextErrors.refund_allocations = `Manual reversals must total ${formatMoney(amountToReopen)}.`
      }
    }
    const reopenByInvoice = getWithdrawRefundReopenByInvoice()
    const invoicesById = new Map(selectedWithdrawInvoiceRows().map((invoice) => [invoice.id, invoice]))
    const invalidInvoiceAction = Object.entries(withdrawInvoiceActions).find(([invoiceId, action]) => {
      if (action.action === 'none') return false
      const invoice = invoicesById.get(Number(invoiceId))
      if (!invoice) return false
      const amount = Number(action.amount)
      if (!Number.isFinite(amount) || amount <= 0) return true
      const amountToClose = getWithdrawInvoiceAmountToClose(invoice, reopenByInvoice)
      if (action.action === 'cancel_unpaid') {
        return Number(invoice.paid_total) > 0 || Math.round(amount * 100) > Math.round(Number(invoice.amount_due) * 100)
      }
      if (action.action === 'write_off') {
        return Math.round(amount * 100) > Math.round(amountToClose * 100)
      }
      return false
    })
    if (invalidInvoiceAction) {
      nextErrors.invoice_actions =
        'Check invoice actions: cancel only unpaid invoices, and write-off cannot exceed current due plus refund reopening.'
    }
    setWithdrawValidationErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const buildWithdrawPayload = () => {
    const invoice_actions = Object.entries(withdrawInvoiceActions)
      .map(([invoiceId, action]) => ({
        invoice_id: Number(invoiceId),
        action: action.action,
        amount: Number(action.amount),
        notes: action.notes.trim() || null,
      }))
      .filter((action) => action.action !== 'none' && Number.isFinite(action.amount) && action.amount > 0)

    const refundAmount = getWithdrawRefundAmount()
    return {
      student_ids: withdrawStudentIds,
      settlement_date: withdrawForm.settlement_date,
      reason: withdrawForm.reason.trim(),
      retained_amount: Number(withdrawForm.retained_amount || 0),
      deduction_amount: Number(withdrawForm.deduction_amount || 0),
      notes: withdrawForm.notes.trim() || null,
      invoice_actions,
      ...(refundAmount > 0
        ? {
            refund: {
              amount: refundAmount,
              refund_date: withdrawForm.settlement_date,
              refund_method: withdrawForm.refund_method || null,
              reference_number: withdrawForm.reference_number.trim() || null,
              proof_text: withdrawForm.proof_text.trim() || null,
              reason: withdrawForm.refund_reason.trim() || withdrawForm.reason.trim(),
              notes: withdrawForm.refund_notes.trim() || null,
              allocation_reversals: buildWithdrawManualAllocationReversals(),
            },
          }
        : {}),
    }
  }

  const previewWithdrawSettlement = async () => {
    if (!validateWithdrawForm('preview')) return
    setError(null)
    setSuccessMessage(null)
    withdrawalPreviewMutation.reset()
    const result = await withdrawalPreviewMutation.execute(() =>
      api.post(`/billing-accounts/${resolvedId}/withdrawal-settlements/preview`, buildWithdrawPayload())
    )
    if (result != null) {
      setWithdrawPreview(result)
    } else if (withdrawalPreviewMutation.error) {
      setError(withdrawalPreviewMutation.error)
    }
  }

  const submitWithdrawSettlement = async () => {
    if (!validateWithdrawForm('submit')) return
    setError(null)
    setSuccessMessage(null)
    withdrawalMutation.reset()
    const result = await withdrawalMutation.execute(() =>
      api.post(`/billing-accounts/${resolvedId}/withdrawal-settlements`, buildWithdrawPayload())
    )
    if (result != null) {
      setWithdrawDialogOpen(false)
      setWithdrawPreview(null)
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      refundsApi.refetch()
      withdrawalSettlementsApi.refetch()
      if (statement) await loadStatement()
      setSuccessMessage('Family withdrawal settlement posted.')
    } else if (withdrawalMutation.error) {
      setError(withdrawalMutation.error)
    }
  }

  const validateAccountRefundForm = (mode: 'preview' | 'submit' = 'submit') => {
    const nextErrors: Record<string, string> = {}
    const amount = Number(refundForm.amount)
    if (!Number.isFinite(amount) || amount <= 0) {
      nextErrors.amount = 'Amount must be greater than zero.'
    }
    if (!refundForm.refund_date) {
      nextErrors.refund_date = 'Refund date is required.'
    }
    if (mode === 'submit' && (!refundForm.reason.trim() || refundForm.reason.trim().length < 3)) {
      nextErrors.reason = 'Reason must be at least 3 characters.'
    }
    const hasRefundProof =
      Boolean(refundForm.reference_number.trim()) ||
      Boolean(refundForm.proof_text.trim()) ||
      refundForm.proof_attachment_id != null
    if (mode === 'submit' && !hasRefundProof) {
      nextErrors.proof = 'Reference, proof text or confirmation file is required.'
    }
    if (refundAllocationMode === 'manual' && Number.isFinite(amount) && amount > 0) {
      const amountToReopen = getRefundAmountToReopen()
      const selectedTotal = getManualReversalTotal()
      const selectedTotalCents = Math.round(selectedTotal * 100)
      const amountToReopenCents = Math.round(amountToReopen * 100)
      const optionsById = new Map(
        (refundAllocationOptionsApi.data ?? []).map((option) => [option.allocation_id, option])
      )
      const hasInvalidAmount = buildManualAllocationReversals().some((item) => {
        const option = optionsById.get(item.allocation_id)
        return !option || Math.round(item.amount * 100) > Math.round(option.current_allocation_amount * 100)
      })
      if (hasInvalidAmount) {
        nextErrors.allocation_reversals = 'Selected reversal exceeds the current invoice allocation.'
      } else if (amountToReopenCents > 0 && selectedTotalCents !== amountToReopenCents) {
        nextErrors.allocation_reversals = `Manual reversals must total ${formatMoney(amountToReopen)}.`
      } else if (amountToReopenCents === 0 && selectedTotalCents > 0) {
        nextErrors.allocation_reversals = 'This refund uses free credit only; no invoice allocation should be selected.'
      }
    }
    setAccountRefundValidationErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const buildAccountRefundPayload = () => {
    const payload: Record<string, unknown> = {
      amount: Number(refundForm.amount),
      refund_date: refundForm.refund_date,
      refund_method: refundForm.refund_method || null,
      reference_number: refundForm.reference_number.trim() || null,
      proof_text: refundForm.proof_text.trim() || null,
      proof_attachment_id: refundForm.proof_attachment_id,
      reason: refundForm.reason.trim(),
      notes: refundForm.notes.trim() || null,
    }
    if (refundAllocationMode === 'manual' && getRefundAmountToReopen() > 0) {
      payload.allocation_reversals = buildManualAllocationReversals()
    }
    return payload
  }

  const previewAccountRefund = async () => {
    if (!validateAccountRefundForm('preview')) return
    setError(null)
    setSuccessMessage(null)
    accountRefundPreviewMutation.reset()
    const result = await accountRefundPreviewMutation.execute(() =>
      api.post(`/billing-accounts/${resolvedId}/refunds/preview`, {
        amount: Number(refundForm.amount),
        refund_date: refundForm.refund_date,
        ...(refundAllocationMode === 'manual' && getRefundAmountToReopen() > 0
          ? { allocation_reversals: buildManualAllocationReversals() }
          : {}),
      })
    )
    if (result != null) {
      setAccountRefundPreview(result)
    } else if (accountRefundPreviewMutation.error) {
      setError(accountRefundPreviewMutation.error)
    }
  }

  const submitAccountRefund = async () => {
    if (!validateAccountRefundForm()) return
    setError(null)
    setSuccessMessage(null)
    accountRefundMutation.reset()
    const result = await accountRefundMutation.execute(() =>
      api.post(`/billing-accounts/${resolvedId}/refunds`, buildAccountRefundPayload())
    )
    if (result != null) {
      setAccountRefundDialogOpen(false)
      setAccountRefundPreview(null)
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      refundsApi.refetch()
      if (statement) await loadStatement()
      setSuccessMessage('Billing account refund created.')
    } else if (accountRefundMutation.error) {
      setError(accountRefundMutation.error)
    }
  }

  const uploadRefundProofFile = useCallback(async (file: File) => {
    setUploadingRefundProof(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setRefundForm((current) => ({
        ...current,
        proof_attachment_id: response.data.data.id,
        proof_file_name: file.name,
      }))
      setRefundValidationError(null)
      setAccountRefundValidationErrors((current) => {
        const { proof, ...rest } = current
        void proof
        return rest
      })
    } catch {
      setRefundForm((current) => ({
        ...current,
        proof_attachment_id: null,
        proof_file_name: null,
      }))
      setRefundValidationError('Failed to upload refund proof file.')
      setAccountRefundValidationErrors((current) => ({
        ...current,
        proof: 'Failed to upload refund proof file.',
      }))
    } finally {
      setUploadingRefundProof(false)
    }
  }, [])

  const openManualAllocation = () => {
    invoicesApi.refetch()
    setAllocationLines([])
    setAllocationForm({ invoice_id: '', invoice_line_id: '', amount: '' })
    setAllocationDialogOpen(true)
  }

  const loadInvoiceLinesForAllocation = async (invoiceId: string) => {
    if (!invoiceId) {
      setAllocationLines([])
      return
    }
    try {
      const response = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${invoiceId}`)
      setAllocationLines(response.data.data.lines)
    } catch {
      setAllocationLines([])
    }
  }

  const submitManualAllocation = async () => {
    setError(null)
    setSuccessMessage(null)
    manualAllocationMutation.reset()
    const result = await manualAllocationMutation.execute(() =>
      api.post('/payments/allocations/manual', {
        billing_account_id: resolvedId,
        invoice_id: Number(allocationForm.invoice_id),
        invoice_line_id: allocationForm.invoice_line_id
          ? Number(allocationForm.invoice_line_id)
          : null,
        amount: Number(allocationForm.amount),
      })
    )
    if (result != null) {
      setAllocationDialogOpen(false)
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      refundsApi.refetch()
      if (statement) await loadStatement()
      setSuccessMessage('Credit allocated.')
    } else if (manualAllocationMutation.error) {
      setError(manualAllocationMutation.error)
    }
  }

  const submitRefund = async () => {
    if (!refundDialogPayment) return
    const hasRefundProof =
      Boolean(refundForm.reference_number.trim()) ||
      Boolean(refundForm.proof_text.trim()) ||
      refundForm.proof_attachment_id != null
    if (!hasRefundProof) {
      setRefundValidationError('Reference, proof text or confirmation file is required.')
      return
    }
    setRefundValidationError(null)
    setError(null)
    setSuccessMessage(null)
    refundPaymentMutation.reset()
    const result = await refundPaymentMutation.execute(() =>
      api.post(`/payments/${refundDialogPayment.id}/refunds`, {
        amount: Number(refundForm.amount),
        refund_date: refundForm.refund_date,
        refund_method: refundForm.refund_method || null,
        reference_number: refundForm.reference_number.trim() || null,
        proof_text: refundForm.proof_text.trim() || null,
        proof_attachment_id: refundForm.proof_attachment_id,
        reason: refundForm.reason.trim(),
        notes: refundForm.notes.trim() || null,
      })
    )
    if (result != null) {
      setRefundDialogPayment(null)
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      if (statement) await loadStatement()
      setSuccessMessage('Payment refunded.')
    } else if (refundPaymentMutation.error) {
      setError(refundPaymentMutation.error)
    }
  }

  const submitMembers = async () => {
    setError(null)
    addMembersMutation.reset()
    const result = await addMembersMutation.execute(() =>
      api.post(`/billing-accounts/${resolvedId}/members`, { student_ids: selectedStudentIds })
    )
    if (result) {
      setAddDialogOpen(false)
      setSelectedStudentIds([])
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
    } else if (addMembersMutation.error) {
      setError(addMembersMutation.error)
    }
  }

  const submitChild = async () => {
    const nextErrors = validateBillingChildDraft(childDraft, {
      guardian_name: account?.primary_guardian_name ?? '',
      guardian_phone: account?.primary_guardian_phone ?? '',
      guardian_email: account?.primary_guardian_email ?? '',
    })
    setChildErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      setError('Fix the highlighted child details before saving.')
      return
    }

    setError(null)
    addChildMutation.reset()
    const result = await addChildMutation.execute(() =>
      api.post(`/billing-accounts/${resolvedId}/children`, buildBillingChildPayload(childDraft))
    )
    if (result) {
      setAddChildDialogOpen(false)
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      setSuccessMessage('Child added to the billing account.')
    } else if (addChildMutation.error) {
      setError(addChildMutation.error)
    }
  }

  const loadStatement = async () => {
    statementMutation.reset()
    const result = await statementMutation.execute(() =>
      api.get(`/billing-accounts/${resolvedId}/statement`, {
        params: statementForm,
      })
    )
    if (result) {
      setStatement(result)
    } else if (statementMutation.error) {
      setError(statementMutation.error)
    }
  }

  const autoAllocateCredit = async () => {
    setError(null)
    setSuccessMessage(null)
    autoAllocateMutation.reset()
    const result = await autoAllocateMutation.execute(() =>
      api.post('/payments/allocations/auto', { billing_account_id: resolvedId })
    )
    if (result) {
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      if (statement) await loadStatement()
      setSuccessMessage(
        result.total_allocated > 0
          ? `Allocated ${formatMoney(result.total_allocated)} automatically.`
          : 'No allocatable credit or open invoices found.'
      )
    } else if (autoAllocateMutation.error) {
      setError(autoAllocateMutation.error)
    }
  }

  const undoAllocation = async (allocationId: number, reallocate: boolean) => {
    setError(null)
    setSuccessMessage(null)
    let allocatedAmount = 0
    if (reallocate) {
      autoAllocateMutation.reset()
      const result = await autoAllocateMutation.execute(() =>
        api.post(
          `/payments/allocations/${allocationId}/undo-reallocate`,
          {},
          {
            params: {
              reason: 'Undo allocation before reallocation',
            },
          }
        )
      )
      if (result == null) {
        refetch()
        invoicesApi.refetch()
        paymentsApi.refetch()
        await loadStatement()
        setError(autoAllocateMutation.error ?? 'Failed to reallocate credit.')
        return
      }
      allocatedAmount = result.total_allocated
    } else {
      deleteAllocationMutation.reset()
      const ok = await deleteAllocationMutation.execute(() =>
        api
          .delete(`/payments/allocations/${allocationId}`, {
            params: {
              reason: 'Undo allocation from billing account statement',
            },
          })
          .then(() => ({ data: { data: true } }))
      )
      if (ok == null) {
        setError(deleteAllocationMutation.error ?? 'Failed to undo allocation.')
        return
      }
    }

    refetch()
    invoicesApi.refetch()
    paymentsApi.refetch()
    await loadStatement()
    setSuccessMessage(
      reallocate
        ? `Allocation removed and ${formatMoney(allocatedAmount)} reallocated.`
        : 'Allocation removed. Credit returned to the billing account.'
    )
  }

  if (accountLoading) {
    return <Spinner size="medium" />
  }

  if (!account) {
    return (
      <div>
        <Alert severity="error">{error ?? accountError ?? 'Failed to load billing account.'}</Alert>
      </div>
    )
  }

  const invoices = invoicesApi.data?.items ?? []
  const payments = paymentsApi.data?.items ?? []
  const selectedInvoice = invoiceDetailApi.data
  const displayStudentNumber = account.members[0]?.student_number
  const studentCountLabel = `${account.member_count} student${account.member_count === 1 ? '' : 's'}`
  const activeTermId = activeTermApi.data?.id ?? null
  const activeMembers = account.members.filter((member) => member.status?.toLowerCase() === 'active')
  const openInvoicesForAllocation = invoices.filter((invoice) => {
    const status = invoice.status?.toLowerCase()
    return status !== 'paid' && status !== 'cancelled' && status !== 'void'
  })

  const navigateToSellItem = (studentId: number) => {
    navigate('/billing/invoices/new', {
      state: {
        studentId,
        returnTo: `/billing/families/${account.id}`,
      },
    })
  }

  const openSellItem = () => {
    if (activeMembers.length === 1) {
      navigateToSellItem(activeMembers[0].student_id)
      return
    }
    setSelectedSellStudentId(activeMembers[0]?.student_id ?? '')
    setSellItemDialogOpen(true)
  }

  const generateAccountTermInvoices = async () => {
    if (!activeTermId) {
      setError('No active term found.')
      return
    }
    setError(null)
    setSuccessMessage(null)
    generateTermMutation.reset()
    const result = await generateTermMutation.execute(() =>
      api.post(`/billing-accounts/${account.id}/generate-term-invoices`, {
        term_id: activeTermId,
      })
    )
    if (result != null) {
      refetch()
      invoicesApi.refetch()
      paymentsApi.refetch()
      if (statement) await loadStatement()
      const created = result.school_fee_invoices_created + result.transport_invoices_created
      const studentLabel = `active student${result.total_students_processed === 1 ? '' : 's'}`
      setSuccessMessage(
        created > 0
          ? `Generated ${created} term invoice${created === 1 ? '' : 's'} for ${result.total_students_processed} ${studentLabel}.`
          : 'No missing term invoices to generate.'
      )
    } else if (generateTermMutation.error) {
      setError(generateTermMutation.error)
    }
  }

  return (
    <div className="space-y-6">
      <Button variant="outlined" onClick={() => navigate(-1)}>
        Back
      </Button>

      {(
        error ||
        accountError ||
        invoicesApi.error ||
        paymentsApi.error ||
        refundsApi.error ||
        withdrawalSettlementsApi.error ||
        studentsApi.error ||
        activeTermApi.error ||
        referencedError ||
        invoiceDetailApi.error
      ) && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error ??
            accountError ??
            invoicesApi.error ??
            paymentsApi.error ??
            refundsApi.error ??
            withdrawalSettlementsApi.error ??
            studentsApi.error ??
            activeTermApi.error ??
            referencedError ??
            invoiceDetailApi.error}
        </Alert>
      )}
      {successMessage && (
        <Alert severity="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      <div className="flex justify-between gap-4 flex-wrap">
        <div>
          <Typography variant="h4">{account.display_name}</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {displayStudentNumber
              ? `Student #${formatStudentNumberShort(displayStudentNumber)}`
              : 'No linked students'}
            {` · ${studentCountLabel}`}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {account.primary_guardian_name ?? 'No contact'}
            {account.primary_guardian_phone ? ` · ${account.primary_guardian_phone}` : ''}
            {account.primary_guardian_email ? ` · ${account.primary_guardian_email}` : ''}
          </Typography>
        </div>
        <div className="flex gap-2 flex-wrap">
          {canManage && (
            <>
              {canInvoiceTerm(user) && (
                <Button
                  variant="outlined"
                  onClick={generateAccountTermInvoices}
                  disabled={
                    !activeTermId ||
                    activeMembers.length === 0 ||
                    generateTermMutation.loading
                  }
                >
                  {generateTermMutation.loading ? <Spinner size="small" /> : 'Invoice term'}
                </Button>
              )}
              <Button
                variant="outlined"
                onClick={openSellItem}
                disabled={activeMembers.length === 0}
              >
                Sell item
              </Button>
              <Button
                variant="outlined"
                onClick={() =>
                  navigate('/payments/new', {
                    state: {
                      billingAccountId: account.id,
                      billingAccountName: account.display_name,
                    },
                  })
                }
              >
                Record payment
              </Button>
              <Button
                variant="outlined"
                onClick={autoAllocateCredit}
                disabled={autoAllocateMutation.loading}
              >
                {autoAllocateMutation.loading ? <Spinner size="small" /> : 'Auto-allocate credit'}
              </Button>
              {canRefund && (
                <Button
                  variant="outlined"
                  color="error"
                  onClick={openAccountRefundDialog}
                  disabled={accountRefundMutation.loading}
                >
                  Refund account credit
                </Button>
              )}
              <Button
                variant="outlined"
                color="error"
                onClick={openWithdrawDialog}
                disabled={activeMembers.length === 0 || withdrawalMutation.loading}
              >
                Withdraw family
              </Button>
              <Button
                variant="outlined"
                onClick={openManualAllocation}
                disabled={manualAllocationMutation.loading}
              >
                Allocate credit
              </Button>
              <Button variant="outlined" onClick={() => navigate(`/billing/families/${account.id}/edit`)}>
                Edit
              </Button>
              <Button variant="outlined" onClick={openAddChildDialog}>
                Add child
              </Button>
              <Button variant="contained" onClick={() => setAddDialogOpen(true)}>
                Link existing students
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <Typography variant="body2" color="secondary">Credit</Typography>
          <Typography variant="h6" className="mt-1">{formatMoney(account.available_balance)}</Typography>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <Typography variant="body2" color="secondary">Outstanding debt</Typography>
          <Typography variant="h6" className="mt-1">{formatMoney(account.outstanding_debt)}</Typography>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <Typography variant="body2" color="secondary">Net balance</Typography>
          <Typography variant="h6" className="mt-1">{formatMoney(account.balance)}</Typography>
        </div>
      </div>

      {account.notes && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <Typography variant="body2" color="secondary">Notes</Typography>
          <Typography variant="body2" className="mt-2">{account.notes}</Typography>
        </div>
      )}

      {(withdrawalSettlementsApi.data ?? []).length > 0 && (
        <section>
          <Typography variant="h6" className="mb-3">Withdrawal settlements</Typography>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Date</TableHeaderCell>
                  <TableHeaderCell>Settlement #</TableHeaderCell>
                  <TableHeaderCell>Students</TableHeaderCell>
                  <TableHeaderCell align="right">Refund</TableHeaderCell>
                  <TableHeaderCell align="right">Write-off</TableHeaderCell>
                  <TableHeaderCell align="right">Cancelled</TableHeaderCell>
                  <TableHeaderCell align="right">Remaining debt</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(withdrawalSettlementsApi.data ?? []).map((settlement) => (
                  <TableRow key={settlement.id}>
                    <TableCell>{formatDate(settlement.settlement_date)}</TableCell>
                    <TableCell>{settlement.settlement_number}</TableCell>
                    <TableCell>
                      {settlement.students.length
                        ? settlement.students.map((student) => student.student_name ?? `Student #${student.student_id}`).join(', ')
                        : '—'}
                    </TableCell>
                    <TableCell align="right">{formatMoney(settlement.refund_amount)}</TableCell>
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

      <section>
        <Typography variant="h6" className="mb-3">Students</Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Student</TableHeaderCell>
                <TableHeaderCell>Grade</TableHeaderCell>
                <TableHeaderCell>Guardian</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {account.members.map((member) => (
                <TableRow key={member.student_id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span>{member.student_name}</span>
                      <span className="text-xs text-slate-500">#{formatStudentNumberShort(member.student_number)}</span>
                    </div>
                  </TableCell>
                  <TableCell>{member.grade_name ?? '—'}</TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span>{member.guardian_name}</span>
                      <span className="text-xs text-slate-500">{member.guardian_phone}</span>
                    </div>
                  </TableCell>
                  <TableCell>{member.status}</TableCell>
                  <TableCell align="right">
                    <Button size="small" variant="outlined" onClick={() => navigate(`/students/${member.student_id}`)}>
                      View student
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      <section>
        <div className="flex justify-between items-center mb-3 flex-wrap gap-3">
          <Typography variant="h6">Invoices</Typography>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Invoice</TableHeaderCell>
                <TableHeaderCell>Student</TableHeaderCell>
                <TableHeaderCell>Type</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Due</TableHeaderCell>
                <TableHeaderCell>Due date</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoices.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell>
                    <button
                      type="button"
                      className="font-mono text-sm text-indigo-700 hover:underline"
                      onClick={() => setSelectedInvoiceId(invoice.id)}
                    >
                      {invoice.invoice_number}
                    </button>
                  </TableCell>
                  <TableCell>{invoice.student_name ?? '—'}</TableCell>
                  <TableCell>{invoice.invoice_type}</TableCell>
                  <TableCell>{invoice.status}</TableCell>
                  <TableCell align="right">{formatMoney(invoice.amount_due)}</TableCell>
                  <TableCell>{invoice.due_date ? formatDate(invoice.due_date) : '—'}</TableCell>
                  <TableCell align="right">
                    <div className="flex gap-2 justify-end">
                      <Button size="small" variant="outlined" onClick={() => setSelectedInvoiceId(invoice.id)}>
                        View
                      </Button>
                      {canManage && invoice.amount_due > 0 && (
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() =>
                            navigate('/payments/new', {
                              state: {
                                billingAccountId: account.id,
                                billingAccountName: account.display_name,
                                preferredInvoiceId: invoice.id,
                              },
                            })
                          }
                        >
                          Pay
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {invoicesApi.loading && (
                <TableRow>
                  <td colSpan={7} className="px-4 py-8 text-center">
                    <Spinner size="medium" />
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      <section>
        <div className="flex justify-between items-center mb-3 flex-wrap gap-3">
          <Typography variant="h6">Refunds</Typography>
          {canRefund && (
            <Button size="small" variant="outlined" color="error" onClick={openAccountRefundDialog}>
              Refund account credit
            </Button>
          )}
        </div>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Refund #</TableHeaderCell>
                <TableHeaderCell>Method</TableHeaderCell>
                <TableHeaderCell>Reference</TableHeaderCell>
                <TableHeaderCell>Sources</TableHeaderCell>
                <TableHeaderCell>Allocation impact</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(refundsApi.data ?? []).map((refund) => (
                <TableRow key={refund.id}>
                  <TableCell>{formatDate(refund.refund_date)}</TableCell>
                  <TableCell>{refund.refund_number ?? `Refund #${refund.id}`}</TableCell>
                  <TableCell>{refund.refund_method ?? '—'}</TableCell>
                  <TableCell>{refund.reference_number ?? '—'}</TableCell>
                  <TableCell>
                    {refund.payment_sources.length
                      ? refund.payment_sources
                          .map((source) => `${source.payment_number ?? `Payment #${source.payment_id}`}: ${formatMoney(source.amount)}`)
                          .join(', ')
                      : '—'}
                  </TableCell>
                  <TableCell>
                    {refund.allocation_reversals.length
                      ? refund.allocation_reversals
                          .map((impact) =>
                            `${getAllocationInvoiceLabel(impact)} (${impact.student_name ?? `Student #${impact.student_id}`}): ${formatMoney(impact.reversal_amount)}`
                          )
                          .join(', ')
                      : 'No invoice reopened'}
                  </TableCell>
                  <TableCell align="right">{formatMoney(refund.amount)}</TableCell>
                </TableRow>
              ))}
              {refundsApi.loading && (
                <TableRow>
                  <td colSpan={7} className="px-4 py-8 text-center">
                    <Spinner size="medium" />
                  </td>
                </TableRow>
              )}
              {!refundsApi.loading && !(refundsApi.data ?? []).length && (
                <TableRow>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No refunds recorded
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      <section>
        <Typography variant="h6" className="mb-3">Payments</Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Payment #</TableHeaderCell>
                <TableHeaderCell>Student</TableHeaderCell>
                <TableHeaderCell>Reference</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
                {canRefund && <TableHeaderCell align="right">Actions</TableHeaderCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {payments.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell>{formatDate(payment.payment_date)}</TableCell>
                  <TableCell>{payment.payment_number}</TableCell>
                  <TableCell>{payment.student_name ?? '—'}</TableCell>
                  <TableCell>{payment.reference ?? '—'}</TableCell>
                  <TableCell>{getPaymentStatusLabel(payment)}</TableCell>
                  <TableCell align="right">{formatMoney(payment.amount)}</TableCell>
                  {canRefund && (
                    <TableCell align="right">
                      {payment.status === 'completed' && getRefundableAmount(payment) > 0 ? (
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          onClick={() => openRefundDialog(payment)}
                        >
                          Refund
                        </Button>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {paymentsApi.loading && (
                <TableRow>
                  <td colSpan={canRefund ? 7 : 6} className="px-4 py-8 text-center">
                    <Spinner size="medium" />
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      <section className="space-y-4">
        <Typography variant="h6">Statement</Typography>
        <div className="flex gap-4 flex-wrap">
          <Input
            label="From"
            type="date"
            value={statementForm.date_from}
            onChange={(event) =>
              setStatementForm((current) => ({ ...current, date_from: event.target.value }))
            }
            className="w-48"
          />
          <Input
            label="To"
            type="date"
            value={statementForm.date_to}
            onChange={(event) =>
              setStatementForm((current) => ({ ...current, date_to: event.target.value }))
            }
            className="w-48"
          />
          <Button variant="contained" onClick={loadStatement} disabled={statementMutation.loading}>
            {statementMutation.loading ? <Spinner size="small" /> : 'Load statement'}
          </Button>
        </div>
        {statement && (
          <>
            <div className="flex gap-6 flex-wrap">
              <Typography variant="body2">Opening: {formatMoney(statement.opening_balance)}</Typography>
              <Typography variant="body2">Closing: {formatMoney(statement.closing_balance)}</Typography>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Date</TableHeaderCell>
                    <TableHeaderCell>Description</TableHeaderCell>
                    <TableHeaderCell>Reference</TableHeaderCell>
                    <TableHeaderCell align="right">Credit</TableHeaderCell>
                    <TableHeaderCell align="right">Debit</TableHeaderCell>
                    <TableHeaderCell align="right">Balance</TableHeaderCell>
                    {canManage && <TableHeaderCell align="right">Actions</TableHeaderCell>}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {statement.entries.map((entry, index) => (
                    <TableRow key={`${entry.entry_type}-${entry.payment_id ?? entry.allocation_id ?? index}`}>
                      <TableCell>{formatDateTime(entry.date)}</TableCell>
                      <TableCell>{entry.description}</TableCell>
                      <TableCell>{entry.reference ?? '—'}</TableCell>
                      <TableCell align="right">{entry.credit ? formatMoney(entry.credit) : '—'}</TableCell>
                      <TableCell align="right">{entry.debit ? formatMoney(entry.debit) : '—'}</TableCell>
                      <TableCell align="right">{formatMoney(entry.balance)}</TableCell>
                      {canManage && (
                        <TableCell align="right">
                          {entry.allocation_id ? (
                            <div className="flex gap-2 justify-end">
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={deleteAllocationMutation.loading || autoAllocateMutation.loading}
                                onClick={() => undoAllocation(Number(entry.allocation_id), false)}
                              >
                                Undo
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={deleteAllocationMutation.loading || autoAllocateMutation.loading}
                                onClick={() => undoAllocation(Number(entry.allocation_id), true)}
                              >
                                Undo + reallocate
                              </Button>
                            </div>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </section>

      <Dialog open={withdrawDialogOpen} onClose={() => setWithdrawDialogOpen(false)} maxWidth="xl" fullWidth>
        <DialogCloseButton onClose={() => setWithdrawDialogOpen(false)} />
        <DialogTitle>Withdraw family</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            {(withdrawValidationErrors.students ||
              withdrawValidationErrors.invoice_actions ||
              withdrawValidationErrors.refund_allocations ||
              withdrawValidationErrors.refund_proof ||
              withdrawalPreviewMutation.error ||
              withdrawalMutation.error) && (
              <Alert severity="error">
                {withdrawValidationErrors.students ||
                  withdrawValidationErrors.invoice_actions ||
                  withdrawValidationErrors.refund_allocations ||
                  withdrawValidationErrors.refund_proof ||
                  withdrawalPreviewMutation.error ||
                  withdrawalMutation.error}
              </Alert>
            )}

            <div className="grid gap-3 md:grid-cols-4">
              <Input
                label="Settlement date"
                type="date"
                value={withdrawForm.settlement_date}
                error={withdrawValidationErrors.settlement_date}
                onChange={(event) => {
                  setWithdrawPreview(null)
                  setWithdrawValidationErrors((current) => ({ ...current, settlement_date: '' }))
                  setWithdrawForm((current) => ({ ...current, settlement_date: event.target.value }))
                }}
              />
              <Input
                label="Retained amount"
                type="number"
                value={withdrawForm.retained_amount}
                onChange={(event) => {
                  setWithdrawPreview(null)
                  setWithdrawForm((current) => ({ ...current, retained_amount: event.target.value }))
                }}
              />
              <Input
                label="Deduction amount"
                type="number"
                value={withdrawForm.deduction_amount}
                onChange={(event) => {
                  setWithdrawPreview(null)
                  setWithdrawForm((current) => ({ ...current, deduction_amount: event.target.value }))
                }}
              />
              <Input
                label="Refund amount"
                type="number"
                value={withdrawForm.refund_amount}
                error={withdrawValidationErrors.refund_amount}
                onChange={(event) => {
                  setWithdrawPreview(null)
                  setWithdrawValidationErrors((current) => ({ ...current, refund_amount: '', refund_allocations: '' }))
                  setWithdrawForm((current) => ({ ...current, refund_amount: event.target.value }))
                }}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Textarea
                label="Reason"
                value={withdrawForm.reason}
                error={withdrawValidationErrors.reason}
                rows={3}
                onChange={(event) => {
                  setWithdrawValidationErrors((current) => ({ ...current, reason: '' }))
                  setWithdrawForm((current) => ({ ...current, reason: event.target.value }))
                }}
              />
              <Textarea
                label="Notes"
                value={withdrawForm.notes}
                rows={3}
                onChange={(event) => setWithdrawForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </div>

            <div className="rounded-lg border border-slate-200 p-4 space-y-3">
              <Typography variant="body2" className="font-semibold">Students</Typography>
              <div className="grid gap-2 md:grid-cols-2">
                {activeMembers.map((member) => (
                  <label key={member.student_id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={withdrawStudentIds.includes(member.student_id)}
                      onChange={() => {
                        setWithdrawPreview(null)
                        setWithdrawValidationErrors((current) => ({ ...current, students: '' }))
                        setWithdrawStudentIds((current) =>
                          current.includes(member.student_id)
                            ? current.filter((id) => id !== member.student_id)
                            : [...current, member.student_id]
                        )
                      }}
                    />
                    <span>{member.student_name} · #{formatStudentNumberShort(member.student_number)}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <Typography variant="body2" className="font-semibold">Invoice actions</Typography>
              <div className="overflow-hidden rounded-lg border border-slate-200">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Invoice</TableHeaderCell>
                      <TableHeaderCell>Student</TableHeaderCell>
                      <TableHeaderCell>Status</TableHeaderCell>
                      <TableHeaderCell align="right">Paid</TableHeaderCell>
                      <TableHeaderCell align="right">Due</TableHeaderCell>
                      <TableHeaderCell align="right">Refund reopening</TableHeaderCell>
                      <TableHeaderCell align="right">Amount to close</TableHeaderCell>
                      <TableHeaderCell>Action</TableHeaderCell>
                      <TableHeaderCell align="right">Amount</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {selectedWithdrawInvoiceRows().map((invoice) => {
                      const action = withdrawInvoiceActions[invoice.id] ?? {
                        action: 'none' as const,
                        amount: String(invoice.amount_due),
                        notes: '',
                      }
                      const refundReopening = getWithdrawRefundReopenByInvoice()[invoice.id] ?? 0
                      const amountToClose = getWithdrawInvoiceAmountToClose(invoice)
                      return (
                        <TableRow key={invoice.id}>
                          <TableCell>
                            <div className="font-medium">{invoice.invoice_number}</div>
                            <div className="text-xs text-slate-500">
                              {formatInvoiceTypeLabel(invoice.invoice_type)}
                              {invoice.due_date ? ` · due ${formatDate(invoice.due_date)}` : ''}
                            </div>
                          </TableCell>
                          <TableCell>{invoice.student_name ?? `Student #${invoice.student_id}`}</TableCell>
                          <TableCell>{formatInvoiceStatusLabel(invoice.status)}</TableCell>
                          <TableCell align="right">{formatMoney(invoice.paid_total)}</TableCell>
                          <TableCell align="right">{formatMoney(invoice.amount_due)}</TableCell>
                          <TableCell align="right">{refundReopening > 0 ? formatMoney(refundReopening) : '—'}</TableCell>
                          <TableCell align="right">{formatMoney(amountToClose)}</TableCell>
                          <TableCell>
                            <Select
                              value={action.action}
                              onChange={(event) => {
                                setWithdrawPreview(null)
                                setWithdrawInvoiceActions((current) => ({
                                  ...current,
                                  [invoice.id]: {
                                    ...action,
                                    action: event.target.value as 'none' | 'cancel_unpaid' | 'write_off' | 'keep_charged',
                                    amount:
                                      event.target.value === 'write_off'
                                        ? String(amountToClose)
                                        : event.target.value === 'cancel_unpaid'
                                          ? String(invoice.amount_due)
                                          : action.amount || String(amountToClose),
                                  },
                                }))
                              }}
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
                              containerClassName="min-w-32"
                              onChange={(event) => {
                                setWithdrawPreview(null)
                                setWithdrawInvoiceActions((current) => ({
                                  ...current,
                                  [invoice.id]: { ...action, amount: event.target.value },
                                }))
                              }}
                            />
                          </TableCell>
                        </TableRow>
                      )
                    })}
                    {!selectedWithdrawInvoiceRows().length && (
                      <TableRow>
                        <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                          No invoices for selected students.
                        </td>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>

            {getWithdrawRefundAmount() > 0 && (
              <div className="rounded-lg border border-slate-200 p-4 space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <Select
                    label="Refund method"
                    value={withdrawForm.refund_method}
                    onChange={(event) => setWithdrawForm((current) => ({ ...current, refund_method: event.target.value }))}
                  >
                    <option value="mpesa">M-Pesa</option>
                    <option value="bank_transfer">Bank Transfer</option>
                    <option value="cash">Cash</option>
                    <option value="other">Other</option>
                  </Select>
                  <Input
                    label="Reference number"
                    value={withdrawForm.reference_number}
                    onChange={(event) => {
                      setWithdrawValidationErrors((current) => ({ ...current, refund_proof: '' }))
                      setWithdrawForm((current) => ({ ...current, reference_number: event.target.value }))
                    }}
                  />
                  <Input
                    label="Refund reason"
                    value={withdrawForm.refund_reason}
                    onChange={(event) => setWithdrawForm((current) => ({ ...current, refund_reason: event.target.value }))}
                  />
                </div>
                <Textarea
                  label="Refund proof"
                  value={withdrawForm.proof_text}
                  rows={3}
                  onChange={(event) => {
                    setWithdrawValidationErrors((current) => ({ ...current, refund_proof: '' }))
                    setWithdrawForm((current) => ({ ...current, proof_text: event.target.value }))
                  }}
                  helperText="Reference or proof text is required before posting a refund"
                />

                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Typography variant="body2" className="font-semibold">
                      Refund allocation reversals
                    </Typography>
                    <Typography variant="body2" color="secondary">
                      Amount to reopen: {formatMoney(getWithdrawRefundAmountToReopen())} · Selected: {formatMoney(getWithdrawManualReversalTotal())}
                    </Typography>
                  </div>
                  <div className="overflow-hidden rounded-lg border border-slate-200">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Invoice</TableHeaderCell>
                          <TableHeaderCell>Student</TableHeaderCell>
                          <TableHeaderCell align="right">Allocated</TableHeaderCell>
                          <TableHeaderCell align="right">Reverse</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {(refundAllocationOptionsApi.data ?? [])
                          .filter((option) => withdrawStudentIds.includes(option.student_id))
                          .map((option) => (
                            <TableRow key={option.allocation_id}>
                              <TableCell>
                                <div className="font-medium">{option.invoice_number}</div>
                                <div className="text-xs text-slate-500">{formatInvoiceTypeLabel(option.invoice_type)}</div>
                              </TableCell>
                              <TableCell>{option.student_name ?? `Student #${option.student_id}`}</TableCell>
                              <TableCell align="right">{formatMoney(option.current_allocation_amount)}</TableCell>
                              <TableCell align="right">
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  value={withdrawManualReversals[option.allocation_id] ?? ''}
                                  containerClassName="min-w-32"
                                  onChange={(event) => {
                                    const nextValue = event.target.value
                                    setWithdrawPreview(null)
                                    setWithdrawValidationErrors((current) => ({
                                      ...current,
                                      refund_allocations: '',
                                      invoice_actions: '',
                                    }))
                                    setWithdrawManualReversals((current) => {
                                      const next = {
                                        ...current,
                                        [option.allocation_id]: nextValue,
                                      }
                                      const reopenByInvoice = getWithdrawRefundReopenByInvoice(next)
                                      const invoice = invoices.find((item) => item.id === option.invoice_id)
                                      if (invoice) {
                                        const amountToClose = getWithdrawInvoiceAmountToClose(invoice, reopenByInvoice)
                                        setWithdrawInvoiceActions((currentActions) => {
                                          const currentAction = currentActions[invoice.id] ?? {
                                            action: 'none' as const,
                                            amount: '0',
                                            notes: '',
                                          }
                                          return {
                                            ...currentActions,
                                            [invoice.id]: {
                                              ...currentAction,
                                              action: 'write_off',
                                              amount: String(amountToClose),
                                            },
                                          }
                                        })
                                      }
                                      return next
                                    })
                                  }}
                                />
                              </TableCell>
                            </TableRow>
                          ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </div>
            )}

            {withdrawPreview && (
              <div className="rounded-lg border border-slate-200 p-4 space-y-4">
                <div className="grid gap-3 md:grid-cols-4">
                  <div>
                    <Typography variant="body2" color="secondary">Current debt</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.current_outstanding_debt)}</Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Refund</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.refund_amount)}</Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Write-off / cancel</Typography>
                    <Typography variant="body2" className="font-semibold">
                      {formatMoney(withdrawPreview.write_off_amount)} / {formatMoney(withdrawPreview.cancelled_amount)}
                    </Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Remaining debt</Typography>
                    <Typography variant="body2" className="font-semibold">{formatMoney(withdrawPreview.remaining_collectible_debt_after)}</Typography>
                  </div>
                </div>
                {withdrawPreview.warnings.length > 0 && (
                  <Alert severity="warning">{withdrawPreview.warnings.join(' ')}</Alert>
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
            onClick={previewWithdrawSettlement}
            disabled={withdrawalPreviewMutation.loading || withdrawalMutation.loading}
          >
            {withdrawalPreviewMutation.loading ? <Spinner size="small" /> : 'Preview'}
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={submitWithdrawSettlement}
            disabled={withdrawalMutation.loading}
          >
            {withdrawalMutation.loading ? <Spinner size="small" /> : 'Post settlement'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={accountRefundDialogOpen} onClose={() => setAccountRefundDialogOpen(false)} maxWidth="lg" fullWidth>
        <DialogCloseButton onClose={() => setAccountRefundDialogOpen(false)} />
        <DialogTitle>Refund account credit</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            {(accountRefundValidationErrors.proof ||
              accountRefundValidationErrors.allocation_reversals ||
              refundAllocationOptionsApi.error ||
              accountRefundPreviewMutation.error ||
              accountRefundMutation.error) && (
              <Alert severity="error">
                {accountRefundValidationErrors.proof ||
                  accountRefundValidationErrors.allocation_reversals ||
                  refundAllocationOptionsApi.error ||
                  accountRefundPreviewMutation.error ||
                  accountRefundMutation.error}
              </Alert>
            )}
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Available credit</Typography>
                <Typography variant="body2" className="font-semibold">{formatMoney(account.available_balance)}</Typography>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Outstanding debt</Typography>
                <Typography variant="body2" className="font-semibold">{formatMoney(account.outstanding_debt)}</Typography>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <Typography variant="body2" color="secondary">Refundable after preview</Typography>
                <Typography variant="body2" className="font-semibold">
                  {accountRefundPreview ? formatMoney(accountRefundPreview.refundable_total) : '—'}
                </Typography>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Amount"
                type="number"
                value={refundForm.amount}
                error={accountRefundValidationErrors.amount}
                onChange={(event) => {
                  setAccountRefundPreview(null)
                  setAccountRefundValidationErrors((current) => ({
                    ...current,
                    amount: '',
                    allocation_reversals: '',
                  }))
                  setRefundForm((current) => ({ ...current, amount: event.target.value }))
                }}
              />
              <Input
                label="Refund date"
                type="date"
                value={refundForm.refund_date}
                error={accountRefundValidationErrors.refund_date}
                onChange={(event) => {
                  setAccountRefundPreview(null)
                  setAccountRefundValidationErrors((current) => ({ ...current, refund_date: '' }))
                  setRefundForm((current) => ({ ...current, refund_date: event.target.value }))
                }}
              />
              <Select
                label="Refund method"
                value={refundForm.refund_method}
                onChange={(event) =>
                  setRefundForm((current) => ({ ...current, refund_method: event.target.value }))
                }
              >
                <option value="mpesa">M-Pesa</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cash">Cash</option>
                <option value="other">Other</option>
              </Select>
              <Input
                label="Reference number"
                value={refundForm.reference_number}
                onChange={(event) => {
                  setAccountRefundValidationErrors((current) => ({ ...current, proof: '' }))
                  setRefundForm((current) => ({ ...current, reference_number: event.target.value }))
                }}
              />
            </div>
            <Textarea
              label="Reference / proof"
              value={refundForm.proof_text}
              onChange={(event) => {
                setAccountRefundValidationErrors((current) => ({ ...current, proof: '' }))
                setRefundForm((current) => ({ ...current, proof_text: event.target.value }))
              }}
              rows={3}
              helperText="Reference, proof text or confirmation file is required"
            />
            <FileDropzone
              title="Upload refund confirmation (image/PDF)"
              accept="image/*,.pdf,application/pdf"
              fileName={refundForm.proof_file_name}
              disabled={uploadingRefundProof}
              loading={uploadingRefundProof}
              onFileSelected={uploadRefundProofFile}
            />
            <Input
              label="Reason"
              value={refundForm.reason}
              error={accountRefundValidationErrors.reason}
              onChange={(event) => {
                setAccountRefundValidationErrors((current) => ({ ...current, reason: '' }))
                setRefundForm((current) => ({ ...current, reason: event.target.value }))
              }}
            />
            <Input
              label="Notes"
              value={refundForm.notes}
              onChange={(event) =>
                setRefundForm((current) => ({ ...current, notes: event.target.value }))
              }
            />

            <div className="space-y-3 rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <Typography variant="body2" className="font-semibold">Invoice allocation impact</Typography>
                  <Typography variant="body2" color="secondary">
                    Amount to reopen: {formatMoney(getRefundAmountToReopen())}
                  </Typography>
                </div>
                <ToggleButtonGroup
                  value={refundAllocationMode}
                  size="small"
                  onChange={(_, value) => {
                    if (value !== 'auto' && value !== 'manual') return
                    setAccountRefundPreview(null)
                    setAccountRefundValidationErrors((current) => ({ ...current, allocation_reversals: '' }))
                    setRefundAllocationMode(value)
                  }}
                >
                  <ToggleButton value="auto">Auto</ToggleButton>
                  <ToggleButton value="manual">Manual</ToggleButton>
                </ToggleButtonGroup>
              </div>

              {refundAllocationMode === 'manual' && (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Typography variant="body2" color="secondary">
                      Selected: {formatMoney(getManualReversalTotal())}
                    </Typography>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => {
                        setAccountRefundPreview(null)
                        setManualRefundReversals({})
                        setAccountRefundValidationErrors((current) => ({ ...current, allocation_reversals: '' }))
                      }}
                    >
                      Clear
                    </Button>
                  </div>
                  {refundAllocationOptionsApi.loading ? (
                    <div className="py-4">
                      <Spinner size="small" />
                    </div>
                  ) : (refundAllocationOptionsApi.data ?? []).length ? (
                    <div className="overflow-hidden rounded-lg border border-slate-200">
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableHeaderCell>Invoice</TableHeaderCell>
                            <TableHeaderCell>Student</TableHeaderCell>
                            <TableHeaderCell>Status</TableHeaderCell>
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
                                  {formatInvoiceTypeLabel(option.invoice_type)}
                                  {option.due_date ? ` · due ${formatDate(option.due_date)}` : ''}
                                </div>
                              </TableCell>
                              <TableCell>{option.student_name ?? `Student #${option.student_id}`}</TableCell>
                              <TableCell>{formatInvoiceStatusLabel(option.invoice_status)}</TableCell>
                              <TableCell align="right">{formatMoney(option.current_allocation_amount)}</TableCell>
                              <TableCell align="right">{formatMoney(option.invoice_amount_due)}</TableCell>
                              <TableCell align="right">
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  value={manualRefundReversals[option.allocation_id] ?? ''}
                                  containerClassName="min-w-32"
                                  aria-label={`Reverse ${option.invoice_number}`}
                                  onChange={(event) => {
                                    setAccountRefundPreview(null)
                                    setAccountRefundValidationErrors((current) => ({
                                      ...current,
                                      allocation_reversals: '',
                                    }))
                                    setManualRefundReversals((current) => ({
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
                  ) : (
                    <Typography variant="body2" color="secondary">No current invoice allocations can be reopened.</Typography>
                  )}
                </div>
              )}
            </div>

            {accountRefundPreview && (
              <div className="space-y-4 rounded-lg border border-slate-200 p-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <div>
                    <Typography variant="body2" color="secondary">Amount to reopen</Typography>
                    <Typography variant="body2" className="font-semibold">
                      {formatMoney(accountRefundPreview.amount_to_reopen)}
                    </Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Free credit used first</Typography>
                    <Typography variant="body2" className="font-semibold">
                      {formatMoney(Math.min(accountRefundPreview.amount, Math.max(accountRefundPreview.available_credit, 0)))}
                    </Typography>
                  </div>
                  <div>
                    <Typography variant="body2" color="secondary">Current allocated credit</Typography>
                    <Typography variant="body2" className="font-semibold">
                      {formatMoney(accountRefundPreview.current_allocated_total)}
                    </Typography>
                  </div>
                </div>
                <div>
                  <Typography variant="body2" className="font-semibold mb-2">Invoice impact</Typography>
                  {accountRefundPreview.allocation_reversals.length ? (
                    <div className="overflow-hidden rounded-lg border border-slate-200">
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableHeaderCell>Invoice</TableHeaderCell>
                            <TableHeaderCell>Student</TableHeaderCell>
                            <TableHeaderCell align="right">Reopen</TableHeaderCell>
                            <TableHeaderCell align="right">Due after</TableHeaderCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {accountRefundPreview.allocation_reversals.map((impact) => (
                            <TableRow key={impact.allocation_id}>
                              <TableCell>
                                <div className="font-medium">{impact.invoice_number}</div>
                                <div className="text-xs text-slate-500">
                                  {formatInvoiceTypeLabel(impact.invoice_type)}
                                  {impact.due_date ? ` · due ${formatDate(impact.due_date)}` : ''}
                                </div>
                              </TableCell>
                              <TableCell>{impact.student_name ?? `Student #${impact.student_id}`}</TableCell>
                              <TableCell align="right">{formatMoney(impact.reversal_amount)}</TableCell>
                              <TableCell align="right">{formatMoney(impact.invoice_amount_due_after)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <Typography variant="body2" color="secondary">No invoice allocations will be reopened.</Typography>
                  )}
                </div>
                <div>
                  <Typography variant="body2" className="font-semibold mb-2">Payment source attribution</Typography>
                  <div className="overflow-hidden rounded-lg border border-slate-200">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Payment</TableHeaderCell>
                          <TableHeaderCell>Date</TableHeaderCell>
                          <TableHeaderCell align="right">Source amount</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {accountRefundPreview.payment_sources.map((source) => (
                          <TableRow key={source.payment_id}>
                            <TableCell>{source.payment_number}</TableCell>
                            <TableCell>{formatDate(source.payment_date)}</TableCell>
                            <TableCell align="right">{formatMoney(source.source_amount)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAccountRefundDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="outlined"
            onClick={previewAccountRefund}
            disabled={accountRefundPreviewMutation.loading || accountRefundMutation.loading || uploadingRefundProof}
          >
            {accountRefundPreviewMutation.loading ? <Spinner size="small" /> : 'Preview impact'}
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={submitAccountRefund}
            disabled={accountRefundMutation.loading || uploadingRefundProof}
          >
            {accountRefundMutation.loading ? <Spinner size="small" /> : 'Create refund'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(refundDialogPayment)} onClose={() => setRefundDialogPayment(null)} maxWidth="sm">
        <DialogCloseButton onClose={() => setRefundDialogPayment(null)} />
        <DialogTitle>Refund payment</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            {(refundValidationError || refundPaymentMutation.error) && (
              <Alert severity="error">
                {refundValidationError || refundPaymentMutation.error}
              </Alert>
            )}
            <Typography variant="body2">
              Payment: {refundDialogPayment?.payment_number ?? '—'}
            </Typography>
            <Typography variant="body2">
              Refundable amount: {formatMoney(getRefundableAmount(refundDialogPayment))}
            </Typography>
            <Input
              label="Amount"
              type="number"
              value={refundForm.amount}
              onChange={(event) =>
                setRefundForm((current) => ({ ...current, amount: event.target.value }))
              }
            />
            <Input
              label="Refund date"
              type="date"
              value={refundForm.refund_date}
              onChange={(event) =>
                setRefundForm((current) => ({ ...current, refund_date: event.target.value }))
              }
            />
            <Select
              label="Refund method"
              value={refundForm.refund_method}
              onChange={(event) =>
                setRefundForm((current) => ({ ...current, refund_method: event.target.value }))
              }
            >
              <option value="mpesa">M-Pesa</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cash">Cash</option>
              <option value="other">Other</option>
            </Select>
            <Input
              label="Reference number"
              value={refundForm.reference_number}
              onChange={(event) => {
                setRefundValidationError(null)
                setRefundForm((current) => ({ ...current, reference_number: event.target.value }))
              }}
            />
            <Textarea
              label="Reference / proof"
              value={refundForm.proof_text}
              onChange={(event) => {
                setRefundValidationError(null)
                setRefundForm((current) => ({ ...current, proof_text: event.target.value }))
              }}
              rows={3}
              helperText="Reference, proof text or confirmation file is required"
            />
            <FileDropzone
              title="Upload refund confirmation (image/PDF)"
              accept="image/*,.pdf,application/pdf"
              fileName={refundForm.proof_file_name}
              disabled={uploadingRefundProof}
              loading={uploadingRefundProof}
              onFileSelected={uploadRefundProofFile}
            />
            <Input
              label="Reason"
              value={refundForm.reason}
              onChange={(event) =>
                setRefundForm((current) => ({ ...current, reason: event.target.value }))
              }
            />
            <Input
              label="Notes"
              value={refundForm.notes}
              onChange={(event) =>
                setRefundForm((current) => ({ ...current, notes: event.target.value }))
              }
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setRefundDialogPayment(null)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={submitRefund}
            disabled={refundPaymentMutation.loading || uploadingRefundProof}
          >
            {refundPaymentMutation.loading ? <Spinner size="small" /> : 'Refund'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(selectedInvoiceId)} onClose={() => setSelectedInvoiceId(null)} maxWidth="lg">
        <DialogCloseButton onClose={() => setSelectedInvoiceId(null)} />
        <DialogTitle>
          Invoice {selectedInvoice?.invoice_number ?? ''}
          {selectedInvoice ? ` · ${selectedInvoice.status}` : invoiceDetailApi.loading ? ' (loading...)' : ''}
        </DialogTitle>
        <DialogContent>
          {invoiceDetailApi.loading ? (
            <div className="py-8 flex justify-center">
              <Spinner size="medium" />
            </div>
          ) : selectedInvoice ? (
            <div className="space-y-4 mt-4">
              <div className="grid gap-3 md:grid-cols-3">
                <div>
                  <Typography variant="body2" color="secondary">Student</Typography>
                  <Typography variant="body2">{selectedInvoice.student_name ?? '—'}</Typography>
                </div>
                <div>
                  <Typography variant="body2" color="secondary">Type</Typography>
                  <Typography variant="body2">{selectedInvoice.invoice_type}</Typography>
                </div>
                <div>
                  <Typography variant="body2" color="secondary">Due date</Typography>
                  <Typography variant="body2">{selectedInvoice.due_date ? formatDate(selectedInvoice.due_date) : '—'}</Typography>
                </div>
                <div>
                  <Typography variant="body2" color="secondary">Total</Typography>
                  <Typography variant="body2">{formatMoney(selectedInvoice.total)}</Typography>
                </div>
                <div>
                  <Typography variant="body2" color="secondary">Paid</Typography>
                  <Typography variant="body2">{formatMoney(selectedInvoice.paid_total)}</Typography>
                </div>
                <div>
                  <Typography variant="body2" color="secondary">Due</Typography>
                  <Typography variant="body2">{formatMoney(selectedInvoice.amount_due)}</Typography>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Description</TableHeaderCell>
                      <TableHeaderCell align="right">Qty</TableHeaderCell>
                      <TableHeaderCell align="right">Line total</TableHeaderCell>
                      <TableHeaderCell align="right">Paid</TableHeaderCell>
                      <TableHeaderCell align="right">Remaining</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {selectedInvoice.lines.map((line) => (
                      <TableRow key={line.id}>
                        <TableCell>{line.description}</TableCell>
                        <TableCell align="right">{line.quantity}</TableCell>
                        <TableCell align="right">{formatMoney(line.line_total)}</TableCell>
                        <TableCell align="right">{formatMoney(line.paid_amount)}</TableCell>
                        <TableCell align="right">{formatMoney(line.remaining_amount)}</TableCell>
                      </TableRow>
                    ))}
                    {!selectedInvoice.lines.length && (
                      <TableRow>
                        <td colSpan={5} className="px-4 py-8 text-center">
                          <Typography color="secondary">No invoice lines.</Typography>
                        </td>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : (
            <Typography color="secondary" className="mt-4">Invoice not found.</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setSelectedInvoiceId(null)}>
            Close
          </Button>
          {selectedInvoice?.student_id && (
            <Button
              variant="outlined"
              onClick={() => navigate(`/students/${selectedInvoice.student_id}?tab=invoices`)}
            >
              Open student invoices
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={sellItemDialogOpen} onClose={() => setSellItemDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setSellItemDialogOpen(false)} />
        <DialogTitle>Sell item</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Typography variant="body2" color="secondary">
              Select which student should receive the item invoice.
            </Typography>
            <Select
              value={selectedSellStudentId === '' ? '' : String(selectedSellStudentId)}
              onChange={(event) =>
                setSelectedSellStudentId(event.target.value ? Number(event.target.value) : '')
              }
              label="Student"
            >
              <option value="">Select student</option>
              {activeMembers.map((member) => (
                <option key={member.student_id} value={String(member.student_id)}>
                  {member.student_name} · #{formatStudentNumberShort(member.student_number)}
                </option>
              ))}
            </Select>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setSellItemDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => {
              if (!selectedSellStudentId) return
              setSellItemDialogOpen(false)
              navigateToSellItem(Number(selectedSellStudentId))
            }}
            disabled={!selectedSellStudentId}
          >
            Continue
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={allocationDialogOpen} onClose={() => setAllocationDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setAllocationDialogOpen(false)} />
        <DialogTitle>Allocate credit</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Select
              value={allocationForm.invoice_id}
              onChange={(event) => {
                const nextInvoice = event.target.value
                setAllocationForm({
                  ...allocationForm,
                  invoice_id: nextInvoice,
                  invoice_line_id: '',
                })
                loadInvoiceLinesForAllocation(nextInvoice)
              }}
              label="Invoice"
            >
              <option value="">Select invoice</option>
              {openInvoicesForAllocation.map((invoice) => (
                <option key={invoice.id} value={String(invoice.id)}>
                  {invoice.invoice_number}
                  {invoice.student_name ? ` · ${invoice.student_name}` : ''}
                  {` · Due ${formatMoney(invoice.amount_due)}`}
                </option>
              ))}
            </Select>
            <Select
              value={allocationForm.invoice_line_id}
              onChange={(event) =>
                setAllocationForm({ ...allocationForm, invoice_line_id: event.target.value })
              }
              label="Invoice line (optional)"
            >
              <option value="">Any line</option>
              {allocationLines.map((line) => (
                <option key={line.id} value={String(line.id)}>
                  {line.description} · {formatMoney(line.remaining_amount)}
                </option>
              ))}
            </Select>
            <Input
              label="Amount"
              type="number"
              value={allocationForm.amount}
              onChange={(event) =>
                setAllocationForm({ ...allocationForm, amount: event.target.value })
              }
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAllocationDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={submitManualAllocation}
            disabled={
              manualAllocationMutation.loading ||
              !allocationForm.invoice_id ||
              !allocationForm.amount
            }
          >
            {manualAllocationMutation.loading ? <Spinner size="small" /> : 'Allocate'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={addChildDialogOpen} onClose={() => setAddChildDialogOpen(false)} maxWidth="lg">
        <DialogCloseButton onClose={() => setAddChildDialogOpen(false)} />
        <DialogTitle>Add child to billing account</DialogTitle>
        <DialogContent>
          <div className="mt-4">
            <BillingAccountChildEditor
              title="New child"
              value={childDraft}
              onChange={(next) => {
                setChildDraft(next)
                setChildErrors({})
              }}
              grades={grades}
              transportZones={transportZones}
              errors={childErrors}
              helperText="Guardian fields can be left blank if they match the billing contact."
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAddChildDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitChild} disabled={addChildMutation.loading}>
            {addChildMutation.loading ? <Spinner size="small" /> : 'Add child'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setAddDialogOpen(false)} />
        <DialogTitle>Link existing students</DialogTitle>
        <DialogContent>
          <div className="space-y-3 mt-4 max-h-[420px] overflow-y-auto">
            {eligibleStudents.map((student) => {
              const disabled =
                (student.billing_account_member_count ?? 0) > 1 &&
                student.billing_account_id !== account.id
              return (
                <div key={student.id} className="flex items-start justify-between gap-4">
                  <Checkbox
                    disabled={disabled}
                    checked={selectedStudentIds.includes(student.id)}
                    onChange={() => toggleStudent(student.id)}
                    label={`${student.full_name} · ${student.student_number}`}
                  />
                  <span className="text-sm text-slate-500">
                    {disabled
                      ? 'Already in another shared account'
                      : student.grade_name ?? 'No grade'}
                  </span>
                </div>
              )
            })}
            {!eligibleStudents.length && (
              <Typography color="secondary">No extra active students available.</Typography>
            )}
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAddDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitMembers} disabled={addMembersMutation.loading}>
            {addMembersMutation.loading ? <Spinner size="small" /> : 'Add students'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
