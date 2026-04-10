import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { canManageBillingAccounts } from '../../utils/permissions'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import type { PaginatedResponse } from '../../types/api'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'

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
  account_type: string
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
  billing_account_type?: string | null
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
  description: string
  reference?: string | null
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

export const BillingAccountDetailPage = () => {
  const { accountId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
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

  const addMembersMutation = useApiMutation<BillingAccountDetail>()
  const statementMutation = useApiMutation<StatementResponse>()
  const autoAllocateMutation = useApiMutation<{
    total_allocated: number
    invoices_fully_paid: number
    invoices_partially_paid: number
    remaining_balance: number
  }>()

  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [selectedStudentIds, setSelectedStudentIds] = useState<number[]>([])
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
      setSuccessMessage(
        result.total_allocated > 0
          ? `Allocated ${formatMoney(result.total_allocated)} automatically.`
          : 'No allocatable credit or open invoices found.'
      )
    } else if (autoAllocateMutation.error) {
      setError(autoAllocateMutation.error)
    }
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

  return (
    <div className="space-y-6">
      <Button variant="outlined" onClick={() => navigate(-1)}>
        Back
      </Button>

      {(error || accountError || invoicesApi.error || paymentsApi.error || studentsApi.error) && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error ?? accountError ?? invoicesApi.error ?? paymentsApi.error ?? studentsApi.error}
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
            {account.account_number} · {account.member_count} students
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
              <Button variant="outlined" onClick={() => navigate(`/billing/families/${account.id}/edit`)}>
                Edit
              </Button>
              <Button variant="contained" onClick={() => setAddDialogOpen(true)}>
                Add students
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
                      <span className="text-xs text-slate-500">{member.student_number}</span>
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
                  <TableCell>{invoice.invoice_number}</TableCell>
                  <TableCell>{invoice.student_name ?? '—'}</TableCell>
                  <TableCell>{invoice.invoice_type}</TableCell>
                  <TableCell>{invoice.status}</TableCell>
                  <TableCell align="right">{formatMoney(invoice.amount_due)}</TableCell>
                  <TableCell>{invoice.due_date ? formatDate(invoice.due_date) : '—'}</TableCell>
                  <TableCell align="right">
                    <div className="flex gap-2 justify-end">
                      <Button size="small" variant="outlined" onClick={() => navigate(`/students/${invoice.student_id}?tab=invoices`)}>
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
                  </TableRow>
                </TableHead>
                <TableBody>
                  {statement.entries.map((entry, index) => (
                    <TableRow key={`${entry.reference ?? 'entry'}-${index}`}>
                      <TableCell>{formatDateTime(entry.date)}</TableCell>
                      <TableCell>{entry.description}</TableCell>
                      <TableCell>{entry.reference ?? '—'}</TableCell>
                      <TableCell align="right">{entry.credit ? formatMoney(entry.credit) : '—'}</TableCell>
                      <TableCell align="right">{entry.debit ? formatMoney(entry.debit) : '—'}</TableCell>
                      <TableCell align="right">{formatMoney(entry.balance)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </section>

      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setAddDialogOpen(false)} />
        <DialogTitle>Add students to family</DialogTitle>
        <DialogContent>
          <div className="space-y-3 mt-4 max-h-[420px] overflow-y-auto">
            {eligibleStudents.map((student) => {
              const disabled =
                student.billing_account_type === 'family' &&
                student.billing_account_id !== account.id
              return (
                <div key={student.id} className="flex items-start justify-between gap-4">
                  <Checkbox
                    disabled={disabled}
                    checked={selectedStudentIds.includes(student.id)}
                    onChange={() => toggleStudent(student.id)}
                    label={`${student.full_name} · ${student.student_number}`}
                  />
                  <span className="text-sm text-slate-500">{student.grade_name ?? 'No grade'}</span>
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
