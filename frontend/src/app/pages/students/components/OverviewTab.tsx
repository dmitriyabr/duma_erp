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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { api } from '../../../services/api'
import { useApi, useApiMutation } from '../../../hooks/useApi'
import { formatDate, formatMoney } from '../../../utils/format'
import type {
  DiscountValueType,
  PaginatedResponse,
  StudentDiscountResponse,
  StudentResponse,
} from '../types'
import { parseNumber } from '../types'

interface OverviewTabProps {
  student: StudentResponse
  studentId: number
  onError: (message: string) => void
}

export const OverviewTab = ({ student, studentId, onError }: OverviewTabProps) => {
  const discountsUrl = useMemo(
    () => `/discounts/student?student_id=${studentId}&include_inactive=true&limit=200&page=1`,
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
    <Box sx={{ display: 'grid', gap: 2 }}>
      <Box
        sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}
      >
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Personal
          </Typography>
          <Typography>{student.full_name}</Typography>
          <Typography variant="body2">Gender: {student.gender}</Typography>
          <Typography variant="body2">
            Date of birth: {student.date_of_birth ? formatDate(student.date_of_birth) : '—'}
          </Typography>
          <Typography variant="body2">
            Enrollment date: {student.enrollment_date ? formatDate(student.enrollment_date) : '—'}
          </Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Guardian
          </Typography>
          <Typography>{student.guardian_name}</Typography>
          <Typography variant="body2">{student.guardian_phone}</Typography>
          <Typography variant="body2">{student.guardian_email ?? '—'}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Notes
          </Typography>
          <Typography variant="body2">{student.notes ?? '—'}</Typography>
        </Box>
      </Box>
      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
          p: 2,
          maxWidth: 520,
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1">School Fees Discount</Typography>
          <Button size="small" onClick={() => openStudentDiscountDialog()}>
            {studentDiscounts.some((discount) => discount.is_active) ? 'Add another' : 'Set discount'}
          </Button>
        </Box>
        {studentDiscounts.length ? (
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <TableRow>
                <TableCell>Value</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
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
                    <Button size="small" onClick={() => openStudentDiscountDialog(discount)}>
                      Edit
                    </Button>
                    <Button size="small" onClick={() => toggleStudentDiscountStatus(discount)}>
                      {discount.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            No discount set
          </Typography>
        )}
      </Box>

      <Dialog
        open={studentDiscountDialogOpen}
        onClose={() => setStudentDiscountDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{editingStudentDiscount ? 'Edit discount' : 'New discount'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Value type</InputLabel>
            <Select
              value={studentDiscountForm.value_type}
              label="Value type"
              onChange={(event) =>
                setStudentDiscountForm({
                  ...studentDiscountForm,
                  value_type: event.target.value as DiscountValueType,
                })
              }
            >
              <MenuItem value="percentage">Percentage</MenuItem>
              <MenuItem value="fixed">Fixed</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Value"
            type="number"
            value={studentDiscountForm.value}
            onChange={(event) =>
              setStudentDiscountForm({ ...studentDiscountForm, value: event.target.value })
            }
          />
          <TextField
            label="Reason"
            value={studentDiscountForm.reason_text}
            onChange={(event) =>
              setStudentDiscountForm({ ...studentDiscountForm, reason_text: event.target.value })
            }
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStudentDiscountDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitStudentDiscount} disabled={busy}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
