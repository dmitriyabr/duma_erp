import { useMemo, useState } from 'react'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TablePagination, TableRow } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { formatDate, formatMoney } from '../../utils/format'

type MpesaEventRow = {
  id: number
  trans_id: string
  business_short_code?: string | null
  bill_ref_number?: string | null
  derived_student_number?: string | null
  amount: string
  status: string
  error_message?: string | null
  payment_id?: number | null
  received_at: string
}

type LinkResponse = {
  id: number
  payment_number: string
  receipt_number?: string | null
  student_id: number
  amount: number
  payment_method: string
  payment_date: string
  reference?: string | null
  status: string
}

export const MpesaUnmatchedPage = () => {
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)

  const [linkDialog, setLinkDialog] = useState<{
    open: boolean
    event: MpesaEventRow | null
    studentId: string
  }>({ open: false, event: null, studentId: '' })

  const url = useMemo(() => {
    const sp = new URLSearchParams()
    sp.append('page', String(page + 1))
    sp.append('limit', String(limit))
    return `/mpesa/c2b/events/unmatched?${sp.toString()}`
  }, [page, limit])

  const { data, loading, error, refetch } = useApi<PaginatedResponse<MpesaEventRow>>(url)
  const rows = data?.items ?? []
  const total = data?.total ?? 0

  const {
    execute: linkEvent,
    loading: linking,
    error: linkError,
    reset: resetLink,
  } = useApiMutation<LinkResponse>()

  const openLink = (event: MpesaEventRow) => {
    resetLink()
    setLinkDialog({ open: true, event, studentId: '' })
  }

  const closeLink = () => {
    setLinkDialog({ open: false, event: null, studentId: '' })
    resetLink()
  }

  const submitLink = async () => {
    if (!linkDialog.event) return
    const sid = Number(linkDialog.studentId)
    if (!Number.isFinite(sid) || sid <= 0) return

    const res = await linkEvent(() =>
      api.post(`/mpesa/c2b/events/${linkDialog.event!.id}/link`, { student_id: sid })
    )
    if (res) {
      closeLink()
      await refetch()
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">M-Pesa unmatched payments</Typography>
      </div>

      <Typography variant="body2" color="secondary" className="mb-4">
        These entries are M-Pesa callback events that could not be matched to a student using BillRefNumber (Admission#).
        Link an event to a student to create a payment and top up the student balance.
      </Typography>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Trans ID</TableHeaderCell>
              <TableHeaderCell>BillRefNumber</TableHeaderCell>
              <TableHeaderCell>Derived student#</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{formatDate(r.received_at)}</TableCell>
                <TableCell className="font-mono text-xs">{r.trans_id}</TableCell>
                <TableCell className="font-mono text-xs">{r.bill_ref_number ?? ''}</TableCell>
                <TableCell className="font-mono text-xs">{r.derived_student_number ?? ''}</TableCell>
                <TableCell align="right">{formatMoney(Number(r.amount))}</TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <span>{r.status}</span>
                    {r.error_message && (
                      <span className="text-xs text-warning">{r.error_message}</span>
                    )}
                  </div>
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => openLink(r)}
                    disabled={linking}
                  >
                    Link to student
                  </Button>
                </TableCell>
              </TableRow>
            ))}

            {loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!rows.length && !loading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Typography color="secondary">No unmatched events</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>

        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(newLimit) => {
            setLimit(newLimit)
            setPage(0)
          }}
          rowsPerPageOptions={[25, 50, 100]}
        />
      </div>

      <Dialog open={linkDialog.open} onClose={closeLink} maxWidth="sm" fullWidth>
        <DialogCloseButton onClose={closeLink} />
        <DialogTitle>Link event to student</DialogTitle>
        <DialogContent>
          <div className="space-y-4">
            <Typography variant="body2" color="secondary">
              Event: <code>{linkDialog.event?.trans_id}</code>
              {linkDialog.event?.bill_ref_number ? (
                <>
                  {' '}
                  · BillRef: <code>{linkDialog.event?.bill_ref_number}</code>
                </>
              ) : null}
            </Typography>

            <Input
              label="Student ID"
              value={linkDialog.studentId}
              onChange={(e) => setLinkDialog((s) => ({ ...s, studentId: e.target.value }))}
              placeholder="123"
              required
            />

            {linkError && <Alert severity="error">{linkError}</Alert>}
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={closeLink} disabled={linking}>
            Cancel
          </Button>
          <Button onClick={submitLink} disabled={linking}>
            {linking ? (
              <span className="flex items-center gap-2">
                <Spinner size="small" />
                Linking
              </span>
            ) : (
              'Link'
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}

