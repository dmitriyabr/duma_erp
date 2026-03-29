import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api, unwrapResponse } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { formatMoney } from '../../utils/format'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Checkbox'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Typography } from '../../components/ui/Typography'
import { Autocomplete } from '../../components/ui/Autocomplete'
import { Spinner } from '../../components/ui/Spinner'

interface GradeOption {
  id: number
  name: string
}

interface TermOption {
  id: number
  display_name: string
}

interface StudentOption {
  id: number
  full_name: string
  student_number: string
  grade_name?: string | null
}

interface ActivityParticipant {
  student_id: number
  student_name: string
  student_number: string
  grade_name?: string | null
  status: string
  invoice_id?: number | null
}

interface ActivityDetail {
  id: number
  code?: string | null
  name: string
  description?: string | null
  activity_date?: string | null
  due_date?: string | null
  term_id?: number | null
  status: string
  audience_type: string
  amount: string
  requires_full_payment: boolean
  notes?: string | null
  audience_grade_ids: number[]
  audience_student_ids: number[]
  participants: ActivityParticipant[]
}

const statusOptions = ['draft', 'published', 'closed', 'cancelled']

interface ActivityFormContentProps {
  initialActivity: ActivityDetail | null
  isEdit: boolean
  resolvedId: number | null
  terms: TermOption[]
  grades: GradeOption[]
}

