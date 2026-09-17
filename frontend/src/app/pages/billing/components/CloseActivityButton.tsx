import { useState } from 'react'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import { Button } from '../../../components/ui/Button'
import { useApiMutation } from '../../../hooks/useApi'
import { api } from '../../../services/api'

interface CloseActivityButtonProps {
  activityId: number
  activityName: string
  status: string
  onClosed: () => void | Promise<void>
  size?: 'small' | 'medium' | 'large'
}

export const CloseActivityButton = ({
  activityId,
  activityName,
  status,
  onClosed,
  size = 'medium',
}: CloseActivityButtonProps) => {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const closeMutation = useApiMutation()

  if (status === 'closed' || status === 'cancelled') return null

  const closeActivity = async () => {
    if (closeMutation.loading) return
    const result = await closeMutation.execute(() => api.post(`/activities/${activityId}/close`))
    if (result == null) return
    setConfirmOpen(false)
    await onClosed()
  }

  return (
    <>
      <Button
        size={size}
        variant="outlined"
        onClick={() => {
          closeMutation.reset()
          setConfirmOpen(true)
        }}
      >
        Close activity
      </Button>
      <ConfirmDialog
        open={confirmOpen}
        title="Close activity"
        description={`Close “${activityName}”? It will no longer be available in Sell items. Existing invoices remain unchanged.`}
        confirmLabel={closeMutation.loading ? 'Closing...' : 'Close activity'}
        error={closeMutation.error}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={closeActivity}
      />
    </>
  )
}
