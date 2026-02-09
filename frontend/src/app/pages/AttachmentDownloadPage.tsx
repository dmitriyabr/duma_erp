import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../services/api'
import { Alert } from '../components/ui/Alert'
import { Typography } from '../components/ui/Typography'
import { Spinner } from '../components/ui/Spinner'

/**
 * Page opened from CSV export links: /attachment/:id/download
 * User must be logged in (JWT). Fetches file from API and triggers download.
 */
export const AttachmentDownloadPage = () => {
  const { id } = useParams<{ id: string }>()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setError('Missing attachment ID')
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
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return (
      <div className="p-6">
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
        <Typography variant="body2" color="secondary">
          You can close this tab and open the file from the app.
        </Typography>
      </div>
    )
  }

  return (
    <div className="p-6 flex items-center gap-4">
      <Spinner size="small" />
      <Typography>Downloading…</Typography>
    </div>
  )
}
