import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { Textarea } from '../../components/ui/Textarea'
import { Typography } from '../../components/ui/Typography'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { canManageBillingAccounts } from '../../utils/permissions'
import { BillingAccountChildEditor } from './components/BillingAccountChildEditor'
import {
  buildBillingChildPayload,
  createEmptyBillingChildDraft,
  type BillingAccountChildDraft,
  type BillingAccountChildErrors,
  validateBillingChildDraft,
} from './components/billingAccountChildForm'

interface StudentOption {
  id: number
  full_name: string
  student_number: string
  grade_name?: string | null
  billing_account_id?: number | null
  billing_account_member_count?: number | null
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
  const { grades, transportZones, loading: referencedLoading, error: referencedError } = useReferencedData()
  const canManage = canManageBillingAccounts(user)
  const editing = Boolean(accountId)

  const { data: account, loading: accountLoading, error: accountError } = useApi<BillingAccountDetail>(
    editing ? `/billing-accounts/${accountId}` : null
  )
  const studentsApi = useApi<PaginatedResponse<StudentOption>>(
    '/students',
    {
      params: { page: 1, limit: 500, status: 'active' },
    },
    []
  )
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
        {editing ? 'Edit billing account' : 'New admission'}
      </Typography>

      {(error || accountError || studentsApi.error || referencedError) && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error ?? accountError ?? studentsApi.error ?? referencedError}
        </Alert>
      )}

      <BillingAccountFormContent
        key={editing ? String(account?.id ?? 'edit') : 'new'}
        accountId={accountId}
        editing={editing}
        students={studentsApi.data?.items ?? []}
        initialForm={initialForm}
        initialStudentIds={initialStudentIds}
        grades={grades}
        transportZones={transportZones}
        loadingChoices={studentsApi.loading || referencedLoading}
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
  grades: ReturnType<typeof useReferencedData>['grades']
  transportZones: ReturnType<typeof useReferencedData>['transportZones']
  loadingChoices: boolean
  onError: (message: string | null) => void
}

