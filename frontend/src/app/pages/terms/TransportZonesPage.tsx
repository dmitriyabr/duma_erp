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
import { useState } from 'react'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'

interface TransportZoneRow {
  id: number
  zone_name: string
  zone_code: string
  is_active: boolean
}

const emptyForm = {
  zone_name: '',
  zone_code: '',
  is_active: true,
}

export const TransportZonesPage = () => {
  const { data: rows, loading, error, refetch } = useApi<TransportZoneRow[]>('/terms/transport-zones')
  const { execute: saveZone, loading: saving, error: saveError } = useApiMutation<TransportZoneRow>()

  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingZone, setEditingZone] = useState<TransportZoneRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const filteredRows = (rows || []).filter((row) => {
    if (statusFilter === 'all') {
      return true
    }
    return statusFilter === 'active' ? row.is_active : !row.is_active
  })

  const openCreate = () => {
    setEditingZone(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (zone: TransportZoneRow) => {
    setEditingZone(zone)
    setForm({
      zone_name: zone.zone_name,
      zone_code: zone.zone_code,
      is_active: zone.is_active,
    })
    setDialogOpen(true)
  }

  const submitForm = async () => {
    const result = await saveZone(() =>
      editingZone
        ? api.put(`/terms/transport-zones/${editingZone.id}`, {
            zone_name: form.zone_name,
            zone_code: form.zone_code,
            is_active: form.is_active,
          })
        : api.post('/terms/transport-zones', {
            zone_name: form.zone_name,
            zone_code: form.zone_code,
          })
    )

    if (result) {
      setDialogOpen(false)
      refetch()
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Transport Zones
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New zone
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

      {error || saveError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || saveError}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Zone name</TableCell>
            <TableCell>Zone code</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filteredRows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{row.zone_name}</TableCell>
              <TableCell>{row.zone_code}</TableCell>
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
              <TableCell colSpan={4} align="center">
                No transport zones found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingZone ? 'Edit transport zone' : 'Create transport zone'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Zone name"
            value={form.zone_name}
            onChange={(event) => setForm({ ...form, zone_name: event.target.value })}
            fullWidth
            required
          />
          <TextField
            label="Zone code"
            value={form.zone_code}
            onChange={(event) => setForm({ ...form, zone_code: event.target.value })}
            fullWidth
            required
          />
          {editingZone ? (
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
          <Button variant="contained" onClick={submitForm} disabled={saving}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
