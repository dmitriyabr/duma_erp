import { useState } from 'react'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { api } from '../../services/api'
import { useApiMutation } from '../../hooks/useApi'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

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
  const { transportZones, loading, error, refetchTransportZones } = useReferencedData()
  const { execute: saveZone, loading: saving, error: saveError } = useApiMutation<TransportZoneRow>()

  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingZone, setEditingZone] = useState<TransportZoneRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const filteredRows = transportZones.filter((row) => {
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
      refetchTransportZones()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Transport Zones
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New zone
        </Button>
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
              <TableHeaderCell>Zone name</TableHeaderCell>
              <TableHeaderCell>Zone code</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
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
            {!filteredRows.length && !loading && (
              <TableRow>
                <td colSpan={4} className="px-4 py-8 text-center">
                  <Typography color="secondary">No transport zones found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingZone ? 'Edit transport zone' : 'Create transport zone'}</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Zone name"
              value={form.zone_name}
              onChange={(e) => setForm({ ...form, zone_name: e.target.value })}
              required
            />
            <Input
              label="Zone code"
              value={form.zone_code}
              onChange={(e) => setForm({ ...form, zone_code: e.target.value })}
              required
            />
            {editingZone && (
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
