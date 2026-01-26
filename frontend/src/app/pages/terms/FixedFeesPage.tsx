import {
  Alert,
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
import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'

interface FixedFeeRow {
  id: number
  fee_type: string
  display_name: string
  amount: number
  is_active: boolean
}

interface ApiResponse<T> {
  success: boolean
  data: T
}

const emptyForm = {
  fee_type: '',
  display_name: '',
  amount: '',
  is_active: true,
}

export const FixedFeesPage = () => {
  const [rows, setRows] = useState<FixedFeeRow[]>([])
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingFee, setEditingFee] = useState<FixedFeeRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const fetchFees = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<FixedFeeRow[]>>('/terms/fixed-fees')
      setRows(response.data.data)
    } catch (err) {
      setError('Failed to load fixed fees.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFees()
  }, [])

  const filteredRows = rows.filter((row) => {
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
    setLoading(true)
    setError(null)
    const amountValue = Number(form.amount)
    try {
      if (editingFee) {
        await api.put(`/terms/fixed-fees/${editingFee.id}`, {
          display_name: form.display_name,
          amount: amountValue,
          is_active: form.is_active,
        })
      } else {
        await api.post('/terms/fixed-fees', {
          fee_type: form.fee_type,
          display_name: form.display_name,
          amount: amountValue,
        })
      }
      setDialogOpen(false)
      await fetchFees()
    } catch (err) {
      setError('Failed to save fixed fee.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Fixed Fees
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New fee
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => setStatusFilter(event.target.value as 'all' | 'active' | 'inactive')}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="inactive">Inactive</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Fee type</TableCell>
            <TableCell>Display name</TableCell>
            <TableCell>Amount</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => openEdit(row)}>
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!filteredRows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={5} align="center">
                No fixed fees found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingFee ? 'Edit fixed fee' : 'Create fixed fee'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Fee type"
            value={form.fee_type}
            onChange={(event) => setForm({ ...form, fee_type: event.target.value })}
            fullWidth
            required
            disabled={!!editingFee}
          />
          <TextField
            label="Display name"
            value={form.display_name}
            onChange={(event) => setForm({ ...form, display_name: event.target.value })}
            fullWidth
            required
          />
          <TextField
            label="Amount"
            value={form.amount}
            onChange={(event) => setForm({ ...form, amount: event.target.value })}
            fullWidth
            type="number"
            required
          />
          {editingFee ? (
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={form.is_active ? 'active' : 'inactive'}
                label="Status"
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.value === 'active' })
                }
              >
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitForm} disabled={loading}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
