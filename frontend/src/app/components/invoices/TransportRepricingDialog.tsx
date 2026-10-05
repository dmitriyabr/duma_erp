import { useState } from 'react'
import { useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Dialog, DialogActions, DialogContent, DialogTitle } from '../ui/Dialog'
import { Textarea } from '../ui/Textarea'

interface Preview {
  invoice_number: string
  student_name: string
  term_name: string
  zone_name: string
  price_before: string
  price_after: string
  discount_before: string
  discount_after: string
  total_before: string
  total_after: string
  paid_before: string
  paid_after: string
  due_before: string
  due_after: string
  credit_before: string
  credit_after: string
  released_credit: string
  changed: boolean
  preview_token: string
}

interface Props {
  invoiceId: number
  onClose: () => void
  onRecalculated: () => void
}

export function TransportRepricingDialog({ invoiceId, onClose, onRecalculated }: Props) {
  const [reason, setReason] = useState('Change of transport zone for the whole term')
  const [preview, setPreview] = useState<Preview | null>(null)
  const reviewMutation = useApiMutation<Preview>()
  const applyMutation = useApiMutation<Preview>()
  const busy = reviewMutation.loading || applyMutation.loading
  const error = reviewMutation.error || applyMutation.error

  const review = async () => {
    setPreview(null)
    applyMutation.reset()
    const result = await reviewMutation.execute(() =>
      api.post(`/invoices/${invoiceId}/recalculate-transport/preview`))
    if (result) setPreview(result)
  }
  const apply = async () => {
    if (!preview || !reason.trim()) return
    const result = await applyMutation.execute(() =>
      api.post(`/invoices/${invoiceId}/recalculate-transport`, {
        reason: reason.trim(), preview_token: preview.preview_token,
      }))
    if (result) onRecalculated()
    else setPreview(null)
  }

  return <Dialog open onClose={() => { if (!busy) onClose() }} maxWidth="sm">
    <DialogTitle>Recalculate transport</DialogTitle>
    <DialogContent>
      <div className="space-y-4 mt-3">
        <p>Apply the student's current transport zone price to the whole term.</p>
        <p className="text-sm text-slate-500">Payments stay recorded. Any excess allocated to this invoice returns to the family balance. Existing family credit is not automatically used.</p>
        {error && <Alert severity="error">{error}</Alert>}
        {preview && <>
          <p><strong>{preview.student_name}</strong><br />{preview.invoice_number} · {preview.term_name}<br />New zone: {preview.zone_name}</p>
          <table className="w-full text-sm text-left">
            <thead><tr><th>Amount</th><th>Before</th><th>After</th></tr></thead>
            <tbody>{([
              ['Transport fee', preview.price_before, preview.price_after],
              ['Discount', preview.discount_before, preview.discount_after],
              ['Invoice total', preview.total_before, preview.total_after],
              ['Allocated payments', preview.paid_before, preview.paid_after],
              ['Amount due', preview.due_before, preview.due_after],
              ['Family credit', preview.credit_before, preview.credit_after],
            ]).map(([label, before, after]) => <tr key={label} className="border-t">
              <td className="py-2">{label}</td><td>{formatMoney(before)}</td><td>{formatMoney(after)}</td>
            </tr>)}</tbody>
          </table>
          {Number(preview.released_credit) > 0 && <Alert severity="info">{formatMoney(preview.released_credit)} will return to the family balance.</Alert>}
          {!preview.changed && <Alert severity="info">This invoice already matches the current zone price.</Alert>}
        </>}
        <Textarea label="Reason" value={reason} onChange={e => setReason(e.target.value)} disabled={busy} maxLength={2000} />
      </div>
    </DialogContent>
    <DialogActions>
      <Button variant="outlined" onClick={onClose} disabled={busy}>Close</Button>
      {preview?.changed
        ? <Button onClick={apply} disabled={busy || !reason.trim()}>{busy ? 'Saving…' : 'Confirm recalculation'}</Button>
        : <Button onClick={review} disabled={busy}>{busy ? 'Loading…' : 'Preview recalculation'}</Button>}
    </DialogActions>
  </Dialog>
}
