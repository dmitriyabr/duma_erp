import { useMemo, useState } from 'react'
import { Zap } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { canManageStudents } from '../../utils/permissions'
import { useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Spinner } from '../ui/Spinner'
import { Typography } from '../ui/Typography'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../ui/Dialog'
import type { PaymentResponse } from '../../pages/students/types'

type MpesaSandboxEvent = {
  id: number
  trans_id: string
  bill_ref_number?: string | null
  derived_student_number?: string | null
  amount: string
  status: string
  error_message?: string | null
  payment_id?: number | null
  received_at: string
}

type SandboxTopUpResponse = {
  event: MpesaSandboxEvent
  payment?: PaymentResponse | null
}

export const MpesaSandboxTopUpWidget = () => {
  const { user } = useAuth()
  const isDev = import.meta.env.DEV
  const canShow = isDev && canManageStudents(user)

  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    student_id: '',
    bill_ref_number: '',
    amount: '5000.00',
    trans_id: '',
    trans_time: '',
    msisdn: '',
    first_name: '',
    last_name: '',
  })
  const { execute, loading, error, data, reset } = useApiMutation<SandboxTopUpResponse>()

  const lastResult = data

  const payload = useMemo(() => {
    const base: Record<string, unknown> = {
      amount: form.amount,
    }

    const studentId = form.student_id.trim()
    const billRef = form.bill_ref_number.trim()

    if (studentId) {
      base.student_id = Number(studentId)
    } else if (billRef) {
      base.bill_ref_number = billRef
    }

    if (form.trans_id.trim()) base.trans_id = form.trans_id.trim()
    if (form.trans_time.trim()) base.trans_time = form.trans_time.trim()
    if (form.msisdn.trim()) base.msisdn = form.msisdn.trim()
    if (form.first_name.trim()) base.first_name = form.first_name.trim()
    if (form.last_name.trim()) base.last_name = form.last_name.trim()

    return base
  }, [form])

  if (!canShow) return null

  const submit = async () => {
    reset()
    await execute(() => api.post('/mpesa/c2b/sandbox/topup', payload))
  }

  const close = () => {
    setOpen(false)
    reset()
  }

  return (
    <>
      <button
        type="button"
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-slate-900 text-white px-4 py-3 shadow-lg hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-900"
        onClick={() => setOpen(true)}
        aria-label="M-Pesa sandbox top-up"
      >
        <Zap className="w-4 h-4" />
        <span className="text-sm font-medium">M-Pesa top-up</span>
      </button>

      <Dialog open={open} onClose={close} maxWidth="sm" fullWidth>
        <DialogCloseButton onClose={close} />
        <DialogTitle>M-Pesa sandbox top-up (dev)</DialogTitle>
        <DialogContent>
          <div className="space-y-4">
            <Typography variant="body2" color="secondary">
              Uses endpoint <code>/api/v1/mpesa/c2b/sandbox/topup</code>. Visible only in dev and only for Admin/SuperAdmin.
            </Typography>

            <div className="grid grid-cols-1 gap-3">
              <Input
                label="Student ID (optional)"
                value={form.student_id}
                onChange={(e) => setForm((s) => ({ ...s, student_id: e.target.value }))}
                placeholder="123"
              />
              <Input
                label="BillRefNumber (optional)"
                value={form.bill_ref_number}
                onChange={(e) => setForm((s) => ({ ...s, bill_ref_number: e.target.value }))}
                placeholder="26123 or STU-2026-000123"
                helperText="If Student ID is provided, BillRefNumber will be generated automatically."
              />
              <Input
                label="Amount"
                value={form.amount}
                onChange={(e) => setForm((s) => ({ ...s, amount: e.target.value }))}
                placeholder="5000.00"
                required
              />
            </div>

            <div className="grid grid-cols-1 gap-3">
              <Input
                label="Trans ID (optional)"
                value={form.trans_id}
                onChange={(e) => setForm((s) => ({ ...s, trans_id: e.target.value }))}
                placeholder="MPESA-DEV-0001"
              />
              <Input
                label="Trans Time (optional, YYYYMMDDHHMMSS)"
                value={form.trans_time}
                onChange={(e) => setForm((s) => ({ ...s, trans_time: e.target.value }))}
                placeholder="20260227123045"
              />
              <Input
                label="MSISDN (optional)"
                value={form.msisdn}
                onChange={(e) => setForm((s) => ({ ...s, msisdn: e.target.value }))}
                placeholder="+254700000001"
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="First name (optional)"
                  value={form.first_name}
                  onChange={(e) => setForm((s) => ({ ...s, first_name: e.target.value }))}
                />
                <Input
                  label="Last name (optional)"
                  value={form.last_name}
                  onChange={(e) => setForm((s) => ({ ...s, last_name: e.target.value }))}
                />
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-error/30 bg-error/5 p-3">
                <Typography variant="body2" className="text-error">
                  {error}
                </Typography>
              </div>
            )}

            {lastResult && (
              <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
                <Typography variant="body2">
                  Event: <code>{lastResult.event.trans_id}</code> · status:{' '}
                  <code>{lastResult.event.status}</code>
                </Typography>
                {lastResult.payment ? (
                  <Typography variant="body2">
                    Payment created: <code>{lastResult.payment.receipt_number ?? lastResult.payment.payment_number}</code> · amount:{' '}
                    <code>{String(lastResult.payment.amount)}</code>
                  </Typography>
                ) : (
                  <Typography variant="body2" color="secondary">
                    Payment not created (unmatched/ignored).
                  </Typography>
                )}
                {lastResult.event.error_message && (
                  <Typography variant="body2" className="text-warning">
                    {lastResult.event.error_message}
                  </Typography>
                )}
              </div>
            )}
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={close} disabled={loading}>
            Close
          </Button>
          <Button onClick={submit} disabled={loading}>
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner size="small" />
                Sending
              </span>
            ) : (
              'Simulate top-up'
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