const ActivityFormContent = ({
  initialActivity,
  isEdit,
  resolvedId,
  terms,
  grades,
}: ActivityFormContentProps) => {
  const navigate = useNavigate()
  const submitMutation = useApiMutation<ActivityDetail>()
  const initialManualStudentIds = new Set(
    initialActivity?.audience_type === 'manual' ? initialActivity.audience_student_ids : []
  )
  const initialManualStudents =
    initialActivity?.audience_type === 'manual'
      ? initialActivity.participants
          .filter((participant) => initialManualStudentIds.has(participant.student_id))
          .map((participant) => ({
            id: participant.student_id,
            full_name: participant.student_name,
            student_number: participant.student_number,
            grade_name: participant.grade_name,
          }))
      : []

  const [name, setName] = useState(initialActivity?.name ?? '')
  const [code, setCode] = useState(initialActivity?.code ?? '')
  const [description, setDescription] = useState(initialActivity?.description ?? '')
  const [activityDate, setActivityDate] = useState(initialActivity?.activity_date ?? '')
  const [dueDate, setDueDate] = useState(initialActivity?.due_date ?? '')
  const [termId, setTermId] = useState<string>(
    initialActivity?.term_id ? String(initialActivity.term_id) : 'none'
  )
  const [amount, setAmount] = useState(initialActivity ? String(initialActivity.amount) : '')
  const [requiresFullPayment, setRequiresFullPayment] = useState(
    initialActivity?.requires_full_payment ?? false
  )
  const [status, setStatus] = useState(initialActivity?.status ?? 'draft')
  const [notes, setNotes] = useState(initialActivity?.notes ?? '')
  const [audienceType, setAudienceType] = useState<'all_active' | 'grades' | 'manual'>(
    (initialActivity?.audience_type as 'all_active' | 'grades' | 'manual') ?? 'all_active'
  )
  const [selectedGradeIds, setSelectedGradeIds] = useState<number[]>(
    initialActivity?.audience_grade_ids ?? []
  )
  const [selectedStudents, setSelectedStudents] = useState<StudentOption[]>(initialManualStudents)
  const [studentSearch, setStudentSearch] = useState('')
  const [pendingStudent, setPendingStudent] = useState<StudentOption | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  const debouncedStudentSearch = useDebouncedValue(studentSearch, 250)
  const hasGeneratedInvoices = initialActivity?.participants.some((participant) => participant.invoice_id != null) ?? false

  const studentsUrl = useMemo(() => {
    if (audienceType !== 'manual') return null
    const params = new URLSearchParams()
    params.append('status', 'active')
    params.append('page', '1')
    params.append('limit', '20')
    if (debouncedStudentSearch.trim()) params.append('search', debouncedStudentSearch.trim())
    return `/students?${params.toString()}`
  }, [audienceType, debouncedStudentSearch])
  const studentsApi = useApi<PaginatedResponse<StudentOption>>(studentsUrl)
  const studentOptions = studentsApi.data?.items ?? []

  const toggleGrade = (gradeId: number) => {
    setSelectedGradeIds((current) =>
      current.includes(gradeId)
        ? current.filter((id) => id !== gradeId)
        : [...current, gradeId]
    )
  }

  const addSelectedStudent = (student: StudentOption | null) => {
    if (!student) return
    setSelectedStudents((current) => {
      if (current.some((existing) => existing.id === student.id)) return current
      return [...current, student]
    })
    setPendingStudent(null)
    setStudentSearch('')
  }

  const removeSelectedStudent = (studentId: number) => {
    setSelectedStudents((current) => current.filter((student) => student.id !== studentId))
  }

  const submit = async () => {
    if (!name.trim()) {
      setValidationError('Name is required.')
      return
    }
    if (!amount.trim()) {
      setValidationError('Amount is required.')
      return
    }
    if (audienceType === 'grades' && selectedGradeIds.length === 0) {
      setValidationError('Select at least one grade.')
      return
    }
    if (audienceType === 'manual' && selectedStudents.length === 0) {
      setValidationError('Select at least one student.')
      return
    }

    setValidationError(null)
    const payload: Record<string, unknown> = {
      code: code.trim() || null,
      name: name.trim(),
      description: description.trim() || null,
      activity_date: activityDate || null,
      due_date: dueDate || null,
      term_id: termId === 'none' ? null : Number(termId),
      amount: Number(amount),
      requires_full_payment: requiresFullPayment,
      status,
      notes: notes.trim() || null,
    }

    if (!isEdit || !hasGeneratedInvoices) {
      payload.audience_type = audienceType
      payload.grade_ids = audienceType === 'grades' ? selectedGradeIds : []
      payload.student_ids =
        audienceType === 'manual' ? selectedStudents.map((student) => student.id) : []
    }

    const result = await submitMutation.execute(() =>
      (isEdit && resolvedId
        ? api.patch(`/activities/${resolvedId}`, payload)
        : api.post('/activities', payload)
      ).then((response) => ({ data: { data: unwrapResponse<ActivityDetail>(response) } }))
    )
    if (result) {
      navigate(`/billing/activities/${result.id}`)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <Typography variant="h4">{isEdit ? 'Edit activity' : 'New activity'}</Typography>
        <Typography variant="body2" color="secondary" className="mt-1">
          Configure the activity, define the audience, and use the detail page to generate invoices.
        </Typography>
      </div>

      {(validationError || submitMutation.error) && (
        <Alert severity="error" className="mb-4">
          {validationError || submitMutation.error}
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <Typography variant="h6" className="mb-4">Activity details</Typography>
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Name" value={name} onChange={(event) => setName(event.target.value)} required />
              <Input
                label="Code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="Optional short code"
              />
              <Input
                label="Activity date"
                type="date"
                value={activityDate}
                onChange={(event) => setActivityDate(event.target.value)}
              />
              <Input
                label="Due date"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
              <Select label="Term" value={termId} onChange={(event) => setTermId(event.target.value)}>
                <option value="none">No term</option>
                {terms.map((term) => (
                  <option key={term.id} value={term.id}>
                    {term.display_name}
                  </option>
                ))}
              </Select>
              <Select label="Status" value={status} onChange={(event) => setStatus(event.target.value)}>
                {statusOptions
                  .filter((option) => !(hasGeneratedInvoices && option === 'cancelled'))
                  .map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
              </Select>
              <Input
                label="Amount"
                type="number"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                required
              />
              <div className="flex items-end">
                <Checkbox
                  checked={requiresFullPayment}
                  onChange={(event) => setRequiresFullPayment(event.target.checked)}
                  label="Requires full payment"
                />
              </div>
            </div>
            <div className="grid gap-4 mt-4">
              <Input
                label="Description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Optional description"
              />
              <Input
                label="Notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Internal notes"
              />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-4">
              <Typography variant="h6">Audience</Typography>
              {hasGeneratedInvoices && (
                <Typography variant="body2" color="secondary" className="mt-1">
                  Audience is locked because invoices already exist. Use the detail page to add or exclude students.
                </Typography>
              )}
            </div>

            <div className="grid gap-4">
              <Select
                label="Audience type"
                value={audienceType}
                onChange={(event) => setAudienceType(event.target.value as 'all_active' | 'grades' | 'manual')}
                disabled={hasGeneratedInvoices}
              >
                <option value="all_active">All active students</option>
                <option value="grades">Selected grades</option>
                <option value="manual">Manual selection</option>
              </Select>

              {audienceType === 'grades' && (
                <div className="grid gap-2 sm:grid-cols-2">
                  {grades.map((grade) => (
                    <Checkbox
                      key={grade.id}
                      checked={selectedGradeIds.includes(grade.id)}
                      onChange={() => toggleGrade(grade.id)}
                      label={grade.name}
                      disabled={hasGeneratedInvoices}
                    />
                  ))}
                </div>
              )}

              {audienceType === 'manual' && (
                <div className="space-y-4">
                  <div className="flex gap-3 items-end">
                    <div className="flex-1">
                      <Autocomplete
                        options={studentOptions}
                        value={pendingStudent}
                        onChange={setPendingStudent}
                        onInputChange={setStudentSearch}
                        loading={studentsApi.loading}
                        label="Search students"
                        placeholder="Type student name or number"
                        getOptionLabel={(student) => `${student.full_name} (${student.student_number})`}
                        getOptionValue={(student) => student.id}
                        renderOption={(student) => (
                          <div className="flex flex-col">
                            <span>{student.full_name}</span>
                            <span className="text-xs text-slate-500">
                              {student.student_number}
                              {student.grade_name ? ` · ${student.grade_name}` : ''}
                            </span>
                          </div>
                        )}
                        disabled={hasGeneratedInvoices}
                      />
                    </div>
                    <Button
                      variant="outlined"
                      onClick={() => addSelectedStudent(pendingStudent)}
                      disabled={!pendingStudent || hasGeneratedInvoices}
                    >
                      Add
                    </Button>
                  </div>

                  <div className="rounded-lg border border-slate-200">
                    <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
                      <Typography variant="body2" color="secondary">
                        Selected students: {selectedStudents.length}
                      </Typography>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {selectedStudents.map((student) => (
                        <div key={student.id} className="flex items-center justify-between gap-4 px-4 py-3">
                          <div>
                            <Typography>{student.full_name}</Typography>
                            <Typography variant="body2" color="secondary">
                              {student.student_number}
                              {student.grade_name ? ` · ${student.grade_name}` : ''}
                            </Typography>
                          </div>
                          {!hasGeneratedInvoices && (
                            <Button
                              size="small"
                              variant="outlined"
                              color="error"
                              onClick={() => removeSelectedStudent(student.id)}
                            >
                              Remove
                            </Button>
                          )}
                        </div>
                      ))}
                      {!selectedStudents.length && (
                        <div className="px-4 py-6">
                          <Typography color="secondary">No students selected yet</Typography>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 h-fit">
          <Typography variant="h6" className="mb-4">Summary</Typography>
          <div className="space-y-3">
            <div>
              <Typography variant="body2" color="secondary">Audience</Typography>
              <Typography className="mt-1">
                {audienceType === 'all_active'
                  ? 'All active students'
                  : audienceType === 'grades'
                    ? `${selectedGradeIds.length} grade(s)`
                    : `${selectedStudents.length} student(s)`}
              </Typography>
            </div>
            <div>
              <Typography variant="body2" color="secondary">Amount</Typography>
              <Typography className="mt-1">{amount ? formatMoney(Number(amount)) : '—'}</Typography>
            </div>
            <div>
              <Typography variant="body2" color="secondary">Due date</Typography>
              <Typography className="mt-1">{dueDate || '—'}</Typography>
            </div>
          </div>

          <div className="flex gap-2 mt-6">
            <Button
              variant="outlined"
              onClick={() =>
                navigate(isEdit && resolvedId ? `/billing/activities/${resolvedId}` : '/billing/activities')
              }
            >
              Cancel
            </Button>
            <Button onClick={submit} disabled={submitMutation.loading}>
              {submitMutation.loading ? 'Saving...' : 'Save activity'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export const ActivityFormPage = () => {
  const { activityId } = useParams()
  const isEdit = Boolean(activityId)
  const resolvedId = activityId ? Number(activityId) : null
  const { grades } = useReferencedData()

  const activityApi = useApi<ActivityDetail>(resolvedId ? `/activities/${resolvedId}` : null, {}, [resolvedId])
  const termsApi = useApi<TermOption[]>('/terms')

  if (isEdit && activityApi.loading && !activityApi.data) {
    return (
      <div className="py-12 flex justify-center">
        <Spinner size="medium" />
      </div>
    )
  }

  if (activityApi.error) {
    return (
      <Alert severity="error">
        {activityApi.error}
      </Alert>
    )
  }

  return (
    <ActivityFormContent
      key={isEdit ? `loaded-${resolvedId}` : 'new-activity'}
      initialActivity={activityApi.data ?? null}
      isEdit={isEdit}
      resolvedId={resolvedId}
      terms={termsApi.data ?? []}
      grades={grades}
    />
  )
}
