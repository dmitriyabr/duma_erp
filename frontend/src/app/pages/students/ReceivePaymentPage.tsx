import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, unwrapResponse } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { DEFAULT_PAGE_SIZE, INVOICE_LIST_LIMIT } from '../../constants/pagination'
import type { PaginatedResponse } from '../../types/api'
import { formatMoney } from '../../utils/format'
import { formatStudentNumberShort } from '../../utils/studentNumber'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Spinner } from '../../components/ui/Spinner'

interface StudentOption {
  id: number
  full_name: string
  student_number: string
  billing_account_id?: number | null
  billing_account_number?: string | null
  billing_account_name?: string | null
  billing_account_type?: string | null
}

interface PaymentResponse {
  id: number
  payment_number: string
  status: string
}

interface InvoiceOption {
  id: number
  invoice_number: string
  student_name?: string | null
  amount_due: number
  status: string
}

interface BillingAccountDetail {
  id: number
  account_number: string
  display_name: string
  account_type: string
  members: Array<{ student_id: number; student_name: string }>
}

const emptyForm = {
  amount: '',
  payment_method: 'mpesa',
  payment_date: new Date().toISOString().slice(0, 10),
  reference: '',
  notes: '',
}

export const ReceivePaymentPage = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const state = (
    location.state as {
      studentId?: number
      billingAccountId?: number
      billingAccountName?: string
      preferredInvoiceId?: number
      preferredInvoiceNumber?: string
    } | null
  ) ?? null
  const [selectedStudentId, setSelectedStudentId] = useState<number | ''>(state?.studentId ?? '')
  const [preferredInvoiceId, setPreferredInvoiceId] = useState<number | ''>(
    state?.preferredInvoiceId ?? ''
  )
  const resolvedId = state?.studentId ?? (selectedStudentId === '' ? 0 : selectedStudentId)
  const studentIdLocked = !!state?.studentId

  const [form, setForm] = useState(emptyForm)
  const [confirmationAttachmentId, setConfirmationAttachmentId] = useState<number | null>(null)
  const [confirmationFileName, setConfirmationFileName] = useState<string | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const studentsApi = useApi<PaginatedResponse<StudentOption>>('/students', {
    params: { page: 1, limit: DEFAULT_PAGE_SIZE, status: 'active' },
  }, [])
  const selectedStudent = studentsApi.data?.items?.find((student) => student.id === resolvedId) ?? null
  const resolvedBillingAccountId =
    state?.billingAccountId ??
    selectedStudent?.billing_account_id ??
    0
  const billingAccountApi = useApi<BillingAccountDetail>(
    state?.billingAccountId ? `/billing-accounts/${state.billingAccountId}` : null
  )
  const invoicesApi = useApi<PaginatedResponse<InvoiceOption>>(
    resolvedBillingAccountId ? '/invoices' : resolvedId ? '/invoices' : null,
    {
      params: resolvedBillingAccountId
        ? { billing_account_id: resolvedBillingAccountId, limit: INVOICE_LIST_LIMIT, page: 1 }
        : { student_id: resolvedId, limit: INVOICE_LIST_LIMIT, page: 1 },
    },
    [resolvedId, resolvedBillingAccountId]
  )
  const submitMutation = useApiMutation<PaymentResponse>()
  const uploadMutation = useApiMutation<{ id: number; file_name: string }>()

  const students = studentsApi.data?.items ?? []
  const openInvoices = (invoicesApi.data?.items ?? []).filter((invoice) => {
    const status = invoice.status.toLowerCase()
    return status !== 'paid' && status !== 'cancelled' && status !== 'void'
  })
  const loading = submitMutation.loading

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    uploadMutation.reset()
    setError(null)
    const formData = new FormData()
    formData.append('file', file)
    const result = await uploadMutation.execute(() =>
      api
        .post('/attachments', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
        .then((r) => ({ data: { data: unwrapResponse<{ id: number; file_name: string }>(r) } }))
    )
    if (result != null) {
      setConfirmationAttachmentId(result.id)
      setConfirmationFileName(file.name)
    } else if (uploadMutation.error) {
      setError(uploadMutation.error)
    }
    event.target.value = ''
  }

  const submitPayment = async () => {
    if (!resolvedId && !resolvedBillingAccountId) {
      setError('Select a student.')
      return
    }
    const hasReference = Boolean(form.reference?.trim())
    const hasFile = confirmationAttachmentId != null
    if (!hasReference && !hasFile) {
      setError('Reference or confirmation file is required.')
      return
    }
    setError(null)
    submitMutation.reset()
    const created = await submitMutation.execute(async () => {
      const createRes = await api.post('/payments', {
        student_id: resolvedId || undefined,
        billing_account_id: resolvedBillingAccountId || undefined,
        preferred_invoice_id: preferredInvoiceId === '' ? undefined : preferredInvoiceId,
        amount: Number(form.amount),
        payment_method: form.payment_method,
        payment_date: form.payment_date,
        reference: form.reference.trim() || null,
        confirmation_attachment_id: confirmationAttachmentId ?? undefined,
        notes: form.notes.trim() || null,
      })
      const payment = unwrapResponse<PaymentResponse>(createRes)
      await api.post(`/payments/${payment.id}/complete`)
      return { data: { data: payment } }
    })
    if (created != null) {
      if (state?.billingAccountId) {
        navigate(`/billing/families/${resolvedBillingAccountId}`)
      } else {
        navigate(`/students/${resolvedId}?tab=payments`)
      }
    } else if (submitMutation.error) {
      setError(submitMutation.error)
    }
  }

  if (!resolvedId && !state?.billingAccountId) {
    return (
      <div>
        <Button onClick={() => navigate(-1)} className="mb-4">
          Back
        </Button>
        <Typography variant="h4" className="mb-4">
          Receive student payment
        </Typography>
        {(error || studentsApi.error) && (
          <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
            {error ?? studentsApi.error}
          </Alert>
        )}
        <Select
          value={selectedStudentId === '' ? '' : String(selectedStudentId)}
          onChange={(e) => {
            setSelectedStudentId(e.target.value ? Number(e.target.value) : '')
            setPreferredInvoiceId('')
          }}
          label="Student"
          className="min-w-[280px] mb-4"
        >
          <option value="">Select student</option>
          {students.map((s) => (
            <option key={s.id} value={String(s.id)}>
              {s.full_name} · #{formatStudentNumberShort(s.student_number)}
            </option>
          ))}
        </Select>
      </div>
    )
  }

  const student = students.find((s) => s.id === resolvedId)
  const displayError =
    error ?? submitMutation.error ?? uploadMutation.error ?? invoicesApi.error ?? billingAccountApi.error
  const accountLabel =
    billingAccountApi.data?.display_name ??
    state?.billingAccountName ??
    selectedStudent?.billing_account_name ??
    null
  const accountNumber =
    billingAccountApi.data?.account_number ?? selectedStudent?.billing_account_number ?? null

  return (
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-2">
        {state?.billingAccountId ? 'Receive family payment' : 'Receive student payment'}
      </Typography>
      {student && (
        <Typography variant="body2" color="secondary" className="mb-4">
          {student.full_name} · #{formatStudentNumberShort(student.student_number)}
          {selectedStudent?.billing_account_type === 'family' && accountLabel
            ? ` · ${accountLabel}${accountNumber ? ` (${accountNumber})` : ''}`
            : ''}
          {!studentIdLocked && (
            <Button size="small" variant="text" className="ml-2" onClick={() => setSelectedStudentId('')}>
              Change student
            </Button>
          )}
        </Typography>
      )}
      {!student && state?.billingAccountId && accountLabel && (
        <Typography variant="body2" color="secondary" className="mb-4">
          {accountLabel}
          {accountNumber ? ` · ${accountNumber}` : ''}
        </Typography>
      )}
      {displayError && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {displayError}
        </Alert>
      )}
      <div className="grid gap-4 max-w-[420px]">
        <Input
          label="Amount"
          type="number"
          value={form.amount}
          onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
          required
        />
        <Select
          value={form.payment_method}
          onChange={(e) => setForm((f) => ({ ...f, payment_method: e.target.value }))}
          label="Method"
        >
          <option value="mpesa">M-Pesa</option>
          <option value="bank_transfer">Bank transfer</option>
        </Select>
        <Select
          value={preferredInvoiceId === '' ? '' : String(preferredInvoiceId)}
          onChange={(e) => setPreferredInvoiceId(e.target.value ? Number(e.target.value) : '')}
          label="Apply first to invoice"
          helperText="Optional. This invoice will be paid first, then any remainder will go to other debts."
        >
          <option value="">Auto-allocate normally</option>
          {openInvoices.map((invoice) => (
            <option key={invoice.id} value={String(invoice.id)}>
              {invoice.invoice_number}
              {invoice.student_name ? ` · ${invoice.student_name}` : ''}
              {' · '}
              Due {formatMoney(invoice.amount_due)}
            </option>
          ))}
        </Select>
        <Input
          label="Payment date"
          type="date"
          value={form.payment_date}
          onChange={(e) => setForm((f) => ({ ...f, payment_date: e.target.value }))}
        />
        <Input
          label="Reference (optional if file uploaded)"
          value={form.reference}
          onChange={(e) => setForm((f) => ({ ...f, reference: e.target.value }))}
          helperText="Reference or confirmation file below is required"
        />
        <div>
          <label className="inline-block">
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept="image/*,.pdf,application/pdf"
              onChange={handleFileChange}
            />
            <Button
              variant="outlined"
              disabled={uploadMutation.loading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadMutation.loading ? <Spinner size="small" /> : 'Upload confirmation (image/PDF)'}
            </Button>
          </label>
          {confirmationFileName && (
            <Typography variant="body2" color="secondary" className="ml-2 inline-block">
              {confirmationFileName}
            </Typography>
          )}
        </div>
        <Textarea
          label="Notes"
          value={form.notes}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          rows={3}
        />
      </div>
      <div className="flex gap-2 mt-6">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={submitPayment}
          disabled={loading || (!form.reference?.trim() && confirmationAttachmentId == null)}
        >
          {loading ? <Spinner size="small" /> : 'Save'}
        </Button>
      </div>
    </div>
  )
}
