import { useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'
import { canCancelIssuance } from '../../utils/permissions'
import { Button } from '../../components/ui/Button'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface IssuanceItem {
  id: number
  item_name?: string | null
  item_sku?: string | null
  quantity: number
}

interface IssuanceRow {
  id: number
  issuance_number: string
  issuance_type: string
  recipient_type: string
  recipient_name: string
  status: string
  issued_at: string
  notes?: string | null
  items: IssuanceItem[]
}

export const IssuancesPage = () => {
  const { user } = useAuth()
  const canCancel = canCancelIssuance(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [typeFilter, setTypeFilter] = useState<string | 'all'>('all')
  const [recipientFilter, setRecipientFilter] = useState<string | 'all'>('all')
  const [selected, setSelected] = useState<IssuanceRow | null>(null)

  const params = useMemo(() => {
    const p: Record<string, string | number> = { page: page + 1, limit }
    if (typeFilter !== 'all') {
      p.issuance_type = typeFilter
    }
    if (recipientFilter !== 'all') {
      p.recipient_type = recipientFilter
    }
    return p
  }, [page, limit, typeFilter, recipientFilter])

  const url = useMemo(() => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value))
    })
    return `/inventory/issuances?${searchParams.toString()}`
  }, [params])

  const { data, loading, error, refetch } = useApi<PaginatedResponse<IssuanceRow>>(url)
  const { execute: cancelIssuanceApi, loading: _cancelling, error: cancelError } = useApiMutation()

  const rows = data?.items || []
  const total = data?.total || 0

  const cancelIssuance = async (issuanceId: number) => {
    const result = await cancelIssuanceApi(() => api.post(`/inventory/issuances/${issuanceId}/cancel`))
    if (result) {
      setSelected(null)
      refetch()
    }
  }

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Issuances
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="min-w-[160px]">
          <Select
            label="Type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="internal">Internal</option>
            <option value="reservation">Reservation</option>
          </Select>
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Recipient"
            value={recipientFilter}
            onChange={(e) => setRecipientFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="employee">Employee</option>
            <option value="department">Department</option>
            <option value="student">Student</option>
          </Select>
        </div>
      </div>

      {(error || cancelError) && (
        <Alert severity="error" className="mb-4">
          {error || cancelError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Issuance #</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Recipient</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Issued at</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.issuance_number}</TableCell>
                <TableCell>{row.issuance_type}</TableCell>
                <TableCell>{row.recipient_name}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell>{formatDateTime(row.issued_at)}</TableCell>
                <TableCell align="right">
                  <div className="flex gap-2 justify-end">
                    <Button size="small" variant="outlined" onClick={() => setSelected(row)}>
                      View
                    </Button>
                    {canCancel && (
                      <Button size="small" variant="outlined" color="error" onClick={() => cancelIssuance(row.id)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <TableCell colSpan={6} align="center" className="py-8">
                  <Spinner size="medium" />
                </TableCell>
              </TableRow>
            )}
            {!rows.length && !loading && (
              <TableRow>
                <TableCell colSpan={6} align="center" className="py-8">
                  <Typography color="secondary">No issuances found</Typography>
                </TableCell>
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
        />
      </div>

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} maxWidth="md" fullWidth>
        <DialogTitle>Issuance details</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Typography variant="body2">Issuance #: {selected?.issuance_number}</Typography>
            <Typography variant="body2">Recipient: {selected?.recipient_name}</Typography>
            <Typography variant="body2">Status: {selected?.status}</Typography>
            <div className="mt-2">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Item</TableHeaderCell>
                    <TableHeaderCell>SKU</TableHeaderCell>
                    <TableHeaderCell>Qty</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selected?.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.item_name ?? '—'}</TableCell>
                      <TableCell>{item.item_sku ?? '—'}</TableCell>
                      <TableCell>{item.quantity}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setSelected(null)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
