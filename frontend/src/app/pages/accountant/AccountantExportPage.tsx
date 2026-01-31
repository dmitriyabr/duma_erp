import { Alert, Box, Button, TextField, Typography } from '@mui/material'
import { useState } from 'react'
import { api } from '../../services/api'

function getDefaultDateRange(): { start: string; end: string } {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

type ExportType = 'student-payments' | 'procurement-payments' | 'student-balance-changes'

export const AccountantExportPage = () => {
  const [datesPayments, setDatesPayments] = useState(getDefaultDateRange)
  const [datesProcurement, setDatesProcurement] = useState(getDefaultDateRange)
  const [datesBalanceChanges, setDatesBalanceChanges] = useState(getDefaultDateRange)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async (
    type: ExportType,
    startDate: string,
    endDate: string,
  ) => {
    if (!startDate || !endDate) {
      setError('Please set start date and end date.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const url = `/accountant/export/${type}?start_date=${startDate}&end_date=${endDate}&format=csv`
      const response = await api.get(url, { responseType: 'blob' })
      const blob = new Blob([response.data], { type: 'text/csv' })
      const disposition = response.headers['content-disposition']
      const filenameMatch = disposition?.match(/filename="?([^";]+)"?/)
      const filename = filenameMatch?.[1] ?? `export_${type}_${startDate}_${endDate}.csv`
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (err: unknown) {
      const message = err && typeof err === 'object' && 'message' in err
        ? String((err as { message: string }).message)
        : 'Export failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Data Export
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Export data for accounting (QuickBooks, Xero, Excel). Select date range and download CSV.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Student Payments (Receipts)
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
            <TextField
              label="Start date"
              type="date"
              value={datesPayments.start}
              onChange={(e) => setDatesPayments((p) => ({ ...p, start: e.target.value }))}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <TextField
              label="End date"
              type="date"
              value={datesPayments.end}
              onChange={(e) => setDatesPayments((p) => ({ ...p, end: e.target.value }))}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <Button
              variant="contained"
              onClick={() =>
                handleExport('student-payments', datesPayments.start, datesPayments.end)
              }
              disabled={loading}
            >
              {loading ? 'Exporting…' : 'Download CSV'}
            </Button>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Columns: Receipt Date, Receipt#, Student Name, Admission#, Grade, Parent Name, Payment
            Method, Amount, Received By, Receipt PDF link, Attachment link
          </Typography>
        </Box>

        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Procurement Payments
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
            <TextField
              label="Start date"
              type="date"
              value={datesProcurement.start}
              onChange={(e) => setDatesProcurement((p) => ({ ...p, start: e.target.value }))}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <TextField
              label="End date"
              type="date"
              value={datesProcurement.end}
              onChange={(e) => setDatesProcurement((p) => ({ ...p, end: e.target.value }))}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <Button
              variant="outlined"
              onClick={() =>
                handleExport('procurement-payments', datesProcurement.start, datesProcurement.end)
              }
              disabled={loading}
            >
              {loading ? 'Exporting…' : 'Download CSV'}
            </Button>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Columns: Payment Date, Payment#, Supplier, PO#, Gross Amount, Net Paid, Payment Method,
            Reference, Attachment link
          </Typography>
        </Box>

        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Student Balance Changes
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
            <TextField
              label="Start date"
              type="date"
              value={datesBalanceChanges.start}
              onChange={(e) => setDatesBalanceChanges((p) => ({ ...p, start: e.target.value }))}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <TextField
              label="End date"
              type="date"
              value={datesBalanceChanges.end}
              onChange={(e) => setDatesBalanceChanges((p) => ({ ...p, end: e.target.value }))}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <Button
              variant="outlined"
              onClick={() =>
                handleExport(
                  'student-balance-changes',
                  datesBalanceChanges.start,
                  datesBalanceChanges.end,
                )
              }
              disabled={loading}
            >
              {loading ? 'Exporting…' : 'Download CSV'}
            </Button>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Columns: Date, Student ID, Student Name, Type, Reference, Amount (+ in / − out)
          </Typography>
        </Box>
      </Box>
    </Box>
  )
}
