import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent } from '../../components/ui/Card'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'

interface InflowLine {
  label: string
  amount: string
}

interface OutflowLine {
  label: string
  amount: string
}

interface CashFlowData {
  date_from: string
  date_to: string
  opening_balance: string
  inflow_lines: InflowLine[]
  total_inflows: string
  outflow_lines: OutflowLine[]
  total_outflows: string
  net_cash_flow: string
  closing_balance: string
}

const defaultDateFrom = () => {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}
const defaultDateTo = () => new Date().toISOString().slice(0, 10)

export const CashFlowPage = () => {
  const { user } = useAuth()
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [data, setData] = useState<CashFlowData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<CashFlowData>>('/reports/cash-flow', {
        params: { date_from: dateFrom, date_to: dateTo },
      })
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
      <div>
        <Typography variant="h5" className="mb-4">Cash Flow</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Cash Flow</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <div className="min-w-[160px]">
              <Input
                label="From"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="min-w-[160px]">
              <Input
                label="To"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
            <Button variant="contained" onClick={runReport}>Run report</Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Spinner size="large" />
        </div>
      )}

      {error && <Alert severity="error" className="mb-4">{error}</Alert>}

      {!loading && data && (
        <>
          <Typography variant="body2" color="secondary" className="mb-4">
            Period: {data.date_from} — {data.date_to}
          </Typography>

          <Card className="mb-4">
            <CardContent>
              <Typography variant="subtitle2" color="secondary" className="mb-2">Opening balance (as at {data.date_from})</Typography>
              <Typography variant="h6">{formatMoney(data.opening_balance)}</Typography>
            </CardContent>
          </Card>

          <Card className="mb-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell><strong>Cash Inflows</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Amount (KES)</strong></TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.inflow_lines.map((row) => (
                    <TableRow key={row.label}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell><strong>Total Inflows</strong></TableCell>
                    <TableCell align="right"><strong>{formatMoney(data.total_inflows)}</strong></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </Card>

          <Card className="mb-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell><strong>Cash Outflows</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Amount (KES)</strong></TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.outflow_lines.map((row) => (
                    <TableRow key={row.label}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell><strong>Total Outflows</strong></TableCell>
                    <TableCell align="right"><strong>{formatMoney(data.total_outflows)}</strong></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" className="mb-2"><strong>Net cash flow</strong>: {formatMoney(data.net_cash_flow)}</Typography>
              <Typography variant="subtitle2" className="mb-2"><strong>Closing balance</strong> (as at {data.date_to}): {formatMoney(data.closing_balance)}</Typography>
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select period and run report.</Typography>
      )}
    </div>
  )
}
