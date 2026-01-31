import { Alert, Box, CircularProgress, Typography } from '@mui/material'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../services/api'

/**
 * Page opened from CSV export links: /attachment/:id/download
 * User must be logged in (JWT). Fetches file from API and triggers download.
 */
export const AttachmentDownloadPage = () => {
  const { id } = useParams<{ id: string }>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setError('Missing attachment ID')
      setLoading(false)
      return
    }
    let cancelled = false
    const run = async () => {
      try {
        const response = await api.get(`/attachments/${id}/download`, {
          responseType: 'blob',
        })
        if (cancelled) return
        const disposition = response.headers['content-disposition']
        const match = disposition?.match(/filename="?([^";]+)"?/)
        const filename = match?.[1] ?? `attachment-${id}`
        const blob = new Blob([response.data])
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        URL.revokeObjectURL(url)
      } catch (err: unknown) {
        if (!cancelled) {
          const msg =
            err && typeof err === 'object' && 'message' in err
              ? String((err as { message: string }).message)
              : 'Download failed'
          setError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
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
          You can close this tab and open the file from the app.
        </Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
      <CircularProgress size={24} />
      <Typography>Downloading…</Typography>
    </Box>
  )
}
