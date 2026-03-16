import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import type { KitOption } from '../../pages/students/types'
import { Typography } from '../ui/Typography'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Textarea } from '../ui/Textarea'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../ui/Dialog'
import { Alert } from '../ui/Alert'
import { Spinner } from '../ui/Spinner'

interface ReservationIssueItem {
  id: number
  item_id: number
  item_name?: string | null
  item_sku?: string | null
  quantity_required: number
  quantity_issued: number
}

export interface ReservationIssueDialogReservation {
  id: number
  invoice_id?: number | null
  invoice_line_id?: number | null
  items: ReservationIssueItem[]
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

interface ReservationIssueDialogProps {
  open: boolean
  reservation: ReservationIssueDialogReservation | null
  onClose: () => void
  onReservationChanged?: () => void | Promise<void>
}

export const ReservationIssueDialog = ({
  open,
  reservation,
  onClose,
  onReservationChanged,
}: ReservationIssueDialogProps) => {
  const [currentReservation, setCurrentReservation] =
    useState<ReservationIssueDialogReservation | null>(null)
  const [issueLines, setIssueLines] = useState<IssueLine[]>([])
  const [notes, setNotes] = useState('')
  const [componentsDialogOpen, setComponentsDialogOpen] = useState(false)
  const [componentsDraft, setComponentsDraft] = useState<ComponentDraft[]>([])

  const {
    execute: issueReservation,
    loading: issuing,
    error: issueError,
    reset: resetIssueMutation,
  } = useApiMutation()
  const {
    execute: configureComponents,
    loading: configuring,
    error: configureError,
    reset: resetConfigureMutation,
  } = useApiMutation<ReservationIssueDialogReservation>()

  const kitsApi = useApi<KitOption[]>('/items/kits', {
    params: { include_inactive: false },
  })
  const variantsApi = useApi<VariantRow[]>('/items/variants', {
    params: { include_inactive: false },
  })
  const invoiceApi = useApi<InvoiceRow>(
    open && currentReservation?.invoice_id
      ? `/invoices/${currentReservation.invoice_id}`
      : null
  )

  useEffect(() => {
    if (!open || !reservation) {
      return
    }
    resetIssueMutation()
    resetConfigureMutation()
    setCurrentReservation(reservation)
    setIssueLines(
      reservation.items.map((item) => ({
        reservation_item_id: item.id,
        quantity: Math.max(0, item.quantity_required - item.quantity_issued),
      }))
    )
    setNotes('')
    setComponentsDialogOpen(false)
  }, [open, reservation, resetConfigureMutation, resetIssueMutation])

  const perItemIssueError = (() => {
    if (!issueError) return null
    const match = issueError.match(/reservation_item (\d+)/i)
    if (!match) return null
    return { reservationItemId: Number(match[1]), message: issueError }
  })()

  const selectedInvoiceLine = (() => {
    if (!currentReservation?.invoice_line_id) return null
    const lines = invoiceApi.data?.lines ?? []
    return (
      lines.find((line) => line.id === currentReservation.invoice_line_id) ?? null
    )
  })()

  const selectedKit = (() => {
    const kitId = selectedInvoiceLine?.kit_id
    if (!kitId) return null
    const kits = kitsApi.data ?? []
    return kits.find((kit) => kit.id === kitId) ?? null
  })()

  const canConfigureComponents = Boolean(selectedKit?.is_editable_components)

  const openConfigureDialog = () => {
    resetConfigureMutation()
    const kit = selectedKit
    if (!currentReservation || !kit || !kit.items?.length) return

    const lineQty = selectedInvoiceLine?.quantity ?? 1
    const draft = kit.items.map((kitItem) => {
      const totalUnits = Math.max(1, kitItem.quantity) * Math.max(1, lineQty)
      const defaultId =
        kitItem.source_type === 'item' ? kitItem.item_id : kitItem.default_item_id
      return {
        unit_item_ids: Array.from(
          { length: totalUnits },
          () => (defaultId ?? '') as number | ''
        ),
      }
    })
    setComponentsDraft(draft)
    setComponentsDialogOpen(true)
  }

  const submitConfigure = async () => {
    if (!currentReservation) return
    resetConfigureMutation()
    const missing = componentsDraft.some((component) =>
      component.unit_item_ids.some((value) => value === '')
    )
    if (missing) return

    const components = componentsDraft.map((component) => {
      const counts = new Map<number, number>()
      for (const unit of component.unit_item_ids) {
        const itemId = unit as number
        counts.set(itemId, (counts.get(itemId) ?? 0) + 1)
      }
      return {
        allocations: Array.from(counts.entries()).map(([item_id, quantity]) => ({
          item_id,
          quantity,
        })),
      }
    })

    const result = await configureComponents(() =>
      api.post(`/reservations/${currentReservation.id}/components`, { components })
    )
    if (!result) return

    setCurrentReservation(result)
    setIssueLines(
      result.items.map((item) => ({
        reservation_item_id: item.id,
        quantity: Math.max(0, item.quantity_required - item.quantity_issued),
      }))
    )
    setComponentsDialogOpen(false)
    await onReservationChanged?.()
  }

  const submitIssue = async () => {
    if (!currentReservation) return
    resetIssueMutation()
    const result = await issueReservation(() =>
      api.post(`/reservations/${currentReservation.id}/issue`, {
        items: issueLines.map((line) => ({
          reservation_item_id: line.reservation_item_id,
          quantity: line.quantity,
        })),
        notes: notes.trim() || null,
      })
    )

    if (!result) return

    onClose()
    await onReservationChanged?.()
  }

  const lineQty = selectedInvoiceLine?.quantity ?? 1
  const variants = variantsApi.data ?? []

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md">
        <DialogCloseButton onClose={onClose} />
        <DialogTitle>Issue reservation items</DialogTitle>
        <DialogContent>
          <div className="space-y-4">
            {canConfigureComponents && (
              <div className="flex gap-2 flex-wrap">
                <Button
                  size="small"
                  variant="outlined"
                  onClick={openConfigureDialog}
                  disabled={
                    configuring ||
                    kitsApi.loading ||
                    variantsApi.loading ||
                    invoiceApi.loading
                  }
                >
                  Configure components
                </Button>
                {(kitsApi.error ||
                  variantsApi.error ||
                  invoiceApi.error ||
                  configureError) && (
                  <Typography
                    variant="caption"
                    color="error"
                    className="self-center"
                  >
                    {kitsApi.error ||
                      variantsApi.error ||
                      invoiceApi.error ||
                      configureError}
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
                  {currentReservation?.items.map((item) => {
                    const line = issueLines.find(
                      (entry) => entry.reservation_item_id === item.id
                    )
                    const remaining = Math.max(
                      0,
                      item.quantity_required - item.quantity_issued
                    )
                    const lineError =
                      perItemIssueError?.reservationItemId === item.id
                        ? perItemIssueError.message
                        : null
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
                              onChange={(event) => {
                                resetIssueMutation()
                                const value = Number(event.target.value) || 0
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
                              <Typography
                                variant="caption"
                                color="error"
                                className="mt-1 block"
                              >
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
            {issueError && !perItemIssueError && (
              <Alert severity="error">{issueError}</Alert>
            )}
            <Textarea
              label="Notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitIssue} disabled={issuing}>
            {issuing ? <Spinner size="small" /> : 'Issue'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={componentsDialogOpen}
        onClose={() => setComponentsDialogOpen(false)}
        maxWidth="lg"
      >
        <DialogCloseButton onClose={() => setComponentsDialogOpen(false)} />
        <DialogTitle>Configure components</DialogTitle>
        <DialogContent>
          {!currentReservation || !selectedKit || !selectedKit.items?.length ? (
            <Alert severity="error">Kit not found.</Alert>
          ) : (
            <div className="grid gap-4 mt-2">
              <Typography variant="body2" color="secondary">
                Quantities are calculated automatically based on line quantity ({lineQty}).
              </Typography>
              {selectedKit.items.map((kitItem, index) => {
                const qty = Math.max(1, kitItem.quantity) * Math.max(1, lineQty)
                if (kitItem.source_type === 'variant') {
                  const variantItems =
                    variants.find((variant) => variant.id === kitItem.variant_id)
                      ?.items ?? []
                  return (
                    <div
                      key={`${selectedKit.id}-comp-${index}`}
                      className="rounded-xl border border-slate-200 bg-white p-3"
                    >
                      <div className="grid gap-3 sm:grid-cols-[1fr_140px] items-end">
                        <div className="grid gap-3">
                          <Typography variant="body2" className="font-medium">
                            {kitItem.variant_name
                              ? `Variant: ${kitItem.variant_name}`
                              : 'Variant'}
                          </Typography>
                          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {componentsDraft[index]?.unit_item_ids.map(
                              (unitId, unitIndex) => (
                                <Select
                                  key={`${selectedKit.id}-comp-${index}-${unitIndex}`}
                                  value={unitId === '' ? '' : String(unitId)}
                                  onChange={(event) =>
                                    setComponentsDraft((prev) =>
                                      prev.map((component, componentIndex) =>
                                        componentIndex === index
                                          ? {
                                              ...component,
                                              unit_item_ids:
                                                component.unit_item_ids.map(
                                                  (value, valueIndex) =>
                                                    valueIndex === unitIndex
                                                      ? event.target.value
                                                        ? Number(
                                                            event.target.value
                                                          )
                                                        : ''
                                                      : value
                                                ),
                                            }
                                          : component
                                      )
                                    )
                                  }
                                  label={`Item ${unitIndex + 1} of ${qty}`}
                                  disabled={variantsApi.loading}
                                  required
                                >
                                  <option value="">Select item</option>
                                  {variantItems.map((item) => (
                                    <option key={item.id} value={item.id}>
                                      {`${item.name} (${item.sku_code})`}
                                    </option>
                                  ))}
                                </Select>
                              )
                            )}
                          </div>
                        </div>
                        <Input label="Total qty" type="number" value={qty} disabled />
                      </div>
                    </div>
                  )
                }

                return (
                  <div
                    key={`${selectedKit.id}-comp-${index}`}
                    className="rounded-xl border border-slate-200 bg-white p-3"
                  >
                    <div className="grid gap-3 sm:grid-cols-[1fr_140px] items-end">
                      <Select
                        value={kitItem.item_id ? String(kitItem.item_id) : ''}
                        onChange={() => {}}
                        label={
                          kitItem.item_name
                            ? `Item: ${kitItem.item_name}`
                            : 'Item'
                        }
                        disabled
                      >
                        <option value="">{kitItem.item_name ?? '—'}</option>
                      </Select>
                      <Input label="Qty" type="number" value={qty} disabled />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            variant="outlined"
            onClick={() => setComponentsDialogOpen(false)}
            disabled={configuring}
          >
            Cancel
          </Button>
          <Button
            onClick={submitConfigure}
            disabled={
              configuring ||
              componentsDraft.some((component) =>
                component.unit_item_ids.some((value) => !value)
              )
            }
          >
            {configuring ? <Spinner size="small" /> : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
