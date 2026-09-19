import { useState } from 'react'
import { useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'
import { formatStudentNumberShort } from '../../utils/studentNumber'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Dialog, DialogActions, DialogContent, DialogTitle } from '../ui/Dialog'
import { StudentNumberLookup, type StudentNumberMatch } from '../students/StudentNumberLookup'
import { Textarea } from '../ui/Textarea'

interface Party {
  student_name: string
  student_number: string
  billing_account_id: number
  account_number: string
  account_name: string
}
interface Impact {
  invoice_id: number
  invoice_number: string
  student_name: string
  amount: string
  due_before: string
  due_after: string
}
interface Preview {
  payment_number: string
  amount: string
  source: Party
  target: Party
  removed_allocations: Impact[]
  new_allocations: Impact[]
  allocation_schedule: Array<{ invoice_id: number; amount: string; created_at: string | null }>
  source_credit_before: string
  source_credit_after: string
  target_credit_before: string
  target_credit_after: string
  preview_token: string
}
interface Props {
  payment: { id: number; payment_number: string; student_id: number; amount: string }
  onClose: () => void
  onTransferred: () => void
}

function InvoiceImpacts({ title, rows }: { title: string; rows: Impact[] }) {
  return <section className="space-y-2">
    <h3 className="font-semibold">{title}</h3>
    {rows.length === 0 ? <p className="text-sm text-slate-500">None</p> : (
      <div className="overflow-x-auto"><table className="w-full text-sm text-left">
        <thead><tr><th>Invoice / student</th><th>Amount</th><th>Debt before → after</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.invoice_id} className="border-t">
          <td className="py-2">{row.invoice_number}<br />{row.student_name}</td>
          <td>{formatMoney(row.amount)}</td>
          <td>{formatMoney(row.due_before)} → {formatMoney(row.due_after)}</td>
        </tr>)}</tbody>
      </table></div>
    )}
  </section>
}

export function PaymentTransferDialog({ payment, onClose, onTransferred }: Props) {
  const [studentNumber, setStudentNumber] = useState('')
  const [student, setStudent] = useState<StudentNumberMatch | null>(null)
  const [reason, setReason] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const previewMutation = useApiMutation<Preview>()
  const transferMutation = useApiMutation<Preview>()
  const busy = previewMutation.loading || transferMutation.loading
  const error = previewMutation.error || transferMutation.error

  const review = async () => {
    if (!student) return
    transferMutation.reset()
    setPreview(null)
    const result = await previewMutation.execute(() => api.post(`/payments/${payment.id}/transfer/preview`, {
      target_student_id: student.id,
    }))
    if (result) setPreview(result)
  }
  const transfer = async () => {
    if (!student || !preview || !reason.trim()) return
    const result = await transferMutation.execute(() => api.post(`/payments/${payment.id}/transfer`, {
      target_student_id: student.id, reason: reason.trim(), preview_token: preview.preview_token,
    }))
    if (result) onTransferred()
    else setPreview(null)
  }

  return <Dialog open onClose={() => { if (!busy) onClose() }} maxWidth="md">
    <DialogTitle>Transfer payment · {payment.payment_number}</DialogTitle>
    <DialogContent>
      <div className="space-y-4 mt-3">
        <p>Transfer {formatMoney(payment.amount)} to the correct student and family account.</p>
        {error && <Alert severity="error">{error}</Alert>}
        {!preview && <StudentNumberLookup value={studentNumber} onChange={value => {
          setStudentNumber(value); previewMutation.reset(); transferMutation.reset()
        }} onSelect={setStudent} disabled={busy} excludedStudentId={payment.student_id} />}
        {preview && <>
          <div className="grid gap-3 sm:grid-cols-2">
            {(['source', 'target'] as const).map(key => <div key={key} className="rounded border p-3">
              <p className="text-sm text-slate-500">{key === 'source' ? 'From' : 'To'}</p>
              <strong>{preview[key].student_name} · {formatStudentNumberShort(preview[key].student_number)}</strong>
              <p>{preview[key].account_name} · {preview[key].account_number}</p>
              <p className="text-sm mt-2">Available credit: {formatMoney(preview[`${key}_credit_before`])} → {formatMoney(preview[`${key}_credit_after`])}</p>
            </div>)}
          </div>
          {preview.source.billing_account_id === preview.target.billing_account_id
            ? <Alert severity="info">Both students belong to the same family account. Only the payment recipient changes; invoice allocations stay unchanged.</Alert>
            : <>
              <InvoiceImpacts title="Allocations to reverse" rows={preview.removed_allocations} />
              <InvoiceImpacts title="New allocations" rows={preview.new_allocations} />
              <section className="space-y-2">
                <h3 className="font-semibold">Allocation dates for reports</h3>
                <p className="text-sm text-slate-500">Original allocation dates are preserved. Previously unallocated funds are allocated today.</p>
                <div className="overflow-x-auto"><table className="w-full text-sm text-left">
                  <thead><tr><th>Invoice</th><th>Allocation date</th><th>Amount</th></tr></thead>
                  <tbody>{preview.allocation_schedule.map((part, index) => <tr key={index} className="border-t">
                    <td className="py-2">{preview.new_allocations.find(row => row.invoice_id === part.invoice_id)?.invoice_number}</td>
                    <td>{part.created_at ? formatDate(part.created_at) : 'Today (new allocation)'}</td>
                    <td>{formatMoney(part.amount)}</td>
                  </tr>)}</tbody>
                </table></div>
              </section>
            </>}
          <p className="text-sm text-slate-500">The payment date, amount, reference, receipt number and bank reconciliation are preserved. The correction and reason are recorded in the audit history.</p>
        </>}
        <Textarea label="Reason for correction" value={reason} disabled={busy} maxLength={2000}
          onChange={event => setReason(event.target.value)} />
      </div>
    </DialogContent>
    <DialogActions>
      <Button variant="outlined" disabled={busy} onClick={onClose}>Cancel</Button>
      {preview && <Button variant="outlined" disabled={busy} onClick={() => setPreview(null)}>Change student</Button>}
      {preview
        ? <Button disabled={busy || !reason.trim()} onClick={transfer}>{busy ? 'Transferring…' : 'Confirm transfer'}</Button>
        : <Button disabled={busy || !student || !reason.trim()} onClick={review}>{busy ? 'Loading…' : 'Preview transfer'}</Button>}
    </DialogActions>
  </Dialog>
}
