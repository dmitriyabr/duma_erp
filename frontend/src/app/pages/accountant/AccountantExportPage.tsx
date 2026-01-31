import { Alert, Box, Button, TextField, Typography } from '@mui/material'
import { useState } from 'react'
import { api } from '../../services/api'

type ExportType = 'student-payments'

export const AccountantExportPage = () => {
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async (type: ExportType) => {
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
        Export data for accounting (QuickBooks, Xero, Excel). Select date range and format.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ maxWidth: 480 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
          Student Payments (Receipts)
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
          <TextField
            label="Start date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            size="small"
            InputLabelProps={{ shrink: true }}
            sx={{ width: 180 }}
          />
          <TextField
            label="End date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            size="small"
            InputLabelProps={{ shrink: true }}
            sx={{ width: 180 }}
          />
          <Button
            variant="contained"
            onClick={() => handleExport('student-payments')}
            disabled={loading}
          >
            {loading ? 'Exporting…' : 'Download CSV'}
          </Button>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Columns: Receipt Date, Receipt#, Student Name, Admission#, Grade, Parent Name, Payment
          Method, Amount, Received By
        </Typography>
      </Box>
    </Box>
  )
}
