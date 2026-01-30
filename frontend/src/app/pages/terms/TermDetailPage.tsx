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
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api, unwrapResponse } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'

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
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null)
  const [resultDialogOpen, setResultDialogOpen] = useState(false)
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [studentDialogOpen, setStudentDialogOpen] = useState(false)
  const [studentId, setStudentId] = useState('')
  const [studentIdError, setStudentIdError] = useState<string | null>(null)

  const termApi = useApi<TermDetail>(
    resolvedId != null && !Number.isNaN(resolvedId) ? `/terms/${resolvedId}` : null
  )
  const { grades } = useReferencedData()
  const activateMutation = useApiMutation<unknown>()
  const closeMutation = useApiMutation<unknown>()
  const generateAllMutation = useApiMutation<GenerationResult>()
  const generateSingleMutation = useApiMutation<GenerationResult>()

  const term = useMemo(() => {
    const data = termApi.data
    if (!data) return null
    return {
      ...data,
      price_settings: data.price_settings.map((e) => ({
        ...e,
        school_fee_amount: Number(e.school_fee_amount),
      })),
      transport_pricings: data.transport_pricings.map((e) => ({
        ...e,
        transport_fee_amount: Number(e.transport_fee_amount),
      })),
    }
  }, [termApi.data])

  const gradeNameMap = useMemo(() => new Map(grades.map((g) => [g.code, g.name])), [grades])
  const error =
    termApi.error ??
    activateMutation.error ??
    closeMutation.error ??
    generateAllMutation.error ??
    generateSingleMutation.error
  const loading =
    activateMutation.loading ||
    closeMutation.loading ||
    generateAllMutation.loading ||
    generateSingleMutation.loading

  const handleActivate = async () => {
    if (!resolvedId) return
    const ok = await activateMutation.execute(() =>
      api.post(`/terms/${resolvedId}/activate`).then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) termApi.refetch()
  }

  const handleClose = async () => {
    if (!resolvedId) return
    const ok = await closeMutation.execute(() =>
      api.post(`/terms/${resolvedId}/close`).then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) termApi.refetch()
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
    const data = await generateAllMutation.execute(() =>
      api
        .post('/invoices/generate-term-invoices', { term_id: resolvedId })
        .then((r) => ({ data: { data: unwrapResponse<GenerationResult>(r) } }))
    )
    if (data != null) {
      showResult(data)
      closeMenu()
    }
  }

  const generateSingle = async () => {
    if (!resolvedId) return
    setStudentIdError(null)
    const studentIdValue = Number(studentId)
    if (!studentIdValue) {
      setStudentIdError('Enter student ID.')
      return
    }
    const data = await generateSingleMutation.execute(() =>
      api
        .post('/invoices/generate-term-invoices/student', {
          term_id: resolvedId,
          student_id: studentIdValue,
        })
        .then((r) => ({ data: { data: unwrapResponse<GenerationResult>(r) } }))
    )
    if (data != null) {
      showResult(data)
      setStudentDialogOpen(false)
      setStudentId('')
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

      <Dialog
        open={studentDialogOpen}
        onClose={() => {
          setStudentDialogOpen(false)
          setStudentIdError(null)
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Generate invoices for student</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          {studentIdError ? (
            <Alert severity="error" onClose={() => setStudentIdError(null)}>
              {studentIdError}
            </Alert>
          ) : null}
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
