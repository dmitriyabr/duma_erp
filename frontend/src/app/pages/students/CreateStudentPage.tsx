import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { api } from '../../services/api'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApiMutation } from '../../hooks/useApi'
import type { ApiResponse } from '../../types/api'

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
    <Box>
      <Button onClick={() => navigate(-1)} sx={{ mb: 2 }}>
        Back
      </Button>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        New student
      </Typography>

      {saveError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {saveError}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gap: 2, maxWidth: 720 }}>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          <TextField
            label="First name"
            value={form.first_name}
            onChange={(event) => setForm({ ...form, first_name: event.target.value })}
            required
          />
          <TextField
            label="Last name"
            value={form.last_name}
            onChange={(event) => setForm({ ...form, last_name: event.target.value })}
            required
          />
          <TextField
            label="Date of birth"
            type="date"
            value={form.date_of_birth}
            onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })}
            InputLabelProps={{ shrink: true }}
          />
          <FormControl>
            <InputLabel>Gender</InputLabel>
            <Select
              value={form.gender}
              label="Gender"
              onChange={(event) => setForm({ ...form, gender: event.target.value as Gender })}
            >
              <MenuItem value="male">Male</MenuItem>
              <MenuItem value="female">Female</MenuItem>
            </Select>
          </FormControl>
          <FormControl>
            <InputLabel>Grade</InputLabel>
            <Select
              value={form.grade_id}
              label="Grade"
              onChange={(event) => setForm({ ...form, grade_id: event.target.value as string })}
            >
              {(grades || []).map((grade) => (
                <MenuItem key={grade.id} value={String(grade.id)}>
                  {grade.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl>
            <InputLabel>Transport zone</InputLabel>
            <Select
              value={form.transport_zone_id}
              label="Transport zone"
              onChange={(event) => setForm({ ...form, transport_zone_id: event.target.value as string })}
            >
              <MenuItem value="">None</MenuItem>
              {(transportZones || []).map((zone) => (
                <MenuItem key={zone.id} value={String(zone.id)}>
                  {zone.zone_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Enrollment date"
            type="date"
            value={form.enrollment_date}
            onChange={(event) => setForm({ ...form, enrollment_date: event.target.value })}
            InputLabelProps={{ shrink: true }}
          />
        </Box>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
          <TextField
            label="Guardian name"
            value={form.guardian_name}
            onChange={(event) => setForm({ ...form, guardian_name: event.target.value })}
            required
          />
          <TextField
            label="Guardian phone"
            value={form.guardian_phone}
            onChange={(event) => setForm({ ...form, guardian_phone: event.target.value })}
            placeholder="+254..."
            InputLabelProps={{ shrink: true }}
            required
          />
          <TextField
            label="Guardian email"
            value={form.guardian_email}
            onChange={(event) => setForm({ ...form, guardian_email: event.target.value })}
          />
        </Box>
        <TextField
          label="Notes"
          value={form.notes}
          onChange={(event) => setForm({ ...form, notes: event.target.value })}
          multiline
          minRows={2}
        />

        <Box>
          <FormControlLabel
            control={
              <Switch
                checked={discountForm.enabled}
                onChange={(event) =>
                  setDiscountForm({ ...discountForm, enabled: event.target.checked })
                }
              />
            }
            label="Add student discount"
          />
          {discountForm.enabled ? (
            <Box
              sx={{
                mt: 1,
                display: 'grid',
                gap: 2,
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              }}
            >
              <FormControl>
                <InputLabel>Value type</InputLabel>
                <Select
                  value={discountForm.value_type}
                  label="Value type"
                  onChange={(event) =>
                    setDiscountForm({
                      ...discountForm,
                      value_type: event.target.value as DiscountValueType,
                    })
                  }
                >
                  <MenuItem value="percentage">Percentage</MenuItem>
                  <MenuItem value="fixed">Fixed</MenuItem>
                </Select>
              </FormControl>
              <TextField
                label={discountForm.value_type === 'percentage' ? 'Percent' : 'Amount'}
                value={discountForm.value}
                onChange={(event) =>
                  setDiscountForm({ ...discountForm, value: event.target.value })
                }
                type="number"
              />
              <TextField
                label="Reason (optional)"
                value={discountForm.reason_text}
                onChange={(event) =>
                  setDiscountForm({ ...discountForm, reason_text: event.target.value })
                }
              />
            </Box>
          ) : null}
        </Box>

        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Button onClick={() => navigate(-1)}>Cancel</Button>
          <Button variant="contained" onClick={submitCreate} disabled={saving}>
            Save
          </Button>
        </Box>
      </Box>
    </Box>
  )
}
