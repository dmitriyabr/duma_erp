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
import { useState } from 'react'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'

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
    setForm({ name: purpose.name })
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
          })
        : api.post('/procurement/payment-purposes', {
            name: form.name.trim(),
          })
    )

    if (result) {
      setDialogOpen(false)
      setValidationError(null)
      refetch()
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

      {error || saveError || validationError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || saveError || validationError}
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
          {(rows || []).map((row) => (
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
          {!(rows || []).length && !loading ? (
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
          <Button variant="contained" onClick={submitForm} disabled={saving}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
