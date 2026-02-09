import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { api } from '../../services/api'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApiMutation } from '../../hooks/useApi'
import type { ApiResponse } from '../../types/api'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Switch } from '../../components/ui/Switch'
import { Spinner } from '../../components/ui/Spinner'

type Gender = 'male' | 'female'

type DiscountValueType = 'fixed' | 'percentage'

interface StudentRow {
  id: number
  student_number: string
  full_name: string
}

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

  const { execute: createStudent, loading: saving, error: saveError } = useApiMutation<StudentRow>()

  const submitCreate = async () => {
    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      date_of_birth: form.date_of_birth || null,
      gender: form.gender,
      grade_id: Number(form.grade_id),
      transport_zone_id: form.transport_zone_id ? Number(form.transport_zone_id) : null,
      guardian_name: form.guardian_name.trim(),
      guardian_phone: form.guardian_phone.trim(),
      guardian_email: form.guardian_email.trim() || null,
      enrollment_date: form.enrollment_date || null,
      notes: form.notes.trim() || null,
    }

    const student = await createStudent(() =>
      api.post<ApiResponse<StudentRow>>('/students', payload)
    )
    if (!student) return

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
          return
        }
        console.error('Failed to create student discount:', err)
      }
    }

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
        <Alert severity="error" className="mb-4" onClose={() => {}}>
          {saveError}
        </Alert>
      )}

      <div className="grid gap-4 max-w-[720px]">
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Input
            label="First name"
            value={form.first_name}
            onChange={(event) => setForm({ ...form, first_name: event.target.value })}
            required
          />
          <Input
            label="Last name"
            value={form.last_name}
            onChange={(event) => setForm({ ...form, last_name: event.target.value })}
            required
          />
          <Input
            label="Date of birth"
            type="date"
            value={form.date_of_birth}
            onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })}
          />
          <Select
            value={form.gender}
            onChange={(event) => setForm({ ...form, gender: event.target.value as Gender })}
            label="Gender"
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
          </Select>
          <Select
            value={form.grade_id}
            onChange={(event) => setForm({ ...form, grade_id: event.target.value as string })}
            label="Grade"
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
            onChange={(event) => setForm({ ...form, transport_zone_id: event.target.value as string })}
            label="Transport zone"
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
            onChange={(event) => setForm({ ...form, enrollment_date: event.target.value })}
          />
        </div>
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">
          <Input
            label="Guardian name"
            value={form.guardian_name}
            onChange={(event) => setForm({ ...form, guardian_name: event.target.value })}
            required
          />
          <Input
            label="Guardian phone"
            value={form.guardian_phone}
            onChange={(event) => setForm({ ...form, guardian_phone: event.target.value })}
            placeholder="+254..."
            required
          />
          <Input
            label="Guardian email"
            type="email"
            value={form.guardian_email}
            onChange={(event) => setForm({ ...form, guardian_email: event.target.value })}
          />
        </div>
        <Textarea
          label="Notes"
          value={form.notes}
          onChange={(event) => setForm({ ...form, notes: event.target.value })}
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
