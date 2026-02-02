import { useState } from 'react'
import { useAuth } from '../../../auth/AuthContext'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import { isAccountant } from '../../../utils/permissions'
import { api } from '../../../services/api'
import { useApiMutation } from '../../../hooks/useApi'
import { formatMoney } from '../../../utils/format'
import type { Gender, GradeOption, StudentBalance, StudentResponse, TransportZoneOption } from '../types'
import { parseNumber } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Button } from '../../../components/ui/Button'
import { Chip } from '../../../components/ui/Chip'
import { Input } from '../../../components/ui/Input'
import { Select } from '../../../components/ui/Select'
import { Textarea } from '../../../components/ui/Textarea'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../../components/ui/Dialog'
import { Spinner } from '../../../components/ui/Spinner'

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
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const { execute: updateStudent, loading, error: updateError } = useApiMutation()
  const { execute: toggleStatus, loading: toggling, error: toggleError } = useApiMutation()

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
    const result = await updateStudent(() =>
      api.patch(`/students/${student.id}`, {
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
    )

    if (result) {
      setEditDialogOpen(false)
      onStudentUpdate()
    } else if (updateError) {
      onError('Failed to update student.')
    }
  }

  const requestToggleActive = () => {
    setConfirmState({ open: true, nextActive: student.status !== 'active' })
  }

  const confirmToggleActive = async () => {
    const nextActive = confirmState.nextActive
    setConfirmState({ open: false })

    const result = await toggleStatus(() =>
      nextActive
        ? api.post(`/students/${student.id}/activate`)
        : api.post(`/students/${student.id}/deactivate`)
    )

    if (result) {
      onStudentUpdate()
    } else if (toggleError) {
      onError(`Failed to ${nextActive ? 'activate' : 'deactivate'} student.`)
    }
  }

  const netBalance = balance != null ? parseNumber(balance.balance) : -debt

  return (
    <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
      <div>
        <Typography variant="h4">
          {student.full_name}
        </Typography>
        <Typography variant="body2" color="secondary" className="mt-1">
          Student #{student.student_number} · {student.grade_name ?? 'No grade'}
        </Typography>
      </div>
      <div className="flex gap-2 flex-wrap">
        <Chip
          label={student.status === 'active' ? 'Active' : 'Inactive'}
          color={student.status === 'active' ? 'success' : 'default'}
        />
        <Chip
          label={`Balance ${formatMoney(netBalance)}`}
          color={netBalance > 0 ? 'success' : netBalance < 0 ? 'error' : 'default'}
          variant={netBalance !== 0 ? 'filled' : 'outlined'}
        />
        {!readOnly && (
          <>
            <Button variant="outlined" onClick={openEdit}>
              Edit
            </Button>
            <Button variant="outlined" onClick={requestToggleActive}>
              {student.status === 'active' ? 'Deactivate' : 'Activate'}
            </Button>
          </>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setEditDialogOpen(false)} />
        <DialogTitle>Edit student</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="First name"
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
              />
              <Input
                label="Last name"
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
              />
              <Input
                label="Date of birth"
                type="date"
                value={editForm.date_of_birth}
                onChange={(e) => setEditForm({ ...editForm, date_of_birth: e.target.value })}
              />
              <Select
                value={editForm.gender}
                onChange={(e) => setEditForm({ ...editForm, gender: e.target.value as Gender })}
                label="Gender"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </Select>
              <Select
                value={editForm.grade_id}
                onChange={(e) => setEditForm({ ...editForm, grade_id: e.target.value })}
                label="Grade"
              >
                {grades.map((grade) => (
                  <option key={grade.id} value={String(grade.id)}>
                    {grade.name}
                  </option>
                ))}
              </Select>
              <Select
                value={editForm.transport_zone_id}
                onChange={(e) => setEditForm({ ...editForm, transport_zone_id: e.target.value })}
                label="Transport zone"
              >
                <option value="">None</option>
                {transportZones.map((zone) => (
                  <option key={zone.id} value={String(zone.id)}>
                    {zone.zone_name}
                  </option>
                ))}
              </Select>
              <Input
                label="Enrollment date"
                type="date"
                value={editForm.enrollment_date}
                onChange={(e) => setEditForm({ ...editForm, enrollment_date: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Guardian name"
                value={editForm.guardian_name}
                onChange={(e) => setEditForm({ ...editForm, guardian_name: e.target.value })}
              />
              <Input
                label="Guardian phone"
                value={editForm.guardian_phone}
                onChange={(e) => setEditForm({ ...editForm, guardian_phone: e.target.value })}
              />
              <Input
                label="Guardian email"
                value={editForm.guardian_email}
                onChange={(e) => setEditForm({ ...editForm, guardian_email: e.target.value })}
              />
            </div>
            <Textarea
              label="Notes"
              value={editForm.notes}
              onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setEditDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={saveStudent} disabled={loading || toggling}>
            {loading || toggling ? <Spinner size="small" /> : 'Save'}
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
    </div>
  )
}
