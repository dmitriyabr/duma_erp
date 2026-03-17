import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { api } from '../../services/api'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import type { ApiResponse } from '../../types/api'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Switch } from '../../components/ui/Switch'
import { Spinner } from '../../components/ui/Spinner'
import { parseApiError } from '../../utils/apiErrors'

type Gender = 'male' | 'female'

type DiscountValueType = 'fixed' | 'percentage'

interface StudentRow {
  id: number
  student_number: string
  full_name: string
}

type StudentFormField = keyof typeof emptyForm

type StudentFieldErrors = Partial<Record<StudentFormField, string>>

const emptyForm = {
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: 'male' as Gender,
  grade_id: '',
  transport_zone_id: '',
  guardian_name: '',
  guardian_phone: '',
  guardian_email: '',
  enrollment_date: new Date().toISOString().slice(0, 10),
  notes: '',
}

const emptyDiscountForm = {
  enabled: false,
  value_type: 'percentage' as DiscountValueType,
  value: '',
  reason_text: '',
}

export const CreateStudentPage = () => {
  const navigate = useNavigate()
  const { grades, transportZones } = useReferencedData()
  const [form, setForm] = useState({ ...emptyForm })
  const [discountForm, setDiscountForm] = useState({ ...emptyDiscountForm })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveErrorDetails, setSaveErrorDetails] = useState<string[]>([])
  const [fieldErrors, setFieldErrors] = useState<StudentFieldErrors>({})

  const fieldLabels = useMemo<Record<StudentFormField, string>>(
    () => ({
      first_name: 'First name',
      last_name: 'Last name',
      date_of_birth: 'Date of birth',
      gender: 'Gender',
      grade_id: 'Grade',
      transport_zone_id: 'Transport zone',
      guardian_name: 'Guardian name',
      guardian_phone: 'Guardian phone',
      guardian_email: 'Guardian email',
      enrollment_date: 'Enrollment date',
      notes: 'Notes',
    }),
    []
  )

  const setFormField = <K extends StudentFormField>(field: K, value: (typeof emptyForm)[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setFieldErrors((prev) => {
      if (!prev[field]) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }

  const validateForm = (): StudentFieldErrors => {
    const errors: StudentFieldErrors = {}

    if (!form.first_name.trim()) errors.first_name = 'First name is required.'
    if (!form.last_name.trim()) errors.last_name = 'Last name is required.'
    if (!form.grade_id) errors.grade_id = 'Select a grade.'
    if (!form.guardian_name.trim()) errors.guardian_name = 'Guardian name is required.'
    if (!form.guardian_phone.trim()) errors.guardian_phone = 'Guardian phone is required.'

    return errors
  }

  const formatFieldError = (field: string | null | undefined, message: string) => {
    if (!field) return message
    const label = fieldLabels[field as StudentFormField]
    return label ? `${label}: ${message}` : message
  }

  const submitCreate = async () => {
    const clientErrors = validateForm()
    if (Object.keys(clientErrors).length > 0) {
      setFieldErrors(clientErrors)
      setSaveError('Fill in the required fields and correct the highlighted values.')
      setSaveErrorDetails(
        Object.entries(clientErrors).map(([field, message]) =>
          formatFieldError(field, message as string)
        )
      )
      return
    }

    setSaving(true)
    setSaveError(null)
    setSaveErrorDetails([])
    setFieldErrors({})

    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      date_of_birth: form.date_of_birth || null,
      gender: form.gender,
      grade_id: form.grade_id ? Number(form.grade_id) : null,
      transport_zone_id: form.transport_zone_id ? Number(form.transport_zone_id) : null,
      guardian_name: form.guardian_name.trim(),
      guardian_phone: form.guardian_phone.trim(),
      guardian_email: form.guardian_email.trim() || null,
      enrollment_date: form.enrollment_date || null,
      notes: form.notes.trim() || null,
    }

    let student: StudentRow
    try {
      const response = await api.post<ApiResponse<StudentRow>>('/students', payload)
      student = response.data.data
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setSaving(false)
        return
      }

      const parsed = parseApiError(err)
      const nextFieldErrors: StudentFieldErrors = {}
      for (const detail of parsed.errors) {
        const field = detail.field as StudentFormField | undefined
        if (field && field in fieldLabels && !nextFieldErrors[field]) {
          nextFieldErrors[field] = detail.message
        }
      }

      setFieldErrors(nextFieldErrors)
      setSaveError(
        parsed.errors.length > 0 && parsed.message === 'Validation error'
          ? 'Fix the highlighted fields and try again.'
          : parsed.message
      )
      setSaveErrorDetails(
        parsed.errors.length > 0
          ? parsed.errors.map((detail) => formatFieldError(detail.field, detail.message))
          : []
      )
      setSaving(false)
      return
    }

    if (discountForm.enabled && discountForm.value) {
      try {
        await api.post('/discounts/student', {
          student_id: student.id,
          value_type: discountForm.value_type,
          value: Number(discountForm.value),
          reason_text: discountForm.reason_text.trim() || null,
        })
      } catch (err) {
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          setSaving(false)
          return
        }
        console.error('Failed to create student discount:', err)
      }
    }

    setSaving(false)
    navigate(`/students/${student.id}`)
  }

  return (
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-4">
        New student
      </Typography>

      {saveError && (
        <Alert
          severity="error"
          className="mb-4"
          onClose={() => {
            setSaveError(null)
            setSaveErrorDetails([])
          }}
        >
          <div className="space-y-2">
            <div>{saveError}</div>
            {saveErrorDetails.length > 0 && (
              <ul className="list-disc pl-5 space-y-1">
                {saveErrorDetails.map((detail) => (
                  <li key={detail}>{detail}</li>
                ))}
              </ul>
            )}
          </div>
        </Alert>
      )}

      <div className="grid gap-4 max-w-[720px]">
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Input
            label="First name"
            value={form.first_name}
            onChange={(event) => setFormField('first_name', event.target.value)}
            error={fieldErrors.first_name}
            required
          />
          <Input
            label="Last name"
            value={form.last_name}
            onChange={(event) => setFormField('last_name', event.target.value)}
            error={fieldErrors.last_name}
            required
          />
          <Input
            label="Date of birth"
            type="date"
            value={form.date_of_birth}
            onChange={(event) => setFormField('date_of_birth', event.target.value)}
            error={fieldErrors.date_of_birth}
          />
          <Select
            value={form.gender}
            onChange={(event) => setFormField('gender', event.target.value as Gender)}
            label="Gender"
            error={fieldErrors.gender}
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
          </Select>
          <Select
            value={form.grade_id}
            onChange={(event) => setFormField('grade_id', event.target.value as string)}
            label="Grade"
            error={fieldErrors.grade_id}
            required
          >
            <option value="">Select grade</option>
            {(grades || []).map((grade) => (
              <option key={grade.id} value={String(grade.id)}>
                {grade.name}
              </option>
            ))}
          </Select>
          <Select
            value={form.transport_zone_id}
            onChange={(event) => setFormField('transport_zone_id', event.target.value as string)}
            label="Transport zone"
            error={fieldErrors.transport_zone_id}
          >
            <option value="">None</option>
            {(transportZones || []).map((zone) => (
              <option key={zone.id} value={String(zone.id)}>
                {zone.zone_name}
              </option>
            ))}
          </Select>
          <Input
            label="Enrollment date"
            type="date"
            value={form.enrollment_date}
            onChange={(event) => setFormField('enrollment_date', event.target.value)}
            error={fieldErrors.enrollment_date}
          />
        </div>
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">
          <Input
            label="Guardian name"
            value={form.guardian_name}
            onChange={(event) => setFormField('guardian_name', event.target.value)}
            error={fieldErrors.guardian_name}
            required
          />
          <Input
            label="Guardian phone"
            value={form.guardian_phone}
            onChange={(event) => setFormField('guardian_phone', event.target.value)}
            placeholder="+254..."
            error={fieldErrors.guardian_phone}
            required
          />
          <Input
            label="Guardian email"
            type="email"
            value={form.guardian_email}
            onChange={(event) => setFormField('guardian_email', event.target.value)}
            error={fieldErrors.guardian_email}
          />
        </div>
        <Textarea
          label="Notes"
          value={form.notes}
          onChange={(event) => setFormField('notes', event.target.value)}
          error={fieldErrors.notes}
          rows={3}
        />

        <div>
          <div className="flex items-center gap-2 mb-2">
            <Switch
              checked={discountForm.enabled}
              onChange={(event) =>
                setDiscountForm({ ...discountForm, enabled: event.target.checked })
              }
            />
            <span className="text-sm font-medium text-slate-700">Add student discount</span>
          </div>
          {discountForm.enabled && (
            <div className="mt-2 grid gap-4 grid-cols-[repeat(auto-fit,minmax(200px,1fr))]">
              <Select
                value={discountForm.value_type}
                onChange={(event) =>
                  setDiscountForm({
                    ...discountForm,
                    value_type: event.target.value as DiscountValueType,
                  })
                }
                label="Value type"
              >
                <option value="percentage">Percentage</option>
                <option value="fixed">Fixed</option>
              </Select>
              <Input
                label={discountForm.value_type === 'percentage' ? 'Percent' : 'Amount'}
                value={discountForm.value}
                onChange={(event) =>
                  setDiscountForm({ ...discountForm, value: event.target.value })
                }
                type="number"
              />
              <Input
                label="Reason (optional)"
                value={discountForm.reason_text}
                onChange={(event) =>
                  setDiscountForm({ ...discountForm, reason_text: event.target.value })
                }
              />
            </div>
          )}
        </div>

        <div className="flex gap-2 mt-2">
          <Button variant="outlined" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitCreate} disabled={saving}>
            {saving ? <Spinner size="small" /> : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  )
}
