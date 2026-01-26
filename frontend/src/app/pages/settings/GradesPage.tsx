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
import { useEffect, useState } from 'react'
import { api } from '../../services/api'

interface GradeRow {
  id: number
  code: string
  name: string
  display_order: number
  is_active: boolean
}

interface ApiResponse<T> {
  success: boolean
  data: T
}

const emptyForm = {
  code: '',
  name: '',
  display_order: 0,
}

export const GradesPage = () => {
  const [rows, setRows] = useState<GradeRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingGrade, setEditingGrade] = useState<GradeRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const fetchGrades = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<GradeRow[]>>('/students/grades')
      const sorted = [...response.data.data].sort(
        (a, b) => a.display_order - b.display_order
      )
      setRows(sorted)
    } catch (err) {
      setError('Failed to load grades.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGrades()
  }, [])

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
    setLoading(true)
    setError(null)
    try {
      if (editingGrade) {
        await api.patch(`/students/grades/${editingGrade.id}`, {
          code: form.code,
          name: form.name,
        })
      } else {
        await api.post('/students/grades', {
          code: form.code,
          name: form.name,
          display_order: Number(form.display_order),
        })
      }
      setDialogOpen(false)
      await fetchGrades()
    } catch (err) {
      setError('Failed to save grade.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Grades
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New grade
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
            <TableCell>Code</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => openEdit(row)}>
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={4} align="center">
                No grades found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingGrade ? 'Edit grade' : 'Create grade'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Code"
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value })}
            fullWidth
            required
          />
          <TextField
            label="Name"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            fullWidth
            required
          />
          <TextField
            label="Display order"
            value={form.display_order}
            onChange={(event) => setForm({ ...form, display_order: Number(event.target.value) })}
            fullWidth
            type="number"
            required
            disabled={!!editingGrade}
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
