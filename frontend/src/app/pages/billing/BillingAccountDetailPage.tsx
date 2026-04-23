import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { canInvoiceTerm, canManageBillingAccounts } from '../../utils/permissions'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import { formatStudentNumberShort } from '../../utils/studentNumber'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components/ui/Table'
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
}

interface StatementEntry {
  date: string
  entry_type: string
  description: string
  reference?: string | null
  payment_id?: number | null
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
      if (statement) await loadStatement()
      setSuccessMessage('Credit allocated.')
    } else if (manualAllocationMutation.error) {
      setError(manualAllocationMutation.error)
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
              </TableRow>
            </TableHead>
            <TableBody>
              {payments.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell>{formatDate(payment.payment_date)}</TableCell>
                  <TableCell>{payment.payment_number}</TableCell>
                  <TableCell>{payment.student_name ?? '—'}</TableCell>
                  <TableCell>{payment.reference ?? '—'}</TableCell>
                  <TableCell>{payment.status}</TableCell>
                  <TableCell align="right">{formatMoney(payment.amount)}</TableCell>
                </TableRow>
              ))}
              {paymentsApi.loading && (
                <TableRow>
                  <td colSpan={6} className="px-4 py-8 text-center">
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