const BillingAccountFormContent = ({
  accountId,
  editing,
  students,
  initialForm,
  initialStudentIds,
  grades,
  transportZones,
  loadingChoices,
  onError,
}: BillingAccountFormContentProps) => {
  const navigate = useNavigate()
  const saveMutation = useApiMutation<BillingAccountDetail>()
  const [form, setForm] = useState(initialForm)
  const [selectedStudentIds, setSelectedStudentIds] = useState(initialStudentIds)
  const [newChildren, setNewChildren] = useState<BillingAccountChildDraft[]>(
    editing ? [] : [createEmptyBillingChildDraft()]
  )
  const [childErrors, setChildErrors] = useState<BillingAccountChildErrors[]>([])
  const [existingStudentsOpen, setExistingStudentsOpen] = useState(false)

  const familyDefaults = useMemo(
    () => ({
      guardian_name: form.primary_guardian_name,
      guardian_phone: form.primary_guardian_phone,
      guardian_email: form.primary_guardian_email,
    }),
    [form.primary_guardian_email, form.primary_guardian_name, form.primary_guardian_phone]
  )

  const availableStudents = useMemo(
    () =>
      students.filter((student) => {
        if (editing) return selectedStudentIds.includes(student.id)
        return (student.billing_account_member_count ?? 0) <= 1
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

  const addChild = () => {
    setNewChildren((current) => [...current, createEmptyBillingChildDraft()])
    setChildErrors((current) => [...current, {}])
  }

  const updateChild = (index: number, nextChild: BillingAccountChildDraft) => {
    setNewChildren((current) => current.map((child, childIndex) => (childIndex === index ? nextChild : child)))
    setChildErrors((current) => current.map((errors, childIndex) => (childIndex === index ? {} : errors)))
  }

  const removeChild = (index: number) => {
    setNewChildren((current) => current.filter((_, childIndex) => childIndex !== index))
    setChildErrors((current) => current.filter((_, childIndex) => childIndex !== index))
  }

  const submit = async () => {
    if (!form.display_name.trim()) {
      onError('Billing account name is required.')
      return
    }

    if (!editing && selectedStudentIds.length + newChildren.length < 1) {
      onError('Add at least one child or link at least one existing student.')
      return
    }

    const nextChildErrors = editing
      ? []
      : newChildren.map((child) => validateBillingChildDraft(child, familyDefaults))
    const hasChildErrors = nextChildErrors.some((entry) => Object.keys(entry).length > 0)
    setChildErrors(nextChildErrors)
    if (hasChildErrors) {
      onError('Fix the highlighted child details before saving the admission.')
      return
    }

    onError(null)
    saveMutation.reset()

    const basePayload = {
      display_name: form.display_name.trim(),
      primary_guardian_name: form.primary_guardian_name.trim() || null,
      primary_guardian_phone: form.primary_guardian_phone.trim() || null,
      primary_guardian_email: form.primary_guardian_email.trim() || null,
      notes: form.notes.trim() || null,
    }

    const payload = editing
      ? basePayload
      : {
          ...basePayload,
          student_ids: selectedStudentIds,
          new_children: newChildren.map((child) => buildBillingChildPayload(child)),
        }

    const result = await saveMutation.execute(() =>
      editing ? api.patch(`/billing-accounts/${accountId}`, payload) : api.post('/billing-accounts', payload)
    )

    if (result) {
      navigate(`/billing/families/${result.id}`)
    } else if (saveMutation.error) {
      onError(saveMutation.error)
    }
  }

  return (
    <div className="grid gap-6 max-w-[980px]">
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Billing account name"
          value={form.display_name}
          onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
          required
        />
        <Input
          label="Billing contact name"
          value={form.primary_guardian_name}
          onChange={(event) =>
            setForm((current) => ({ ...current, primary_guardian_name: event.target.value }))
          }
        />
        <Input
          label="Billing contact phone"
          value={form.primary_guardian_phone}
          onChange={(event) =>
            setForm((current) => ({ ...current, primary_guardian_phone: event.target.value }))
          }
          helperText="Used as the default payer/contact and fallback for child forms."
        />
        <Input
          label="Billing contact email"
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
        <>
          <section className="space-y-3">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <Typography variant="h6">Children</Typography>
                <Typography variant="body2" color="secondary" className="mt-1">
                  Add one or more children for this admission. They will share the same billing account.
                </Typography>
              </div>
              <Button type="button" variant="outlined" onClick={addChild}>
                Add child
              </Button>
            </div>

            {newChildren.map((child, index) => (
              <BillingAccountChildEditor
                key={`child-${index}`}
                title={`Child ${index + 1}`}
                value={child}
                onChange={(next) => updateChild(index, next)}
                onRemove={() => removeChild(index)}
                grades={grades}
                transportZones={transportZones}
                errors={childErrors[index]}
                helperText="Guardian fields can be left blank if they match the billing contact above."
              />
            ))}

            {!newChildren.length && (
              <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
                No new children added yet.
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <Typography variant="body2" className="font-medium">
                    Already admitted child?
                  </Typography>
                  <Typography variant="body2" color="secondary" className="mt-1">
                    Optional. Link an existing student only if they should use this billing account.
                  </Typography>
                </div>
                <Button
                  type="button"
                  variant="outlined"
                  onClick={() => setExistingStudentsOpen((current) => !current)}
                >
                  {existingStudentsOpen ? 'Hide existing students' : 'Link existing student'}
                  {selectedStudentIds.length > 0 ? ` (${selectedStudentIds.length})` : ''}
                </Button>
              </div>
            </div>

            {existingStudentsOpen && (
              <div className="border border-slate-200 rounded-lg p-4 max-h-[360px] overflow-y-auto space-y-3 bg-white">
                {loadingChoices && !availableStudents.length ? (
                  <div className="py-6 flex justify-center">
                    <Spinner size="medium" />
                  </div>
                ) : (
                  availableStudents.map((student) => (
                    <div key={student.id} className="flex items-start justify-between gap-4">
                      <Checkbox
                        checked={selectedStudentIds.includes(student.id)}
                        onChange={() => toggleStudent(student.id)}
                        label={`${student.full_name} · ${student.student_number}`}
                      />
                      <span className="text-sm text-slate-500">{student.grade_name ?? 'No grade'}</span>
                    </div>
                  ))
                )}
                {!availableStudents.length && !loadingChoices && (
                  <Typography color="secondary">No eligible students available.</Typography>
                )}
              </div>
            )}
          </section>
        </>
      )}

      <div className="flex gap-2">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={saveMutation.loading}>
          {saveMutation.loading ? <Spinner size="small" /> : editing ? 'Save' : 'Create admission'}
        </Button>
      </div>
    </div>
  )
}
