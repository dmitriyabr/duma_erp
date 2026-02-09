import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../services/api'
import { Alert } from '../components/ui/Alert'
import { Typography } from '../components/ui/Typography'
import { Spinner } from '../components/ui/Spinner'

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
      <div className="p-6">
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
        <Typography variant="body2" color="secondary">
          You can close this tab and open the receipt from the app.
        </Typography>
      </div>
    )
  }

  return (
    <div className="p-6 flex items-center gap-4">
      <Spinner size="small" />
      <Typography>Opening receipt…</Typography>
    </div>
  )
}
