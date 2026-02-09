import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { downloadReportExcel } from '../../utils/reportExcel'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Select,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

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

function formatMetricValue(v: string | number, metricName: string): string {
  if (v === null || v === undefined || v === '—' || v === '') return '—'
  if (typeof v === 'string') return v
  // Проценты — без валюты, только число и %
  if (metricName.includes('(%)')) {
    return `${Number(v).toFixed(2)}%`
  }
  // Суммы в KES — всегда formatMoney (с группировкой разрядов)
  if (metricName.includes('(KES)')) {
    return formatMoney(v)
  }
  // Целые (Students Enrolled и т.п.)
  if (Number.isInteger(v)) return String(v)
  return formatMoney(String(v))
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
      <div>
        <Typography variant="h5" className="mb-4">Term-over-Term Comparison</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Term-over-Term Comparison</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <Select
              value={term1Id}
              onChange={(e) => setTerm1Id(e.target.value)}
              label="Term 1"
              className="min-w-[180px]"
            >
              {(terms ?? []).map((t) => (
                <option key={t.id} value={String(t.id)}>{t.display_name}</option>
              ))}
            </Select>
            <Select
              value={term2Id}
              onChange={(e) => setTerm2Id(e.target.value)}
              label="Term 2"
              className="min-w-[180px]"
            >
              {(terms ?? []).map((t) => (
                <option key={t.id} value={String(t.id)}>{t.display_name}</option>
              ))}
            </Select>
            <Button
              variant="contained"
              onClick={runReport}
              disabled={!term1Id || !term2Id || term1Id === term2Id}
            >
              Compare
            </Button>
            <Button
              variant="outlined"
              disabled={!term1Id || !term2Id || term1Id === term2Id}
              onClick={() => {
                const t1 = Number(term1Id)
                const t2 = Number(term2Id)
                if (Number.isNaN(t1) || Number.isNaN(t2) || t1 === t2) return
                downloadReportExcel('/reports/term-comparison', { term1_id: t1, term2_id: t2 }, 'term-comparison.xlsx')
              }}
            >
              Export to Excel
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Spinner size="medium" />
        </div>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {!loading && data && (
        <>
          <Typography variant="body2" color="secondary" className="mb-4">
            Comparing {data.term1_display_name} vs {data.term2_display_name}
          </Typography>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Metric</TableHeaderCell>
                  <TableHeaderCell align="right">{data.term1_display_name}</TableHeaderCell>
                  <TableHeaderCell align="right">{data.term2_display_name}</TableHeaderCell>
                  <TableHeaderCell align="right">Change</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.metrics.map((m) => (
                  <TableRow key={m.name}>
                    <TableCell>{m.name}</TableCell>
                    <TableCell align="right">{formatMetricValue(m.term1_value, m.name)}</TableCell>
                    <TableCell align="right">{formatMetricValue(m.term2_value, m.name)}</TableCell>
                    <TableCell align="right">
                      {m.change_percent != null
                        ? `${m.change_abs != null ? formatMetricValue(m.change_abs, m.name) + ' ' : ''}(${m.change_percent > 0 ? '+' : ''}${m.change_percent}%)`
                        : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select two different terms and click Compare.</Typography>
      )}
    </div>
  )
}
