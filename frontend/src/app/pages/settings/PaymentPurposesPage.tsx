import { useState } from 'react'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface PurposeRow {
  id: number
  name: string
  is_active: boolean
  purpose_type: 'expense' | 'fee'
}

const emptyForm: { name: string; purpose_type: 'expense' | 'fee' } = { name: '', purpose_type: 'expense' }

export const PaymentPurposesPage = () => {
  const { data: rows, loading, error, refetch } = useApi<PurposeRow[]>('/procurement/payment-purposes?include_inactive=true')
  const { execute: savePurpose, loading: saving, error: saveError } = useApiMutation<PurposeRow>()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingPurpose, setEditingPurpose] = useState<PurposeRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })
  const [validationError, setValidationError] = useState<string | null>(null)

  const openCreate = () => {
    setEditingPurpose(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (purpose: PurposeRow) => {
    setEditingPurpose(purpose)
    setForm({ name: purpose.name, purpose_type: purpose.purpose_type })
    setDialogOpen(true)
  }

  const submitForm = async () => {
    if (!form.name.trim()) {
      setValidationError('Enter purpose name.')
      return
    }
    const result = await savePurpose(() =>
      editingPurpose
        ? api.put(`/procurement/payment-purposes/${editingPurpose.id}`, {
            name: form.name.trim(),
            purpose_type: form.purpose_type,
          })
        : api.post('/procurement/payment-purposes', {
            name: form.name.trim(),
            purpose_type: form.purpose_type,
          })
    )

    if (result) {
      setDialogOpen(false)
      setValidationError(null)
      refetch()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Payment purposes
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New purpose
        </Button>
      </div>

      {(error || saveError || validationError) && (
        <Alert severity="error" className="mb-4">
          {error || saveError || validationError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(rows || []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.name}</TableCell>
                <TableCell className="capitalize">{row.purpose_type}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={row.is_active ? 'Active' : 'Inactive'}
                    color={row.is_active ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => openEdit(row)}>
                    Edit
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={4} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!rows?.length && !loading && (
              <TableRow>
                <td colSpan={4} className="px-4 py-8 text-center">
                  <Typography color="secondary">No purposes found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
        <DialogTitle>{editingPurpose ? 'Edit purpose' : 'Create purpose'}</DialogTitle>
        <DialogContent>
          <div className="mt-2 grid grid-cols-1 gap-4">
            <Input
              label="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            <Select
              label="Type"
              value={form.purpose_type}
              onChange={(e) => setForm({ ...form, purpose_type: e.target.value as 'expense' | 'fee' })}
              required
            >
              <option value="expense">Expense</option>
              <option value="fee">Fee</option>
            </Select>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitForm} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
