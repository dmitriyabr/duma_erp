import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import { api } from '../../../services/api'
import { formatMoney } from '../../../utils/format'
import type { Gender, GradeOption, StudentBalance, StudentResponse, TransportZoneOption } from '../types'
import { parseNumber } from '../types'

interface StudentHeaderProps {
  student: StudentResponse
  balance: StudentBalance | null
  debt: number
  grades: GradeOption[]
  transportZones: TransportZoneOption[]
  onStudentUpdate: () => void
  onError: (message: string) => void
}

export const StudentHeader = ({
  student,
  balance,
  debt,
  grades,
  transportZones,
  onStudentUpdate,
  onError,
}: StudentHeaderProps) => {
  const [loading, setLoading] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editForm, setEditForm] = useState({
    first_name: student.first_name,
    last_name: student.last_name,
    date_of_birth: student.date_of_birth ?? '',
    gender: student.gender,
    grade_id: String(student.grade_id),
    transport_zone_id: student.transport_zone_id ? String(student.transport_zone_id) : '',
    guardian_name: student.guardian_name,
    guardian_phone: student.guardian_phone,
    guardian_email: student.guardian_email ?? '',
    enrollment_date: student.enrollment_date ?? '',
    notes: student.notes ?? '',
  })
  const [confirmState, setConfirmState] = useState<{
    open: boolean
    nextActive?: boolean
  }>({ open: false })

  const openEdit = () => {
    setEditForm({
      first_name: student.first_name,
      last_name: student.last_name,
      date_of_birth: student.date_of_birth ?? '',
      gender: student.gender,
      grade_id: String(student.grade_id),
      transport_zone_id: student.transport_zone_id ? String(student.transport_zone_id) : '',
      guardian_name: student.guardian_name,
      guardian_phone: student.guardian_phone,
      guardian_email: student.guardian_email ?? '',
      enrollment_date: student.enrollment_date ?? '',
      notes: student.notes ?? '',
    })
    setEditDialogOpen(true)
  }

  const saveStudent = async () => {
    setLoading(true)
    try {
      await api.patch(`/students/${student.id}`, {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        date_of_birth: editForm.date_of_birth || null,
        gender: editForm.gender,
        grade_id: Number(editForm.grade_id),
        transport_zone_id: editForm.transport_zone_id ? Number(editForm.transport_zone_id) : null,
        guardian_name: editForm.guardian_name.trim(),
        guardian_phone: editForm.guardian_phone.trim(),
        guardian_email: editForm.guardian_email.trim() || null,
        enrollment_date: editForm.enrollment_date || null,
        notes: editForm.notes.trim() || null,
      })
      setEditDialogOpen(false)
      onStudentUpdate()
    } catch {
      onError('Failed to update student.')
    } finally {
      setLoading(false)
    }
  }

  const requestToggleActive = () => {
    setConfirmState({ open: true, nextActive: student.status !== 'active' })
  }

  const confirmToggleActive = async () => {
    setConfirmState({ open: false })
    setLoading(true)
    try {
      if (confirmState.nextActive) {
        await api.post(`/students/${student.id}/activate`)
      } else {
        await api.post(`/students/${student.id}/deactivate`)
      }
      onStudentUpdate()
    } catch {
      onError(`Failed to ${confirmState.nextActive ? 'activate' : 'deactivate'} student.`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          {student.full_name}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Student #{student.student_number} · {student.grade_name ?? 'No grade'}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Chip
          label={student.status === 'active' ? 'Active' : 'Inactive'}
          color={student.status === 'active' ? 'success' : 'default'}
        />
        <Chip
          label={`Balance ${balance != null ? formatMoney(parseNumber(balance.available_balance)) : '—'}`}
          color={
            balance != null && parseNumber(balance.available_balance) < 0 ? 'warning' : 'success'
          }
        />
        <Button variant="outlined" onClick={openEdit}>
          Edit
        </Button>
        <Button variant="outlined" onClick={requestToggleActive}>
          {student.status === 'active' ? 'Deactivate' : 'Activate'}
        </Button>
      </Box>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Edit student</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <Box
            sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}
          >
            <TextField
              label="First name"
              value={editForm.first_name}
              onChange={(event) => setEditForm({ ...editForm, first_name: event.target.value })}
            />
            <TextField
              label="Last name"
              value={editForm.last_name}
              onChange={(event) => setEditForm({ ...editForm, last_name: event.target.value })}
            />
            <TextField
              label="Date of birth"
              type="date"
              value={editForm.date_of_birth}
              onChange={(event) => setEditForm({ ...editForm, date_of_birth: event.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            <FormControl>
              <InputLabel>Gender</InputLabel>
              <Select
                value={editForm.gender}
                label="Gender"
                onChange={(event) => setEditForm({ ...editForm, gender: event.target.value as Gender })}
              >
                <MenuItem value="male">Male</MenuItem>
                <MenuItem value="female">Female</MenuItem>
              </Select>
            </FormControl>
            <FormControl>
              <InputLabel>Grade</InputLabel>
              <Select
                value={editForm.grade_id}
                label="Grade"
                onChange={(event) => setEditForm({ ...editForm, grade_id: event.target.value })}
              >
                {grades.map((grade) => (
                  <MenuItem key={grade.id} value={String(grade.id)}>
                    {grade.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <InputLabel>Transport zone</InputLabel>
              <Select
                value={editForm.transport_zone_id}
                label="Transport zone"
                onChange={(event) => setEditForm({ ...editForm, transport_zone_id: event.target.value })}
              >
                <MenuItem value="">None</MenuItem>
                {transportZones.map((zone) => (
                  <MenuItem key={zone.id} value={String(zone.id)}>
                    {zone.zone_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Enrollment date"
              type="date"
              value={editForm.enrollment_date}
              onChange={(event) => setEditForm({ ...editForm, enrollment_date: event.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Box>
          <Box
            sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}
          >
            <TextField
              label="Guardian name"
              value={editForm.guardian_name}
              onChange={(event) => setEditForm({ ...editForm, guardian_name: event.target.value })}
            />
            <TextField
              label="Guardian phone"
              value={editForm.guardian_phone}
              onChange={(event) => setEditForm({ ...editForm, guardian_phone: event.target.value })}
            />
            <TextField
              label="Guardian email"
              value={editForm.guardian_email}
              onChange={(event) => setEditForm({ ...editForm, guardian_email: event.target.value })}
            />
          </Box>
          <TextField
            label="Notes"
            value={editForm.notes}
            onChange={(event) => setEditForm({ ...editForm, notes: event.target.value })}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={saveStudent} disabled={loading}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirm Toggle Dialog */}
      <ConfirmDialog
        open={confirmState.open}
        title={`${confirmState.nextActive ? 'Activate' : 'Deactivate'} student`}
        description={
          confirmState.nextActive
            ? 'Activate this student?'
            : debt > 0
              ? `Student has outstanding balance (${formatMoney(debt)}). Deactivate anyway?`
              : 'Deactivate this student?'
        }
        confirmLabel={confirmState.nextActive ? 'Activate' : 'Deactivate'}
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={confirmToggleActive}
      />
    </Box>
  )
}
