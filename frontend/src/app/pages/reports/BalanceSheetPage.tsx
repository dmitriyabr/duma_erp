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

interface AssetLine {
  label: string
  amount: string
}

interface LiabilityLine {
  label: string
  amount: string
}

interface BalanceSheetData {
  as_at_date: string
  asset_lines: AssetLine[]
  total_assets: string
  liability_lines: LiabilityLine[]
  total_liabilities: string
  net_equity: string
  debt_to_asset_percent: number | null
  current_ratio: number | null
}

const defaultAsAt = () => new Date().toISOString().slice(0, 10)

export const BalanceSheetPage = () => {
  const { user } = useAuth()
  const [asAtDate, setAsAtDate] = useState(defaultAsAt)
  const [data, setData] = useState<BalanceSheetData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const runReport = () => {
    if (!canSeeReports(user)) return
    setLoading(true)
    setError(null)
    api
      .get<ApiResponse<BalanceSheetData>>('/reports/balance-sheet', {
        params: { as_at_date: asAtDate },
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
        <Typography variant="h5" className="mb-4">Balance Sheet</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </div>
    )
  }

  return (
    <div>
      <Typography variant="h5" className="mb-4">Balance Sheet</Typography>

      <Card className="mb-4">
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            <div className="min-w-[180px]">
              <Input
                label="As at date"
                type="date"
                value={asAtDate}
                onChange={(e) => setAsAtDate(e.target.value)}
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
            As at {data.as_at_date}
          </Typography>

          <Card className="mb-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell><strong>Assets</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Amount (KES)</strong></TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.asset_lines.map((row) => (
                    <TableRow key={row.label}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell><strong>Total Assets</strong></TableCell>
                    <TableCell align="right"><strong>{formatMoney(data.total_assets)}</strong></TableCell>
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
                    <TableHeaderCell><strong>Liabilities</strong></TableHeaderCell>
                    <TableHeaderCell align="right"><strong>Amount (KES)</strong></TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.liability_lines.map((row) => (
                    <TableRow key={row.label}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell align="right">{formatMoney(row.amount)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell><strong>Total Liabilities</strong></TableCell>
                    <TableCell align="right"><strong>{formatMoney(data.total_liabilities)}</strong></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" className="mb-2"><strong>Net equity</strong>: {formatMoney(data.net_equity)}</Typography>
              {data.debt_to_asset_percent != null && (
                <Typography variant="body2" color="secondary" className="mb-2">
                  Debt-to-asset ratio: {data.debt_to_asset_percent}%
                </Typography>
              )}
              {data.current_ratio != null && (
                <Typography variant="body2" color="secondary">
                  Current ratio: {data.current_ratio}
                </Typography>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="secondary">Select date and run report.</Typography>
      )}
    </div>
  )
}
