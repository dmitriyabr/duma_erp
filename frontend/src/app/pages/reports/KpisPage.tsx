import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { downloadReportExcel } from '../../utils/reportExcel'

interface TermRow {
  id: number
  display_name: string
}

interface KpisData {
  period_type: string
  year: number | null
  term_id: number | null
  term_display_name: string | null
  active_students_count: number
  total_revenue: string
  total_invoiced: string
  collection_rate_percent: number | null
  total_expenses: string
  student_debt: string
  supplier_debt: string
  pending_claims_amount: string
}

export const KpisPage = () => {
  const { user } = useAuth()
  const { data: terms } = useApi<TermRow[]>('/terms')
  const [periodType, setPeriodType] = useState<'year' | 'term'>('year')
  const [year, setYear] = useState(new Date().getFullYear())
  const [termId, setTermId] = useState<string>('')
  const [data, setData] = useState<KpisData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    const params: { year?: number; term_id?: number } = {}
    if (periodType === 'year') params.year = year
    else if (periodType === 'term' && termId) params.term_id = Number(termId)
    api
      .get<ApiResponse<KpisData>>('/reports/kpis', { params })
      .then((res) => {
        if (res.data?.data) setData(res.data.data)
      })
      .catch((err) => {
        if (err.response?.status === 403) setForbidden(true)
        else setError(err.response?.data?.detail ?? 'Failed to load report')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (canSeeReports(user)) runReport()
    else setForbidden(true)
  }, [user])

  if (forbidden) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>KPIs & Metrics</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>KPIs & Metrics</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Period</InputLabel>
              <Select
                value={periodType}
                label="Period"
                onChange={(e) => setPeriodType(e.target.value as 'year' | 'term')}
              >
                <MenuItem value="year">Calendar year</MenuItem>
                <MenuItem value="term">Term</MenuItem>
              </Select>
            </FormControl>
            {periodType === 'year' && (
              <FormControl size="small" sx={{ minWidth: 100 }}>
                <InputLabel>Year</InputLabel>
                <Select
                  value={year}
                  label="Year"
                  onChange={(e) => setYear(Number(e.target.value))}
                >
                  {[new Date().getFullYear(), new Date().getFullYear() - 1, new Date().getFullYear() - 2].map((y) => (
                    <MenuItem key={y} value={y}>{y}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
            {periodType === 'term' && (
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>Term</InputLabel>
                <Select
                  value={termId}
                  label="Term"
                  onChange={(e) => setTermId(e.target.value)}
                >
                  {(terms ?? []).map((t) => (
                    <MenuItem key={t.id} value={String(t.id)}>{t.display_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
            <Button variant="contained" onClick={runReport}>Run report</Button>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                const params: Record<string, unknown> = {}
                if (periodType === 'year') params.year = year
                else if (periodType === 'term' && termId) params.term_id = Number(termId)
                downloadReportExcel('/reports/kpis', params, 'kpis.xlsx')
              }}
            >
              Export to Excel
            </Button>
          </Box>
        </CardContent>
      </Card>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!loading && data && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Period</Typography>
              <Typography variant="h6">
                {data.period_type === 'term' && data.term_display_name
                  ? data.term_display_name
                  : `Year ${data.year}`}
              </Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Active students</Typography>
              <Typography variant="h6">{data.active_students_count}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Total revenue (KES)</Typography>
              <Typography variant="h6">{formatMoney(data.total_revenue)}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Total invoiced (KES)</Typography>
              <Typography variant="h6">{formatMoney(data.total_invoiced)}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Collection rate (%)</Typography>
              <Typography variant="h6">
                {data.collection_rate_percent != null ? `${data.collection_rate_percent}%` : '—'}
              </Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Total expenses (KES)</Typography>
              <Typography variant="h6">{formatMoney(data.total_expenses)}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Student debt (KES)</Typography>
              <Typography variant="h6">{formatMoney(data.student_debt)}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Supplier debt (KES)</Typography>
              <Typography variant="h6">{formatMoney(data.supplier_debt)}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ minWidth: 200 }}>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Pending claims (KES)</Typography>
              <Typography variant="h6">{formatMoney(data.pending_claims_amount)}</Typography>
            </CardContent>
          </Card>
        </Box>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select period and run report.</Typography>
      )}
    </Box>
  )
}
