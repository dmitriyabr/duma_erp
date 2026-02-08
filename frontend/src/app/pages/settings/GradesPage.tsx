import { useMemo, useState } from 'react'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { api } from '../../services/api'
import { useApiMutation } from '../../hooks/useApi'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface GradeRow {
  id: number
  code: string
  name: string
  display_order: number
  is_active: boolean
}

const emptyForm = {
  code: '',
  name: '',
  display_order: 0,
}

export const GradesPage = () => {
  const { grades, loading, error, refetchGrades } = useReferencedData()
  const { execute: saveGrade, loading: saving, error: saveError } = useApiMutation<GradeRow>()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingGrade, setEditingGrade] = useState<GradeRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const rows = useMemo(
    () => [...grades].sort((a, b) => a.display_order - b.display_order),
    [grades]
  )

  const openCreate = () => {
    setEditingGrade(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (grade: GradeRow) => {
    setEditingGrade(grade)
    setForm({
      code: grade.code,
      name: grade.name,
      display_order: grade.display_order,
    })
    setDialogOpen(true)
  }

  const submitForm = async () => {
    const result = await saveGrade(() =>
      editingGrade
        ? api.patch(`/students/grades/${editingGrade.id}`, {
            code: form.code,
            name: form.name,
          })
        : api.post('/students/grades', {
            code: form.code,
            name: form.name,
            display_order: Number(form.display_order),
          })
    )

    if (result) {
      setDialogOpen(false)
      refetchGrades()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Grades
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New grade
        </Button>
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
              <TableHeaderCell>Code</TableHeaderCell>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.code}</TableCell>
                <TableCell>{row.name}</TableCell>
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
            {!rows.length && !loading && (
              <TableRow>
                <td colSpan={4} className="px-4 py-8 text-center">
                  <Typography color="secondary">No grades found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
        <DialogTitle>{editingGrade ? 'Edit grade' : 'Create grade'}</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Code"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
            />
            <Input
              label="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            <Input
              label="Display order"
              type="number"
              value={form.display_order}
              onChange={(e) => setForm({ ...form, display_order: Number(e.target.value) })}
              required
              disabled={!!editingGrade}
            />
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
