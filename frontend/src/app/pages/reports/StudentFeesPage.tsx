import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { formatMoney } from '../../utils/format'

interface TermRow {
  id: number
  year: number
  term_number: number
  display_name: string
  status: string
}

interface StudentFeesRow {
  grade_id: number
  grade_name: string
  students_count: number
  total_invoiced: string
  total_paid: string
  balance: string
  rate_percent: number | null
}

interface StudentFeesSummary {
  students_count: number
  total_invoiced: string
  total_paid: string
  balance: string
  rate_percent: number | null
}

interface StudentFeesData {
  term_id: number
  term_display_name: string
  grade_id: number | null
  rows: StudentFeesRow[]
  summary: StudentFeesSummary
}

export const StudentFeesPage = () => {
  const { grades } = useReferencedData()
  const { data: terms, loading: termsLoading } = useApi<TermRow[]>('/terms')
  const { data: activeTerm } = useApi<{ id: number } | null>('/terms/active')
  const [termId, setTermId] = useState<string>('')
  const [gradeId, setGradeId] = useState<string>('')
  const [report, setReport] = useState<StudentFeesData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  // Default to current (active) term when terms and active term are loaded
  useEffect(() => {
    if (termId !== '' || !activeTerm?.id) return
    setTermId(String(activeTerm.id))
  }, [activeTerm?.id, termId])

  useEffect(() => {
    if (!termId) return
    const tid = Number(termId)
    if (Number.isNaN(tid)) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setForbidden(false)
    const params: { term_id: number; grade_id?: number } = { term_id: tid }
    if (gradeId) {
      const gid = Number(gradeId)
      if (!Number.isNaN(gid)) params.grade_id = gid
    }
    api
      .get<ApiResponse<StudentFeesData>>('/reports/student-fees', { params })
      .then((res) => {
        if (!cancelled && res.data?.data) setReport(res.data.data)
      })
      .catch((err) => {
        if (!cancelled) {
          if (err.response?.status === 403) setForbidden(true)
          else setError(err.response?.data?.message ?? 'Failed to load report')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [termId, gradeId])

  if (forbidden) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Student Fees by Term</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Student Fees by Term</Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Term</InputLabel>
          <Select
            value={termId}
            label="Term"
            onChange={(e) => setTermId(e.target.value)}
          >
            <MenuItem value="">Select term</MenuItem>
            {(terms ?? []).map((t) => (
              <MenuItem key={t.id} value={String(t.id)}>{t.display_name}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Grade</InputLabel>
          <Select
            value={gradeId}
            label="Grade"
            onChange={(e) => setGradeId(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            {grades.map((g) => (
              <MenuItem key={g.id} value={String(g.id)}>{g.name}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {termsLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {!termId && !termsLoading && (
        <Typography color="text.secondary">Select a term to view the report.</Typography>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {termId && loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {termId && !loading && report && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {report.term_display_name}
            {report.grade_id != null && ` · Grade filter applied`}
          </Typography>
          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Class</strong></TableCell>
                  <TableCell align="right"><strong>Students</strong></TableCell>
                  <TableCell align="right"><strong>Total Invoiced</strong></TableCell>
                  <TableCell align="right"><strong>Total Paid</strong></TableCell>
                  <TableCell align="right"><strong>Balance</strong></TableCell>
                  <TableCell align="right"><strong>Rate</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report.rows.map((row) => (
                  <TableRow key={row.grade_id}>
                    <TableCell>{row.grade_name}</TableCell>
                    <TableCell align="right">{row.students_count}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_invoiced)}</TableCell>
                    <TableCell align="right">{formatMoney(row.total_paid)}</TableCell>
                    <TableCell align="right">{formatMoney(row.balance)}</TableCell>
                    <TableCell align="right">
                      {row.rate_percent != null ? `${row.rate_percent}%` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Summary</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Typography variant="body2"><strong>Students:</strong> {report.summary.students_count}</Typography>
                <Typography variant="body2"><strong>Total Invoiced:</strong> {formatMoney(report.summary.total_invoiced)}</Typography>
                <Typography variant="body2"><strong>Total Paid:</strong> {formatMoney(report.summary.total_paid)}</Typography>
                <Typography variant="body2"><strong>Balance:</strong> {formatMoney(report.summary.balance)}</Typography>
                <Typography variant="body2"><strong>Rate:</strong> {report.summary.rate_percent != null ? `${report.summary.rate_percent}%` : '—'}</Typography>
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      {termId && !loading && !report && !error && (
        <Typography color="text.secondary">No data for this term.</Typography>
      )}
    </Box>
  )
}
