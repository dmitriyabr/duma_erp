import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, unwrapResponse } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import type { PaginatedResponse } from '../../types/api'
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
}

interface PaymentResponse {
  id: number
  payment_number: string
  status: string
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
  const state = (location.state as { studentId?: number } | null) ?? null
  const [selectedStudentId, setSelectedStudentId] = useState<number | ''>(state?.studentId ?? '')
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
  const submitMutation = useApiMutation<PaymentResponse>()
  const uploadMutation = useApiMutation<{ id: number; file_name: string }>()

  const students = studentsApi.data?.items ?? []
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
    if (!resolvedId) {
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
        student_id: resolvedId,
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
      navigate(`/students/${resolvedId}?tab=payments`)
    } else if (submitMutation.error) {
      setError(submitMutation.error)
    }
  }

  if (!resolvedId) {
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
          onChange={(e) => setSelectedStudentId(e.target.value ? Number(e.target.value) : '')}
          label="Student"
          className="min-w-[280px] mb-4"
        >
          <option value="">Select student</option>
          {students.map((s) => (
            <option key={s.id} value={String(s.id)}>
              {s.full_name} · #{s.student_number}
            </option>
          ))}
        </Select>
      </div>
    )
  }

  const student = students.find((s) => s.id === resolvedId)
  const displayError = error ?? submitMutation.error ?? uploadMutation.error

  return (
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-2">
        Receive student payment
      </Typography>
      {student && (
        <Typography variant="body2" color="secondary" className="mb-4">
          {student.full_name} · #{student.student_number}
          {!studentIdLocked && (
            <Button size="small" variant="text" className="ml-2" onClick={() => setSelectedStudentId('')}>
              Change student
            </Button>
          )}
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
