import { useMemo, useState } from 'react'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/format'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

interface AuditEntry {
  id: number
  user_id: number | null
  user_full_name: string | null
  action: string
  entity_type: string
  entity_id: number
  entity_identifier: string | null
  comment: string | null
  created_at: string
}

export const AuditTrailPage = () => {
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [entityType, setEntityType] = useState('')
  const [actionFilter, setActionFilter] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    if (entityType) params.entity_type = entityType
    if (actionFilter) params.action = actionFilter
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/accountant/audit-trail?${sp.toString()}`
  }, [page, limit, dateFrom, dateTo, entityType, actionFilter])

  const { data, loading, error } = useApi<PaginatedResponse<AuditEntry>>(url)

  const items = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Audit Trail
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap items-center">
        <div className="min-w-[160px]">
          <Input
            label="Date from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div className="min-w-[160px]">
          <Input
            label="Date to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
        <div className="min-w-[140px]">
          <Select
            label="Entity type"
            value={entityType || '_'}
            onChange={(e) => setEntityType(e.target.value === '_' ? '' : e.target.value)}
          >
            <option value="_">All</option>
            <option value="Payment">Payment</option>
            <option value="Invoice">Invoice</option>
            <option value="PurchaseOrder">PurchaseOrder</option>
            <option value="GoodsReceived">GoodsReceived</option>
            <option value="Student">Student</option>
          </Select>
        </div>
        <div className="min-w-[120px]">
          <Select
            label="Action"
            value={actionFilter || '_'}
            onChange={(e) => setActionFilter(e.target.value === '_' ? '' : e.target.value)}
          >
            <option value="_">All</option>
            <option value="CREATE">CREATE</option>
            <option value="UPDATE">UPDATE</option>
            <option value="CANCEL">CANCEL</option>
            <option value="APPROVE">APPROVE</option>
          </Select>
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Date / Time</TableHeaderCell>
              <TableHeaderCell>User</TableHeaderCell>
              <TableHeaderCell>Action</TableHeaderCell>
              <TableHeaderCell>Document</TableHeaderCell>
              <TableHeaderCell>Details</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDate(row.created_at)}</TableCell>
                <TableCell>{row.user_full_name ?? '—'}</TableCell>
                <TableCell>{row.action}</TableCell>
                <TableCell>
                  {row.entity_identifier ?? `${row.entity_type} #${row.entity_id}`}
                </TableCell>
                <TableCell>{row.comment ?? '—'}</TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!items.length && !loading && (
              <TableRow>
                <td colSpan={5} className="px-4 py-8 text-center">
                  <Typography color="secondary">No audit entries found</Typography>
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
    </div>
  )
}
