import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Select } from '../../components/ui/Select'
import { Card, CardContent } from '../../components/ui/Card'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import { downloadReportExcel } from '../../utils/reportExcel'

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
    const t = window.setTimeout(() => setTermId(String(activeTerm.id)), 0)
    return () => window.clearTimeout(t)
  }, [activeTerm?.id, termId])

  useEffect(() => {
    if (!termId) return
    const tid = Number(termId)
    if (Number.isNaN(tid)) return
    let cancelled = false
    const t = window.setTimeout(() => {
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
    }, 0)
    return () => { cancelled = true; window.clearTimeout(t) }
  }, [termId, gradeId])

  if (forbidden) {
    return (
      <div>
        <Typography variant="h5" className="mb-4">Student Fees by Term</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  const handleExportExcel = () => {
    if (!termId) return
    const params: Record<string, unknown> = { term_id: Number(termId) }
    if (gradeId) params.grade_id = Number(gradeId)
    downloadReportExcel('/reports/student-fees', params, 'student-fees.xlsx')
  }

  return (
    <div>
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <Typography variant="h5">Student Fees by Term</Typography>
        {termId && (
          <Button variant="outlined" onClick={handleExportExcel}>
            Export to Excel
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-4 mb-4">
        <div className="min-w-[200px]">
          <Select
            label="Term"
            value={termId}
            onChange={(e) => setTermId(e.target.value)}
          >
            <option value="">Select term</option>
            {(terms ?? []).map((t) => (
              <option key={t.id} value={String(t.id)}>{t.display_name}</option>
            ))}
          </Select>
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Grade"
            value={gradeId}
            onChange={(e) => setGradeId(e.target.value)}
          >
            <option value="">All</option>
            {grades.map((g) => (
              <option key={g.id} value={String(g.id)}>{g.name}</option>
            ))}
          </Select>
        </div>
      </div>

      {termsLoading && (
        <div className="flex justify-center py-2">
          <Spinner size="small" />
        </div>
      )}

      {!termId && !termsLoading && (
        <Typography color="secondary">Select a term to view the report.</Typography>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {termId && loading && (
        <div className="flex justify-center py-8">
          <Spinner size="large" />
        </div>
      )}

      {termId && !loading && report && (
        <>
          <Typography variant="body2" color="secondary" className="mb-2">
            {report.term_display_name}
            {report.grade_id != null && ` · Grade filter applied`}
          </Typography>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Class</TableHeaderCell>
                  <TableHeaderCell align="right">Students</TableHeaderCell>
                  <TableHeaderCell align="right">Total Invoiced</TableHeaderCell>
                  <TableHeaderCell align="right">Total Paid</TableHeaderCell>
                  <TableHeaderCell align="right">Balance</TableHeaderCell>
                  <TableHeaderCell align="right">Rate</TableHeaderCell>
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
          </div>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="secondary" className="mb-2">Summary</Typography>
              <div className="flex flex-wrap gap-6">
                <Typography variant="body2"><strong>Students:</strong> {report.summary.students_count}</Typography>
                <Typography variant="body2"><strong>Total Invoiced:</strong> {formatMoney(report.summary.total_invoiced)}</Typography>
                <Typography variant="body2"><strong>Total Paid:</strong> {formatMoney(report.summary.total_paid)}</Typography>
                <Typography variant="body2"><strong>Balance:</strong> {formatMoney(report.summary.balance)}</Typography>
                <Typography variant="body2"><strong>Rate:</strong> {report.summary.rate_percent != null ? `${report.summary.rate_percent}%` : '—'}</Typography>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {termId && !loading && !report && !error && (
        <Typography color="secondary">No data for this term.</Typography>
      )}
    </div>
  )
}
