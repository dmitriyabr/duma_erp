import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { isAccountant } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface FixedFeeRow {
  id: number
  fee_type: string
  display_name: string
  amount: number
  is_active: boolean
}

const emptyForm = {
  fee_type: '',
  display_name: '',
  amount: '',
  is_active: true,
}

export const FixedFeesPage = () => {
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const { data: rows, loading, error, refetch } = useApi<FixedFeeRow[]>('/terms/fixed-fees')
  const { execute: saveFee, loading: saving, error: saveError } = useApiMutation<FixedFeeRow>()

  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingFee, setEditingFee] = useState<FixedFeeRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const filteredRows = (rows || []).filter((row) => {
    if (statusFilter === 'all') {
      return true
    }
    return statusFilter === 'active' ? row.is_active : !row.is_active
  })

  const openCreate = () => {
    setEditingFee(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (fee: FixedFeeRow) => {
    setEditingFee(fee)
    setForm({
      fee_type: fee.fee_type,
      display_name: fee.display_name,
      amount: String(fee.amount),
      is_active: fee.is_active,
    })
    setDialogOpen(true)
  }

  const submitForm = async () => {
    const amountValue = Number(form.amount)

    const result = await saveFee(() =>
      editingFee
        ? api.put(`/terms/fixed-fees/${editingFee.id}`, {
            display_name: form.display_name,
            amount: amountValue,
            is_active: form.is_active,
          })
        : api.post('/terms/fixed-fees', {
            fee_type: form.fee_type,
            display_name: form.display_name,
            amount: amountValue,
          })
    )

    if (result) {
      setDialogOpen(false)
      refetch()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Fixed Fees
        </Typography>
        {!readOnly && (
          <Button variant="contained" onClick={openCreate}>
            New fee
          </Button>
        )}
      </div>

      <div className="flex gap-4 mb-4">
        <div className="min-w-[160px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </Select>
        </div>
      </div>

      {(error || saveError) && (
        <Alert severity="error" className="mb-4">
          {error || saveError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Fee type</TableHeaderCell>
              <TableHeaderCell>Display name</TableHeaderCell>
              <TableHeaderCell>Amount</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredRows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.fee_type}</TableCell>
                <TableCell>{row.display_name}</TableCell>
                <TableCell>{formatMoney(row.amount)}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={row.is_active ? 'Active' : 'Inactive'}
                    color={row.is_active ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell align="right">
                  {!readOnly && (
                    <Button size="small" variant="outlined" onClick={() => openEdit(row)}>
                      Edit
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!filteredRows.length && !loading && (
              <TableRow>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <Typography color="secondary">No fixed fees found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingFee ? 'Edit fixed fee' : 'Create fixed fee'}</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Fee type"
              value={form.fee_type}
              onChange={(e) => setForm({ ...form, fee_type: e.target.value })}
              required
              disabled={!!editingFee}
            />
            <Input
              label="Display name"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              required
            />
            <Input
              label="Amount"
              type="number"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              required
            />
            {editingFee && (
              <Select
                label="Status"
                value={form.is_active ? 'active' : 'inactive'}
                onChange={(e) => setForm({ ...form, is_active: e.target.value === 'active' })}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </Select>
            )}
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
