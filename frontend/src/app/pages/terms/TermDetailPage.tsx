import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Menu,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PriceSettingRow {
  grade: string
  school_fee_amount: number
}

interface TransportPricingRow {
  zone_id: number
  zone_name: string
  zone_code: string
  transport_fee_amount: number
}

interface GradeRow {
  id: number
  code: string
  name: string
}

interface TermDetail {
  id: number
  year: number
  term_number: number
  display_name: string
  status: 'Draft' | 'Active' | 'Closed'
  start_date?: string | null
  end_date?: string | null
  price_settings: PriceSettingRow[]
  transport_pricings: TransportPricingRow[]
}

interface GenerationResult {
  school_fee_invoices_created: number
  transport_invoices_created: number
  students_skipped: number
  total_students_processed: number
}

const statusColor = (status: TermDetail['status']) => {
  if (status === 'Active') return 'success'
  if (status === 'Closed') return 'default'
  return 'warning'
}

export const TermDetailPage = () => {
  const { termId } = useParams()
  const navigate = useNavigate()
  const resolvedId = termId ? Number(termId) : null
  const [term, setTerm] = useState<TermDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [grades, setGrades] = useState<GradeRow[]>([])

  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null)
  const [resultDialogOpen, setResultDialogOpen] = useState(false)
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [studentDialogOpen, setStudentDialogOpen] = useState(false)
  const [studentId, setStudentId] = useState('')

  const loadTerm = useCallback(async () => {
    if (!resolvedId) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<TermDetail>>(`/terms/${resolvedId}`)
      const termData = response.data.data
      setTerm({
        ...termData,
        price_settings: termData.price_settings.map((entry) => ({
          ...entry,
          school_fee_amount: Number(entry.school_fee_amount),
        })),
        transport_pricings: termData.transport_pricings.map((entry) => ({
          ...entry,
          transport_fee_amount: Number(entry.transport_fee_amount),
        })),
      })
    } catch {
      setError('Failed to load term.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  useEffect(() => {
    loadTerm()
  }, [loadTerm])

  useEffect(() => {
    const loadGrades = async () => {
      try {
        const response = await api.get<ApiResponse<GradeRow[]>>('/students/grades', {
          params: { include_inactive: true },
        })
        setGrades(response.data.data)
      } catch {
        // Ignore grade loading errors; fallback to codes in UI
      }
    }
    loadGrades()
  }, [])

  const gradeNameMap = new Map(grades.map((grade) => [grade.code, grade.name]))

  const handleActivate = async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      await api.post(`/terms/${resolvedId}/activate`)
      await loadTerm()
    } catch {
      setError('Failed to activate term.')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      await api.post(`/terms/${resolvedId}/close`)
      await loadTerm()
    } catch {
      setError('Failed to close term.')
    } finally {
      setLoading(false)
    }
  }

  const openMenu = (event: React.MouseEvent<HTMLButtonElement>) => {
    setMenuAnchor(event.currentTarget)
  }

  const closeMenu = () => {
    setMenuAnchor(null)
  }

  const showResult = (data: GenerationResult) => {
    setResult(data)
    setResultDialogOpen(true)
  }

  const generateAll = async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.post<ApiResponse<GenerationResult>>('/invoices/generate-term-invoices', {
        term_id: resolvedId,
      })
      showResult(response.data.data)
    } catch {
      setError('Failed to generate invoices.')
    } finally {
      setLoading(false)
      closeMenu()
    }
  }

  const generateSingle = async () => {
    if (!resolvedId) return
    const studentIdValue = Number(studentId)
    if (!studentIdValue) {
      setError('Enter student ID.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await api.post<ApiResponse<GenerationResult>>(
        '/invoices/generate-term-invoices/student',
        {
          term_id: resolvedId,
          student_id: studentIdValue,
        }
      )
      showResult(response.data.data)
      setStudentDialogOpen(false)
      setStudentId('')
    } catch {
      setError('Failed to generate invoices.')
    } finally {
      setLoading(false)
    }
  }

  if (!term) {
    return (
      <Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {term.display_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {formatDate(term.start_date)} → {formatDate(term.end_date)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip label={term.status} color={statusColor(term.status)} />
          <Button variant="outlined" onClick={() => navigate(`/billing/terms/${term.id}/edit`)}>
            Edit
          </Button>
          {term.status !== 'Active' && term.status !== 'Closed' ? (
            <Button variant="contained" onClick={handleActivate} disabled={loading}>
              Activate
            </Button>
          ) : null}
          {term.status === 'Active' ? (
            <Button variant="contained" color="warning" onClick={handleClose} disabled={loading}>
              Close
            </Button>
          ) : null}
          <Button variant="outlined" onClick={openMenu}>
            Generate invoices
          </Button>
        </Box>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ mt: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          School fees by grade
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Grade</TableCell>
              <TableCell align="right">Amount</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {term.price_settings.map((entry) => (
              <TableRow key={entry.grade}>
                <TableCell>{gradeNameMap.get(entry.grade) ?? entry.grade}</TableCell>
                <TableCell align="right">{formatMoney(entry.school_fee_amount)}</TableCell>
              </TableRow>
            ))}
            {!term.price_settings.length ? (
              <TableRow>
                <TableCell colSpan={2} align="center">
                  No pricing data
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Box>

      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Transport fees by zone
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Zone</TableCell>
              <TableCell>Code</TableCell>
              <TableCell align="right">Amount</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {term.transport_pricings.map((entry) => (
              <TableRow key={entry.zone_id}>
                <TableCell>{entry.zone_name}</TableCell>
                <TableCell>{entry.zone_code}</TableCell>
                <TableCell align="right">{formatMoney(entry.transport_fee_amount)}</TableCell>
              </TableRow>
            ))}
            {!term.transport_pricings.length ? (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  No transport pricing data
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Box>

      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
        <MenuItem onClick={generateAll}>All students</MenuItem>
        <MenuItem
          onClick={() => {
            setStudentDialogOpen(true)
            closeMenu()
          }}
        >
          Single student
        </MenuItem>
      </Menu>

      <Dialog open={studentDialogOpen} onClose={() => setStudentDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Generate invoices for student</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Student ID"
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            type="number"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStudentDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={generateSingle} disabled={loading}>
            Generate
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={resultDialogOpen} onClose={() => setResultDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Invoice generation result</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 1, mt: 1 }}>
          <Typography>School fee invoices: {result?.school_fee_invoices_created ?? 0}</Typography>
          <Typography>Transport invoices: {result?.transport_invoices_created ?? 0}</Typography>
          <Typography>Students skipped: {result?.students_skipped ?? 0}</Typography>
          <Typography>Total processed: {result?.total_students_processed ?? 0}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResultDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
