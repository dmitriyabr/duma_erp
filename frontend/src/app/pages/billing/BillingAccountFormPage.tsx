import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { canManageBillingAccounts } from '../../utils/permissions'
import type { PaginatedResponse } from '../../types/api'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Typography } from '../../components/ui/Typography'
import { Spinner } from '../../components/ui/Spinner'

interface StudentOption {
  id: number
  full_name: string
  student_number: string
  grade_name?: string | null
  billing_account_id?: number | null
  billing_account_type?: string | null
}

interface BillingAccountDetail {
  id: number
  account_number: string
  display_name: string
  primary_guardian_name?: string | null
  primary_guardian_phone?: string | null
  primary_guardian_email?: string | null
  notes?: string | null
  members: Array<{ student_id: number }>
}

const emptyForm = {
  display_name: '',
  primary_guardian_name: '',
  primary_guardian_phone: '',
  primary_guardian_email: '',
  notes: '',
}

export const BillingAccountFormPage = () => {
  const { accountId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = canManageBillingAccounts(user)
  const editing = Boolean(accountId)

  const { data: account, loading: accountLoading, error: accountError } = useApi<BillingAccountDetail>(
    editing ? `/billing-accounts/${accountId}` : null
  )
  const studentsApi = useApi<PaginatedResponse<StudentOption>>('/students', {
    params: { page: 1, limit: 500, status: 'active' },
  }, [])
  const [error, setError] = useState<string | null>(null)

  if (!canManage) {
    return <Alert severity="error">Access denied.</Alert>
  }

  if (editing && accountLoading) {
    return <Spinner size="medium" />
  }

  const initialForm = account
    ? {
        display_name: account.display_name,
        primary_guardian_name: account.primary_guardian_name ?? '',
        primary_guardian_phone: account.primary_guardian_phone ?? '',
        primary_guardian_email: account.primary_guardian_email ?? '',
        notes: account.notes ?? '',
      }
    : emptyForm
  const initialStudentIds = account?.members.map((member) => member.student_id) ?? []

  return (
    <div>
      <Button variant="outlined" className="mb-4" onClick={() => navigate(-1)}>
        Back
      </Button>
      <Typography variant="h4" className="mb-4">
        {editing ? 'Edit family billing account' : 'New family billing account'}
      </Typography>

      {(error || accountError || studentsApi.error) && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error ?? accountError ?? studentsApi.error}
        </Alert>
      )}

      <BillingAccountFormContent
        key={editing ? String(account?.id ?? 'edit') : 'new'}
        accountId={accountId}
        editing={editing}
        students={studentsApi.data?.items ?? []}
        initialForm={initialForm}
        initialStudentIds={initialStudentIds}
        onError={setError}
      />
    </div>
  )
}

interface BillingAccountFormContentProps {
  accountId?: string
  editing: boolean
  students: StudentOption[]
  initialForm: typeof emptyForm
  initialStudentIds: number[]
  onError: (message: string | null) => void
}

const BillingAccountFormContent = ({
  accountId,
  editing,
  students,
  initialForm,
  initialStudentIds,
  onError,
}: BillingAccountFormContentProps) => {
  const navigate = useNavigate()
  const saveMutation = useApiMutation<BillingAccountDetail>()
  const [form, setForm] = useState(initialForm)
  const [selectedStudentIds, setSelectedStudentIds] = useState(initialStudentIds)

  const availableStudents = useMemo(
    () =>
      students.filter((student) => {
        if (editing) return selectedStudentIds.includes(student.id)
        return student.billing_account_type !== 'family'
      }),
    [editing, selectedStudentIds, students]
  )

  const toggleStudent = (studentId: number) => {
    setSelectedStudentIds((current) =>
      current.includes(studentId)
        ? current.filter((id) => id !== studentId)
        : [...current, studentId]
    )
  }

  const submit = async () => {
    if (!form.display_name.trim()) {
      onError('Family name is required.')
      return
    }
    if (!editing && selectedStudentIds.length < 2) {
      onError('Select at least 2 students for a new family account.')
      return
    }

    onError(null)
    saveMutation.reset()
    const payload = {
      display_name: form.display_name.trim(),
      primary_guardian_name: form.primary_guardian_name.trim() || null,
      primary_guardian_phone: form.primary_guardian_phone.trim() || null,
      primary_guardian_email: form.primary_guardian_email.trim() || null,
      notes: form.notes.trim() || null,
      student_ids: selectedStudentIds,
    }

    const result = await saveMutation.execute(() =>
      editing
        ? api.patch(`/billing-accounts/${accountId}`, payload)
        : api.post('/billing-accounts', payload)
    )

    if (result) {
      navigate(`/billing/families/${result.id}`)
    } else if (saveMutation.error) {
      onError(saveMutation.error)
    }
  }

  return (
    <div className="grid gap-6 max-w-[900px]">
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Family name"
          value={form.display_name}
          onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
          required
        />
        <Input
          label="Primary guardian name"
          value={form.primary_guardian_name}
          onChange={(event) =>
            setForm((current) => ({ ...current, primary_guardian_name: event.target.value }))
          }
        />
        <Input
          label="Primary guardian phone"
          value={form.primary_guardian_phone}
          onChange={(event) =>
            setForm((current) => ({ ...current, primary_guardian_phone: event.target.value }))
          }
        />
        <Input
          label="Primary guardian email"
          value={form.primary_guardian_email}
          onChange={(event) =>
            setForm((current) => ({ ...current, primary_guardian_email: event.target.value }))
          }
        />
      </div>

      <Textarea
        label="Notes"
        value={form.notes}
        onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
        rows={4}
      />

      {!editing && (
        <div className="space-y-3">
          <Typography variant="h6">Students in this family</Typography>
          <div className="border border-slate-200 rounded-lg p-4 max-h-[360px] overflow-y-auto space-y-3">
            {availableStudents.map((student) => (
              <div key={student.id} className="flex items-start justify-between gap-4">
                <Checkbox
                  checked={selectedStudentIds.includes(student.id)}
                  onChange={() => toggleStudent(student.id)}
                  label={`${student.full_name} · ${student.student_number}`}
                />
                <span className="text-sm text-slate-500">{student.grade_name ?? 'No grade'}</span>
              </div>
            ))}
            {!availableStudents.length && (
              <Typography color="secondary">No eligible students available.</Typography>
            )}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={saveMutation.loading}>
          {saveMutation.loading ? <Spinner size="small" /> : editing ? 'Save' : 'Create family'}
        </Button>
      </div>
    </div>
  )
}
