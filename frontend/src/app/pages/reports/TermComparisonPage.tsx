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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'

interface TermRow {
  id: number
  year: number
  term_number: number
  display_name: string
  status: string
}

interface TermComparisonMetric {
  name: string
  term1_value: string | number
  term2_value: string | number
  change_abs: string | number | null
  change_percent: number | null
}

interface TermComparisonData {
  term1_id: number
  term1_display_name: string
  term2_id: number
  term2_display_name: string
  metrics: TermComparisonMetric[]
}

function formatMetricValue(v: string | number): string {
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v)
    return formatMoney(String(v))
  }
  return String(v)
}

export const TermComparisonPage = () => {
  const { user } = useAuth()
  const { data: terms } = useApi<TermRow[]>('/terms')
  const [term1Id, setTerm1Id] = useState<string>('')
  const [term2Id, setTerm2Id] = useState<string>('')
  const [data, setData] = useState<TermComparisonData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    const t1 = Number(term1Id)
    const t2 = Number(term2Id)
    if (Number.isNaN(t1) || Number.isNaN(t2) || t1 === t2) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<TermComparisonData>>('/reports/term-comparison', {
        params: { term1_id: t1, term2_id: t2 },
      })
      .then((res) => {
        if (res.data?.data) setData(res.data.data)
      })
      .catch((err) => {
        if (err.response?.status === 403) setForbidden(true)
        else if (err.response?.status === 404) setError('One or both terms not found')
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
        <Typography variant="h5" sx={{ mb: 2 }}>Term-over-Term Comparison</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Term-over-Term Comparison</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Term 1</InputLabel>
              <Select
                value={term1Id}
                label="Term 1"
                onChange={(e) => setTerm1Id(e.target.value)}
              >
                {(terms ?? []).map((t) => (
                  <MenuItem key={t.id} value={String(t.id)}>{t.display_name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Term 2</InputLabel>
              <Select
                value={term2Id}
                label="Term 2"
                onChange={(e) => setTerm2Id(e.target.value)}
              >
                {(terms ?? []).map((t) => (
                  <MenuItem key={t.id} value={String(t.id)}>{t.display_name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              onClick={runReport}
              disabled={!term1Id || !term2Id || term1Id === term2Id}
            >
              Compare
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
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Comparing {data.term1_display_name} vs {data.term2_display_name}
          </Typography>

          <TableContainer component={Card}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Metric</strong></TableCell>
                  <TableCell align="right"><strong>{data.term1_display_name}</strong></TableCell>
                  <TableCell align="right"><strong>{data.term2_display_name}</strong></TableCell>
                  <TableCell align="right"><strong>Change</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.metrics.map((m) => (
                  <TableRow key={m.name}>
                    <TableCell>{m.name}</TableCell>
                    <TableCell align="right">{formatMetricValue(m.term1_value)}</TableCell>
                    <TableCell align="right">{formatMetricValue(m.term2_value)}</TableCell>
                    <TableCell align="right">
                      {m.change_percent != null
                        ? `${m.change_abs != null ? formatMetricValue(m.change_abs) + ' ' : ''}(${m.change_percent > 0 ? '+' : ''}${m.change_percent}%)`
                        : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select two different terms and click Compare.</Typography>
      )}
    </Box>
  )
}
