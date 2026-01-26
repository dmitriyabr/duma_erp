import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../services/api'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PurposeRow {
  id: number
  name: string
  is_active: boolean
}

const emptyForm = { name: '' }

export const PaymentPurposesPage = () => {
  const [rows, setRows] = useState<PurposeRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingPurpose, setEditingPurpose] = useState<PurposeRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const fetchPurposes = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<PurposeRow[]>>('/procurement/payment-purposes', {
        params: { include_inactive: true },
      })
      setRows(response.data.data)
    } catch {
      setError('Failed to load payment purposes.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPurposes()
  }, [fetchPurposes])

  const openCreate = () => {
    setEditingPurpose(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (purpose: PurposeRow) => {
    setEditingPurpose(purpose)
    setForm({ name: purpose.name })
    setDialogOpen(true)
  }

  const submitForm = async () => {
    if (!form.name.trim()) {
      setError('Enter purpose name.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      if (editingPurpose) {
        await api.put(`/procurement/payment-purposes/${editingPurpose.id}`, {
          name: form.name.trim(),
        })
      } else {
        await api.post('/procurement/payment-purposes', {
          name: form.name.trim(),
        })
      }
      setDialogOpen(false)
      await fetchPurposes()
    } catch {
      setError('Failed to save payment purpose.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Payment purposes
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New purpose
        </Button>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.name}</TableCell>
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
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={3} align="center">
                No payment purposes found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingPurpose ? 'Edit purpose' : 'Create purpose'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Name"
            value={form.name}
            onChange={(event) => setForm({ name: event.target.value })}
            fullWidth
            required
          />
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
