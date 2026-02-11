import { useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'
import { canManageReservations } from '../../utils/permissions'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { ToggleButton, ToggleButtonGroup } from '../../components/ui/ToggleButton'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'
import type { KitOption } from '../students/types'

interface ReservationItem {
  id: number
  item_id: number
  item_name?: string | null
  item_sku?: string | null
  quantity_required: number
  quantity_issued: number
}

interface ReservationRow {
  id: number
  student_id: number
  student_name?: string | null
  invoice_id: number
  invoice_line_id: number
  status: string
  created_at: string
  items: ReservationItem[]
}

interface IssueLine {
  reservation_item_id: number
  quantity: number
}

interface InvoiceLineRow {
  id: number
  kit_id: number
  quantity: number
}

interface InvoiceRow {
  id: number
  lines: InvoiceLineRow[]
}

interface VariantGroupItemRow {
  id: number
  name: string
  sku_code: string
}

interface VariantRow {
  id: number
  name: string
  is_active: boolean
  items: VariantGroupItemRow[]
}

interface ComponentDraft {
  unit_item_ids: Array<number | ''>
}

export const ReservationsPage = () => {
  const { user } = useAuth()
  const canManage = canManageReservations(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active')
  const [selected, setSelected] = useState<ReservationRow | null>(null)
  const [issueLines, setIssueLines] = useState<IssueLine[]>([])
  const [issueDialogOpen, setIssueDialogOpen] = useState(false)
  const [componentsDialogOpen, setComponentsDialogOpen] = useState(false)
  const [componentsDraft, setComponentsDraft] = useState<ComponentDraft[]>([])
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [notes, setNotes] = useState('')

  const reservationsUrl = useMemo(() => {
    const params = { page: page + 1, limit }
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value))
    })
    return `/reservations?${searchParams.toString()}`
  }, [page, limit])

  const { data: reservationsData, loading, error, refetch } = useApi<PaginatedResponse<ReservationRow>>(reservationsUrl)
  const { execute: issueReservation, loading: issuing, error: issueError, reset: resetIssueMutation } = useApiMutation()
  const { execute: cancelReservation, loading: cancelling, error: cancelError } = useApiMutation()
  const {
    execute: configureComponents,
    loading: configuring,
    error: configureError,
    reset: resetConfigureMutation,
  } = useApiMutation<ReservationRow>()

  const kitsApi = useApi<KitOption[]>('/items/kits', { params: { include_inactive: false } })
  const variantsApi = useApi<VariantRow[]>('/items/variants', { params: { include_inactive: false } })
  const invoiceApi = useApi<InvoiceRow>(
    issueDialogOpen && selected?.invoice_id ? `/invoices/${selected.invoice_id}` : null
  )

  const rows = reservationsData?.items || []
  const total = reservationsData?.total || 0

  const perItemIssueError = (() => {
    if (!issueError) return null
    const match = issueError.match(/reservation_item (\d+)/i)
    if (!match) return null
    return { reservationItemId: Number(match[1]), message: issueError }
  })()

  const openIssueDialog = (reservation: ReservationRow) => {
    resetIssueMutation()
    setSelected(reservation)
    setIssueLines(
      reservation.items.map((item) => ({
        reservation_item_id: item.id,
        quantity: Math.max(0, item.quantity_required - item.quantity_issued),
      }))
    )
    setNotes('')
    setIssueDialogOpen(true)
  }

  const selectedInvoiceLine = (() => {
    if (!selected?.invoice_line_id) return null
    const lines = invoiceApi.data?.lines ?? []
    return lines.find((line) => line.id === selected.invoice_line_id) ?? null
  })()

  const selectedKit = (() => {
    const kitId = selectedInvoiceLine?.kit_id
    if (!kitId) return null
    const kits = kitsApi.data ?? []
    return kits.find((k) => k.id === kitId) ?? null
  })()

  const canConfigureComponents = Boolean(selectedKit?.is_editable_components)

  const openConfigureDialog = () => {
    resetConfigureMutation()
    const kit = selectedKit
    if (!selected || !kit || !kit.items?.length) return

    const lineQty = selectedInvoiceLine?.quantity ?? 1
    const draft = kit.items.map((kitItem) => {
      const totalUnits = Math.max(1, kitItem.quantity) * Math.max(1, lineQty)
      const defaultId = kitItem.source_type === 'item' ? kitItem.item_id : kitItem.default_item_id
      return {
        unit_item_ids: Array.from({ length: totalUnits }, () => (defaultId ?? '') as number | ''),
      }
    })
    setComponentsDraft(draft)
    setComponentsDialogOpen(true)
  }

  const submitConfigure = async () => {
    if (!selected) return
    resetConfigureMutation()
    const missing = componentsDraft.some((c) => c.unit_item_ids.some((v) => v === ''))
    if (missing) return

    const components = componentsDraft.map((c) => {
      const counts = new Map<number, number>()
      for (const unit of c.unit_item_ids) {
        const id = unit as number
        counts.set(id, (counts.get(id) ?? 0) + 1)
      }
      return {
        allocations: Array.from(counts.entries()).map(([item_id, quantity]) => ({ item_id, quantity })),
      }
    })
    const result = await configureComponents(() =>
      api.post(`/reservations/${selected.id}/components`, { components })
    )
    if (result) {
      setSelected(result)
      setIssueLines(
        result.items.map((item) => ({
          reservation_item_id: item.id,
          quantity: Math.max(0, item.quantity_required - item.quantity_issued),
        }))
      )
      setComponentsDialogOpen(false)
      refetch()
    }
  }

  const submitIssue = async () => {
    if (!selected) return
    resetIssueMutation()
    const result = await issueReservation(() =>
      api.post(`/reservations/${selected.id}/issue`, {
        items: issueLines.map((line) => ({
          reservation_item_id: line.reservation_item_id,
          quantity: line.quantity,
        })),
        notes: notes.trim() || null,
      })
    )

    if (result) {
      setIssueDialogOpen(false)
      refetch()
    }
  }

  const openCancelDialog = (reservation: ReservationRow) => {
    setSelected(reservation)
    setCancelReason('')
    setCancelDialogOpen(true)
  }

  const submitCancel = async () => {
    if (!selected) {
      return
    }
    const result = await cancelReservation(() =>
      api.post(`/reservations/${selected.id}/cancel`, {
        reason: cancelReason.trim() || null,
      })
    )

    if (result) {
      setCancelDialogOpen(false)
      refetch()
    }
  }

  const filteredRows = rows.filter((row) => {
    if (statusFilter !== 'active') {
      return true
    }
    return row.status === 'pending' || row.status === 'partial'
  })

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Reservations
      </Typography>

      <div className="flex gap-4 mb-4 flex-wrap">
        <ToggleButtonGroup
          size="small"
          value={statusFilter}
          exclusive
          onChange={(_, value) => {
            if (value && (value === 'all' || value === 'active')) {
              setPage(0)
              setStatusFilter(value)
            }
          }}
        >
          <ToggleButton value="active">Active</ToggleButton>
          <ToggleButton value="all">All</ToggleButton>
        </ToggleButtonGroup>
      </div>

      {(error || issueError || cancelError) && (
        <Alert severity="error" className="mb-4">
          {error || issueError || cancelError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Reservation #</TableHeaderCell>
              <TableHeaderCell>Student</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Items</TableHeaderCell>
              <TableHeaderCell>Created</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
              {filteredRows.map((row) => (
                <TableRow key={row.id}>
                 <TableCell>{row.id}</TableCell>
                 <TableCell>{row.student_name ?? `Student #${row.student_id}`}</TableCell>
                 <TableCell>{row.status}</TableCell>
                 <TableCell>{row.items.length}</TableCell>
                 <TableCell>{formatDateTime(row.created_at)}</TableCell>
                 <TableCell align="right">
                  {canManage ? (
                    <>
                      {row.status === 'pending' || row.status === 'partial' ? (
                        <div className="flex gap-2 justify-end">
                          <Button size="small" variant="outlined" onClick={() => openIssueDialog(row)}>
                            Issue
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={() => openCancelDialog(row)}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        '—'
                      )}
                    </>
                  ) : (
                      '—'
                    )}
                 </TableCell>
                </TableRow>
              ))}
            {loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Spinner size="small" />
                </td>
              </TableRow>
            )}
            {!filteredRows.length && !loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Typography color="secondary">No reservations found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <TablePagination
        count={statusFilter === 'active' ? filteredRows.length : total}
        page={page}
        onPageChange={(nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(newLimit) => {
          setLimit(newLimit)
          setPage(0)
        }}
      />

      <Dialog open={issueDialogOpen} onClose={() => setIssueDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setIssueDialogOpen(false)} />
        <DialogTitle>Issue reservation items</DialogTitle>
        <DialogContent>
          <div className="space-y-4">
            {canConfigureComponents && (
              <div className="flex gap-2 flex-wrap">
                <Button
                  size="small"
                  variant="outlined"
                  onClick={openConfigureDialog}
                  disabled={configuring || kitsApi.loading || variantsApi.loading || invoiceApi.loading}
                >
                  Configure components
                </Button>
                {(kitsApi.error || variantsApi.error || invoiceApi.error || configureError) && (
                  <Typography variant="caption" color="error" className="self-center">
                    {kitsApi.error || variantsApi.error || invoiceApi.error || configureError}
                  </Typography>
                )}
              </div>
            )}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Item</TableHeaderCell>
                    <TableHeaderCell>Required</TableHeaderCell>
                    <TableHeaderCell>Issued</TableHeaderCell>
                    <TableHeaderCell>To issue</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selected?.items.map((item) => {
                    const line = issueLines.find((entry) => entry.reservation_item_id === item.id)
                    const remaining = Math.max(0, item.quantity_required - item.quantity_issued)
                    const lineError =
                      perItemIssueError?.reservationItemId === item.id ? perItemIssueError.message : null
                      return (
                        <TableRow key={item.id}>
                         <TableCell>{item.item_name ?? '—'}</TableCell>
                         <TableCell>{item.quantity_required}</TableCell>
                         <TableCell>{item.quantity_issued}</TableCell>
                          <TableCell>
                          <div>
                            <Input
                              type="number"
                              value={line?.quantity ?? remaining}
                              onChange={(e) => {
                                resetIssueMutation()
                                const value = Number(e.target.value) || 0
                                setIssueLines((prev) =>
                                  prev.map((entry) =>
                                    entry.reservation_item_id === item.id
                                      ? { ...entry, quantity: value }
                                      : entry
                                  )
                                )
                              }}
                              min={0}
                              max={remaining}
                              error={lineError || undefined}
                              className="w-24"
                            />
                            {lineError && (
                              <Typography variant="caption" color="error" className="mt-1 block">
                                {lineError}
                              </Typography>
                            )}
                            </div>
                         </TableCell>
                        </TableRow>
                      )
                  })}
                </TableBody>
              </Table>
            </div>
            <Textarea
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setIssueDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitIssue} disabled={issuing}>
            {issuing ? <Spinner size="small" /> : 'Issue'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={componentsDialogOpen} onClose={() => setComponentsDialogOpen(false)} maxWidth="lg">
        <DialogCloseButton onClose={() => setComponentsDialogOpen(false)} />
        <DialogTitle>Configure components</DialogTitle>
        <DialogContent>
          {(() => {
            const kit = selectedKit
            const lineQty = selectedInvoiceLine?.quantity ?? 1
            const variants = variantsApi.data ?? []
            if (!selected || !kit || !kit.items?.length) {
              return <Alert severity="error">Kit not found.</Alert>
            }
            return (
              <div className="grid gap-4 mt-2">
                <Typography variant="body2" color="secondary">
                  Quantities are calculated automatically based on line quantity ({lineQty}).
                </Typography>
                {kit.items.map((ki, index) => {
                  const qty = Math.max(1, ki.quantity) * Math.max(1, lineQty)
                  if (ki.source_type === 'variant') {
                    const variantItems = variants.find((v) => v.id === ki.variant_id)?.items ?? []
                    return (
                      <div key={`${kit.id}-comp-${index}`} className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="grid gap-3 sm:grid-cols-[1fr_140px] items-end">
                          <div className="grid gap-3">
                            <Typography variant="body2" className="font-medium">
                              {ki.variant_name ? `Variant: ${ki.variant_name}` : 'Variant'}
                            </Typography>
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                              {componentsDraft[index]?.unit_item_ids.map((unitId, unitIndex) => (
                                <Select
                                  key={`${kit.id}-comp-${index}-${unitIndex}`}
                                  value={unitId === '' ? '' : String(unitId)}
                                  onChange={(event) =>
                                    setComponentsDraft((prev) =>
                                      prev.map((c, i) =>
                                        i === index
                                          ? {
                                              ...c,
                                              unit_item_ids: c.unit_item_ids.map((v, vi) =>
                                                vi === unitIndex
                                                  ? event.target.value
                                                    ? Number(event.target.value)
                                                    : ''
                                                  : v
                                              ),
                                            }
                                          : c
                                      )
                                    )
                                  }
                                  label={`Item ${unitIndex + 1} of ${qty}`}
                                  disabled={variantsApi.loading}
                                  required
                                >
                                  <option value="">Select item</option>
                                  {variantItems.map((it) => (
                                    <option key={it.id} value={it.id}>
                                      {`${it.name} (${it.sku_code})`}
                                    </option>
                                  ))}
                                </Select>
                              ))}
                            </div>
                          </div>
                          <Input label="Total qty" type="number" value={qty} disabled />
                        </div>
                      </div>
                    )
                  }

                  return (
                    <div key={`${kit.id}-comp-${index}`} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="grid gap-3 sm:grid-cols-[1fr_140px] items-end">
                        <Select
                          value={ki.item_id ? String(ki.item_id) : ''}
                          onChange={() => {}}
                          label={ki.item_name ? `Item: ${ki.item_name}` : 'Item'}
                          disabled
                        >
                          <option value="">
                            {ki.item_name ?? '—'}
                          </option>
                        </Select>
                        <Input label="Qty" type="number" value={qty} disabled />
                      </div>
                    </div>
                  )
                })}
              </div>
            )
          })()}
        </DialogContent>
      <DialogActions>
          <Button variant="outlined" onClick={() => setComponentsDialogOpen(false)} disabled={configuring}>
            Cancel
          </Button>
          <Button
            onClick={submitConfigure}
            disabled={configuring || componentsDraft.some((c) => c.unit_item_ids.some((v) => !v))}
          >
            {configuring ? <Spinner size="small" /> : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setCancelDialogOpen(false)} />
        <DialogTitle>Cancel reservation</DialogTitle>
        <DialogContent>
          <Textarea
            label="Reason"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            rows={3}
          />
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCancelDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitCancel} disabled={cancelling}>
            {cancelling ? <Spinner size="small" /> : 'Cancel reservation'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
