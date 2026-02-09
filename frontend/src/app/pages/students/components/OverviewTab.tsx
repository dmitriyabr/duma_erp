import { useMemo, useState } from 'react'
import { useAuth } from '../../../auth/AuthContext'
import { api } from '../../../services/api'
import { canManageStudents, isAccountant } from '../../../utils/permissions'
import { SECONDARY_LIST_LIMIT } from '../../../constants/pagination'
import { useApi, useApiMutation } from '../../../hooks/useApi'
import { formatDate, formatMoney } from '../../../utils/format'
import type {
  DiscountValueType,
  PaginatedResponse,
  StudentDiscountResponse,
  StudentResponse,
} from '../types'
import { parseNumber } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Button } from '../../../components/ui/Button'
import { Chip } from '../../../components/ui/Chip'
import { Input } from '../../../components/ui/Input'
import { Select } from '../../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../../components/ui/Dialog'
import { Spinner } from '../../../components/ui/Spinner'

interface OverviewTabProps {
  student: StudentResponse
  studentId: number
  onError: (message: string) => void
}

export const OverviewTab = ({ student, studentId, onError }: OverviewTabProps) => {
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const canManage = canManageStudents(user)
  const discountsUrl = useMemo(
    () => `/discounts/student?student_id=${studentId}&include_inactive=true&limit=${SECONDARY_LIST_LIMIT}&page=1`,
    [studentId]
  )
  const { data: discountsData, refetch } = useApi<PaginatedResponse<StudentDiscountResponse>>(discountsUrl)
  const { execute: saveDiscount, loading, error: saveError } = useApiMutation()
  const { execute: toggleDiscount, loading: toggling, error: toggleError } = useApiMutation()
  const busy = loading || toggling

  const [studentDiscountDialogOpen, setStudentDiscountDialogOpen] = useState(false)
  const [editingStudentDiscount, setEditingStudentDiscount] =
    useState<StudentDiscountResponse | null>(null)
  const [studentDiscountForm, setStudentDiscountForm] = useState({
    value_type: 'percentage' as DiscountValueType,
    value: '',
    reason_text: '',
  })

  const studentDiscounts = discountsData?.items || []

  if (saveError || toggleError) {
    onError(saveError || toggleError || 'Failed to update student discount.')
  }

  const openStudentDiscountDialog = (discount?: StudentDiscountResponse) => {
    setEditingStudentDiscount(discount ?? null)
    setStudentDiscountForm({
      value_type: (discount?.value_type as DiscountValueType) ?? 'percentage',
      value: discount ? String(discount.value) : '',
      reason_text: discount?.reason_text ?? '',
    })
    setStudentDiscountDialogOpen(true)
  }

  const submitStudentDiscount = async () => {
    const result = await saveDiscount(() =>
      editingStudentDiscount
        ? api.patch(`/discounts/student/${editingStudentDiscount.id}`, {
            value_type: studentDiscountForm.value_type,
            value: Number(studentDiscountForm.value),
            reason_text: studentDiscountForm.reason_text.trim() || null,
          })
        : api.post('/discounts/student', {
            student_id: studentId,
            value_type: studentDiscountForm.value_type,
            value: Number(studentDiscountForm.value),
            reason_text: studentDiscountForm.reason_text.trim() || null,
          })
    )

    if (result) {
      setStudentDiscountDialogOpen(false)
      refetch()
    }
  }

  const toggleStudentDiscountStatus = async (discount: StudentDiscountResponse) => {
    const result = await toggleDiscount(() =>
      api.patch(`/discounts/student/${discount.id}`, {
        is_active: !discount.is_active,
      })
    )

    if (result) {
      refetch()
    }
  }

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Personal
          </Typography>
          <Typography>{student.full_name}</Typography>
          <Typography variant="body2" className="mt-1">Gender: {student.gender}</Typography>
          <Typography variant="body2">
            Date of birth: {student.date_of_birth ? formatDate(student.date_of_birth) : '—'}
          </Typography>
          <Typography variant="body2">
            Enrollment date: {student.enrollment_date ? formatDate(student.enrollment_date) : '—'}
          </Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Guardian
          </Typography>
          <Typography>{student.guardian_name}</Typography>
          <Typography variant="body2" className="mt-1">{student.guardian_phone}</Typography>
          <Typography variant="body2">{student.guardian_email ?? '—'}</Typography>
        </div>
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Notes
          </Typography>
          <Typography variant="body2">{student.notes ?? '—'}</Typography>
        </div>
      </div>
      <div className="border border-slate-200 rounded-lg p-4 max-w-[520px]">
        <div className="flex justify-between items-center mb-2">
          <Typography variant="subtitle1">School Fees Discount</Typography>
          {canManage && !readOnly && (
            <Button size="small" onClick={() => openStudentDiscountDialog()}>
              {studentDiscounts.some((discount) => discount.is_active) ? 'Add another' : 'Set discount'}
            </Button>
          )}
        </div>
        {studentDiscounts.length ? (
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mt-2">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Value</TableHeaderCell>
                  <TableHeaderCell>Reason</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell align="right">Actions</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {studentDiscounts.map((discount) => (
                  <TableRow key={discount.id}>
                    <TableCell>
                      {discount.value_type === 'percentage'
                        ? `${discount.value}%`
                        : formatMoney(parseNumber(discount.value))}
                    </TableCell>
                    <TableCell>{discount.reason_name ?? discount.reason_text ?? '—'}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={discount.is_active ? 'Active' : 'Inactive'}
                        color={discount.is_active ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      {canManage && !readOnly && (
                        <div className="flex gap-2 justify-end">
                          <Button size="small" onClick={() => openStudentDiscountDialog(discount)}>
                            Edit
                          </Button>
                          <Button size="small" variant="outlined" onClick={() => toggleStudentDiscountStatus(discount)}>
                            {discount.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <Typography variant="body2" color="secondary" className="mt-2">
            No discount set
          </Typography>
        )}
      </div>

      <Dialog
        open={studentDiscountDialogOpen}
        onClose={() => setStudentDiscountDialogOpen(false)}
        maxWidth="sm"
      >
        <DialogCloseButton onClose={() => setStudentDiscountDialogOpen(false)} />
        <DialogTitle>{editingStudentDiscount ? 'Edit discount' : 'New discount'}</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Select
              value={studentDiscountForm.value_type}
              onChange={(e) =>
                setStudentDiscountForm({
                  ...studentDiscountForm,
                  value_type: e.target.value as DiscountValueType,
                })
              }
              label="Value type"
            >
              <option value="percentage">Percentage</option>
              <option value="fixed">Fixed</option>
            </Select>
            <Input
              label="Value"
              type="number"
              value={studentDiscountForm.value}
              onChange={(e) =>
                setStudentDiscountForm({ ...studentDiscountForm, value: e.target.value })
              }
            />
            <Input
              label="Reason"
              value={studentDiscountForm.reason_text}
              onChange={(e) =>
                setStudentDiscountForm({ ...studentDiscountForm, reason_text: e.target.value })
              }
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setStudentDiscountDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitStudentDiscount} disabled={busy}>
            {busy ? <Spinner size="small" /> : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
