import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { canSeeReports } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'

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
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Balance Sheet</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Balance Sheet</Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <TextField
              label="As at date"
              type="date"
              size="small"
              value={asAtDate}
              onChange={(e) => setAsAtDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <Button variant="contained" onClick={runReport}>Run report</Button>
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
            As at {data.as_at_date}
          </Typography>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Assets</strong></TableCell>
                  <TableCell align="right"><strong>Amount (KES)</strong></TableCell>
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
          </TableContainer>

          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>Liabilities</strong></TableCell>
                  <TableCell align="right"><strong>Amount (KES)</strong></TableCell>
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
          </TableContainer>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom><strong>Net equity</strong>: {formatMoney(data.net_equity)}</Typography>
              {data.debt_to_asset_percent != null && (
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Debt-to-asset ratio: {data.debt_to_asset_percent}%
                </Typography>
              )}
              {data.current_ratio != null && (
                <Typography variant="body2" color="text.secondary">
                  Current ratio: {data.current_ratio}
                </Typography>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && canSeeReports(user) && (
        <Typography color="text.secondary">Select date and run report.</Typography>
      )}
    </Box>
  )
}
