import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from './ui/Dialog'
import { Button } from './ui/Button'
import { Typography } from './ui/Typography'
import { Alert } from './ui/Alert'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  error?: string | null
  onCancel: () => void
  onConfirm: () => void
}

export const ConfirmDialog = ({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  error = null,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) => {
  return (
    <Dialog open={open} onClose={onCancel}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Typography variant="body1" color="secondary">
          {description}
        </Typography>
        {error ? (
          <Alert severity="error" className="mt-4">
            {error}
          </Alert>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button variant="contained" onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
