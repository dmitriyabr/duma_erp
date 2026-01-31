import { Alert, Box, CircularProgress, Typography } from '@mui/material'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../services/api'

/**
 * Page opened from CSV export links: /payment/:id/receipt
 * User must be logged in (JWT). Fetches receipt PDF from API and opens/downloads it.
 */
export const PaymentReceiptDownloadPage = () => {
  const { id } = useParams<{ id: string }>()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setError('Missing payment ID')
      return
    }
    let cancelled = false
    const run = async () => {
      try {
        const response = await api.get(`/payments/${id}/receipt/pdf`, {
          responseType: 'blob',
        })
        if (cancelled) return
        const blob = new Blob([response.data], { type: 'application/pdf' })
        const url = URL.createObjectURL(blob)
        window.open(url, '_blank')
        URL.revokeObjectURL(url)
      } catch (err: unknown) {
        if (!cancelled) {
          const msg =
            err && typeof err === 'object' && 'message' in err
              ? String((err as { message: string }).message)
              : 'Failed to load receipt'
          setError(msg)
        }
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Typography variant="body2" color="text.secondary">
          You can close this tab and open the receipt from the app.
        </Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
      <CircularProgress size={24} />
      <Typography>Opening receipt…</Typography>
    </Box>
  )
}
