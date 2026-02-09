import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Trash2 } from 'lucide-react'
import { useAuth } from '../../../auth/AuthContext'
import { useApi, useApiMutation } from '../../../hooks/useApi'
import { api, unwrapResponse } from '../../../services/api'
import { INVOICE_LIST_LIMIT } from '../../../constants/pagination'
import { canInvoiceTerm } from '../../../utils/permissions'
import { formatDate, formatMoney } from '../../../utils/format'
import type {
  DiscountValueType,
  InvoiceDetail,
  InvoiceLine,
  InvoiceSummary,
  KitOption,
  PaginatedResponse,
} from '../types'
import { getDefaultDueDate, parseNumber } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Alert } from '../../../components/ui/Alert'
import { Button } from '../../../components/ui/Button'
import { Chip } from '../../../components/ui/Chip'
import { Input } from '../../../components/ui/Input'
import { Select } from '../../../components/ui/Select'
import { Switch } from '../../../components/ui/Switch'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../../components/ui/Dialog'
import { Spinner } from '../../../components/ui/Spinner'

interface InvoicesTabProps {
  studentId: number
  onError: (message: string) => void
  onDebtChange: () => void
  /** When provided, use instead of own fetch — avoids duplicate GET /invoices from parent (StudentDetailPage). */
  initialInvoices?: InvoiceSummary[] | null
  invoicesLoading?: boolean
}

export const InvoicesTab = ({
  studentId,
  onError,
  onDebtChange,
  initialInvoices,
  invoicesLoading: parentInvoicesLoading,
}: InvoicesTabProps) => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [invoiceSearch, setInvoiceSearch] = useState('')
  const [showCancelledInvoices, setShowCancelledInvoices] = useState(false)
  const [termInvoiceMessage, setTermInvoiceMessage] = useState<string | null>(null)
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | null>(null)
  const [lineForm, setLineForm] = useState({
    kit_id: '',
    quantity: 1,
    discount_amount: '',
  })
  const [lineDialogOpen, setLineDialogOpen] = useState(false)
  const [issueDialogOpen, setIssueDialogOpen] = useState(false)
  const [issueDueDate, setIssueDueDate] = useState('')
  const [discountDialogOpen, setDiscountDialogOpen] = useState(false)
  const [discountForm, setDiscountForm] = useState({
    value_type: 'percentage' as DiscountValueType,
    value: '',
    reason_text: '',
  })
  const [discountLineId, setDiscountLineId] = useState<number | null>(null)
  const [downloadingPdf, setDownloadingPdf] = useState(false)

  const invoicesApi = useApi<PaginatedResponse<InvoiceSummary>>(
    initialInvoices === undefined ? '/invoices' : null,
    initialInvoices === undefined
      ? {
          params: {
            student_id: studentId,
            limit: INVOICE_LIST_LIMIT,
            page: 1,
            ...(invoiceSearch.trim() && { search: invoiceSearch.trim() }),
          },
        }
      : undefined,
    initialInvoices === undefined ? [studentId, invoiceSearch] : []
  )
  const activeTermApi = useApi<{ id: number } | null>('/terms/active')
  const activeTermIdForApi = activeTermApi.data?.id ?? null
  const termInvoicesApi = useApi<PaginatedResponse<InvoiceSummary>>(
    activeTermIdForApi ? '/invoices' : null,
    {
      params: {
        student_id: studentId,
        term_id: activeTermIdForApi,
        limit: INVOICE_LIST_LIMIT,
        page: 1,
      },
    },
    [studentId, activeTermIdForApi]
  )
  const kitsApi = useApi<KitOption[]>('/items/kits', { params: { include_inactive: true } })
  const invoiceDetailApi = useApi<InvoiceDetail>(
    selectedInvoiceId ? `/invoices/${selectedInvoiceId}` : null,
    {},
    [selectedInvoiceId]
  )

  const generateTermMutation = useApiMutation<unknown>()
  const addLineMutation = useApiMutation<InvoiceDetail>()
  const removeLineMutation = useApiMutation<unknown>()
  const issueMutation = useApiMutation<unknown>()
  const cancelMutation = useApiMutation<unknown>()
  const discountMutation = useApiMutation<unknown>()

  const invoicesFromApi = invoicesApi.data?.items ?? []
  const invoices = initialInvoices !== undefined ? (initialInvoices ?? []) : invoicesFromApi
  const invoicesLoading = parentInvoicesLoading ?? invoicesApi.loading
  const activeTermId = activeTermApi.data?.id ?? null
  const termInvoiceExists = useMemo(() => {
    const items = termInvoicesApi.data?.items ?? []
    return items.some((inv) => {
      const status = inv.status?.toLowerCase()
      if (status === 'cancelled' || status === 'void') return false
      return ['school_fee', 'transport'].includes(inv.invoice_type)
    })
  }, [termInvoicesApi.data])
  const termInvoiceLoading = generateTermMutation.loading
  const kits = kitsApi.data ?? []
  const selectedInvoice = invoiceDetailApi.data ?? null
  const loading =
    addLineMutation.loading ||
    removeLineMutation.loading ||
    issueMutation.loading ||
    cancelMutation.loading ||
    discountMutation.loading

  useEffect(() => {
    if (invoicesApi.error) onError(invoicesApi.error)
  }, [invoicesApi.error, onError])

  const byStatus = showCancelledInvoices
    ? invoices
    : invoices.filter((invoice) => {
        const status = invoice.status?.toLowerCase()
        return status !== 'cancelled' && status !== 'void'
      })
  const visibleInvoices =
    initialInvoices !== undefined && invoiceSearch.trim()
      ? byStatus.filter((inv) =>
          inv.invoice_number?.toLowerCase().includes(invoiceSearch.trim().toLowerCase())
        )
      : byStatus

  const generateTermInvoices = async () => {
    if (!activeTermId) return
    generateTermMutation.reset()
    const ok = await generateTermMutation.execute(() =>
      api
        .post('/invoices/generate-term-invoices/student', {
          term_id: activeTermId,
          student_id: studentId,
        })
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      setTermInvoiceMessage('Term invoices generated.')
      invoicesApi.refetch()
      termInvoicesApi.refetch()
      onDebtChange()
    } else if (generateTermMutation.error) {
      onError(generateTermMutation.error)
    }
  }

  const openInvoiceDetail = (invoice: InvoiceSummary) => {
    setSelectedInvoiceId(invoice.id)
  }

  const closeInvoiceDetail = () => {
    setSelectedInvoiceId(null)
    setLineDialogOpen(false)
  }

  const openAddLine = () => {
    if (!selectedInvoice) return
    setLineForm({ kit_id: '', quantity: 1, discount_amount: '' })
    setLineDialogOpen(true)
  }

  const submitLine = async () => {
    if (!selectedInvoice) return
    if (!lineForm.kit_id) {
      onError('Select a kit to add to the invoice.')
      return
    }
    const payload = {
      item_id: null as number | null,
      kit_id: Number(lineForm.kit_id),
      quantity: Number(lineForm.quantity),
      discount_amount: lineForm.discount_amount ? Number(lineForm.discount_amount) : 0,
    }
    addLineMutation.reset()
    const refreshed = await addLineMutation.execute(() =>
      api
        .post(`/invoices/${selectedInvoice.id}/lines`, payload)
        .then(() => api.get(`/invoices/${selectedInvoice.id}`))
        .then((r) => ({ data: { data: unwrapResponse<InvoiceDetail>(r) } }))
    )
    if (refreshed != null) {
      setLineDialogOpen(false)
      invoiceDetailApi.refetch()
      invoicesApi.refetch()
      onDebtChange()
    } else if (addLineMutation.error) onError(addLineMutation.error)
  }

  const removeLine = async (lineId: number) => {
    if (!selectedInvoice) return
    removeLineMutation.reset()
    const ok = await removeLineMutation.execute(() =>
      api
        .delete(`/invoices/${selectedInvoice.id}/lines/${lineId}`)
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      invoiceDetailApi.refetch()
      invoicesApi.refetch()
      onDebtChange()
    } else if (removeLineMutation.error) onError(removeLineMutation.error)
  }

  const openIssueInvoice = () => {
    setIssueDueDate(selectedInvoice?.due_date ?? getDefaultDueDate())
    setIssueDialogOpen(true)
  }

  const submitIssueInvoice = async () => {
    if (!selectedInvoice) return
    issueMutation.reset()
    const ok = await issueMutation.execute(() =>
      api
        .post(`/invoices/${selectedInvoice.id}/issue`, { due_date: issueDueDate || null })
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      setIssueDialogOpen(false)
      invoiceDetailApi.refetch()
      invoicesApi.refetch()
      onDebtChange()
    } else if (issueMutation.error) onError(issueMutation.error)
  }

  const cancelInvoice = async () => {
    if (!selectedInvoice) return
    cancelMutation.reset()
    const ok = await cancelMutation.execute(() =>
      api
        .post(`/invoices/${selectedInvoice.id}/cancel`)
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      invoiceDetailApi.refetch()
      invoicesApi.refetch()
      onDebtChange()
    } else if (cancelMutation.error) onError(cancelMutation.error)
  }

  const openDiscountDialog = (lineId: number) => {
    setDiscountLineId(lineId)
    setDiscountForm({ value_type: 'percentage', value: '', reason_text: '' })
    setDiscountDialogOpen(true)
  }

  const submitLineDiscount = async () => {
    if (!discountLineId) return
    discountMutation.reset()
    const ok = await discountMutation.execute(() =>
      api
        .post('/discounts/apply', {
          invoice_line_id: discountLineId,
          value_type: discountForm.value_type,
          value: Number(discountForm.value),
          reason_text: discountForm.reason_text.trim() || null,
        })
        .then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) {
      setDiscountDialogOpen(false)
      if (selectedInvoice) invoiceDetailApi.refetch()
      invoicesApi.refetch()
      onDebtChange()
    } else if (discountMutation.error) onError(discountMutation.error)
  }

  const downloadInvoicePdf = async () => {
    if (!selectedInvoice) return
    setDownloadingPdf(true)
    try {
      const response = await api.get(`/invoices/${selectedInvoice.id}/pdf`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoice_${selectedInvoice.invoice_number}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      onError('Failed to download invoice PDF.')
    } finally {
      setDownloadingPdf(false)
    }
  }

  const canDownloadInvoicePdf =
    selectedInvoice &&
    selectedInvoice.status !== 'draft' &&
    selectedInvoice.status !== 'cancelled' &&
    selectedInvoice.status !== 'void'

  return (
    <div>
      {termInvoiceMessage && (
        <Alert severity="success" className="mb-4">
          {termInvoiceMessage}
        </Alert>
      )}
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <div className="flex items-center gap-4 flex-wrap">
          <Typography variant="h6">Invoices</Typography>
          <Input
            label="Search invoice #"
            value={invoiceSearch}
            onChange={(e) => setInvoiceSearch(e.target.value)}
            className="w-48"
          />
          <Switch
            checked={showCancelledInvoices}
            onChange={(e) => setShowCancelledInvoices(e.target.checked)}
            label="Show cancelled"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {canInvoiceTerm(user) && (
            <Button
              variant="outlined"
              onClick={generateTermInvoices}
              disabled={!activeTermId || termInvoiceExists || termInvoiceLoading}
            >
              {termInvoiceLoading ? <Spinner size="small" /> : 'Invoice term'}
            </Button>
          )}
          <Button variant="contained" onClick={() => navigate(`/students/${studentId}/invoices/new`)}>
            Sell item
          </Button>
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Invoice #</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Total</TableHeaderCell>
              <TableHeaderCell>Due</TableHeaderCell>
              <TableHeaderCell>Issue date</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleInvoices.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell>{invoice.invoice_number}</TableCell>
                <TableCell>{invoice.status}</TableCell>
                <TableCell>{invoice.invoice_type}</TableCell>
                <TableCell>{formatMoney(parseNumber(invoice.total))}</TableCell>
                <TableCell>{formatMoney(parseNumber(invoice.amount_due))}</TableCell>
                <TableCell>{invoice.issue_date ? formatDate(invoice.issue_date) : '—'}</TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => openInvoiceDetail(invoice)}>
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {invoicesLoading && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Spinner size="small" />
                </td>
              </TableRow>
            )}
            {!invoicesLoading && !visibleInvoices.length && (
              <TableRow>
                <td colSpan={7} className="px-4 py-8 text-center">
                  <Typography color="secondary">No invoices yet</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Invoice Detail Dialog */}
      <Dialog open={Boolean(selectedInvoiceId)} onClose={closeInvoiceDetail} maxWidth="lg">
        <DialogCloseButton onClose={closeInvoiceDetail} />
        <DialogTitle>
          Invoice {selectedInvoice?.invoice_number ?? ''}
          {selectedInvoice ? ` · ${selectedInvoice.status}` : invoiceDetailApi.loading ? ' (loading…)' : ''}
        </DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            {selectedInvoice && (
              <div className="flex gap-2 flex-wrap">
                <Chip label={`Total ${formatMoney(parseNumber(selectedInvoice.total))}`} />
                <Chip label={`Due ${formatMoney(parseNumber(selectedInvoice.amount_due))}`} />
                <Chip label={`Paid ${formatMoney(parseNumber(selectedInvoice.paid_total))}`} />
                <Chip
                  label={`Issue ${selectedInvoice.issue_date ? formatDate(selectedInvoice.issue_date) : '—'}`}
                />
              </div>
            )}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Description</TableHeaderCell>
                    <TableHeaderCell>Qty</TableHeaderCell>
                    <TableHeaderCell>Unit</TableHeaderCell>
                    <TableHeaderCell>Total</TableHeaderCell>
                    <TableHeaderCell>Discount</TableHeaderCell>
                    <TableHeaderCell>Net</TableHeaderCell>
                    <TableHeaderCell align="right">Actions</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selectedInvoice?.lines.map((line: InvoiceLine) => (
                    <TableRow key={line.id}>
                      <TableCell>{line.description}</TableCell>
                      <TableCell>{line.quantity}</TableCell>
                      <TableCell>{formatMoney(parseNumber(line.unit_price))}</TableCell>
                      <TableCell>{formatMoney(parseNumber(line.line_total))}</TableCell>
                      <TableCell>{formatMoney(parseNumber(line.discount_amount))}</TableCell>
                      <TableCell>{formatMoney(parseNumber(line.net_amount))}</TableCell>
                      <TableCell align="right">
                        <div className="flex gap-2 justify-end">
                          {selectedInvoice.status === 'draft' && (
                            <Button
                              size="small"
                              variant="outlined"
                              color="error"
                              onClick={() => removeLine(line.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                          <Button size="small" variant="outlined" onClick={() => openDiscountDialog(line.id)}>
                            Discount
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!selectedInvoice?.lines.length && (
                    <TableRow>
                      <td colSpan={7} className="px-4 py-8 text-center">
                        <Typography color="secondary">No lines</Typography>
                      </td>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </DialogContent>
        <DialogActions>
          {canDownloadInvoicePdf && (
            <Button
              variant="outlined"
              onClick={downloadInvoicePdf}
              disabled={downloadingPdf}
            >
              <FileText className="h-4 w-4 mr-1" />
              {downloadingPdf ? 'Downloading…' : 'Download PDF'}
            </Button>
          )}
          {selectedInvoice?.status === 'draft' && (
            <Button variant="outlined" onClick={openAddLine}>
              Add line
            </Button>
          )}
          {selectedInvoice?.status === 'draft' && (
            <Button variant="contained" onClick={openIssueInvoice}>
              Issue
            </Button>
          )}
          {selectedInvoice && selectedInvoice.status !== 'paid' && (
            <Button variant="outlined" color="warning" onClick={cancelInvoice}>
              Cancel invoice
            </Button>
          )}
          <Button variant="outlined" onClick={closeInvoiceDetail}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Line Dialog */}
      <Dialog open={lineDialogOpen} onClose={() => setLineDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setLineDialogOpen(false)} />
        <DialogTitle>Add invoice line</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Select
              value={lineForm.kit_id}
              onChange={(e) => setLineForm({ ...lineForm, kit_id: e.target.value })}
              label="Kit"
            >
              <option value="">Select kit</option>
              {kits.map((kit) => (
                <option key={kit.id} value={String(kit.id)}>
                  {kit.name}
                </option>
              ))}
            </Select>
            <Input
              label="Quantity"
              type="number"
              value={lineForm.quantity}
              onChange={(e) => setLineForm({ ...lineForm, quantity: Number(e.target.value) })}
            />
            <Input
              label="Discount amount"
              type="number"
              value={lineForm.discount_amount}
              onChange={(e) => setLineForm({ ...lineForm, discount_amount: e.target.value })}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setLineDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitLine} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Add line'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Issue Dialog */}
      <Dialog open={issueDialogOpen} onClose={() => setIssueDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setIssueDialogOpen(false)} />
        <DialogTitle>Issue invoice</DialogTitle>
        <DialogContent>
          <div className="mt-4">
            <Input
              label="Due date"
              type="date"
              value={issueDueDate}
              onChange={(e) => setIssueDueDate(e.target.value)}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setIssueDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitIssueInvoice} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Issue'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Discount Dialog */}
      <Dialog
        open={discountDialogOpen}
        onClose={() => setDiscountDialogOpen(false)}
        maxWidth="sm"
      >
        <DialogCloseButton onClose={() => setDiscountDialogOpen(false)} />
        <DialogTitle>Apply discount</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            <Select
              value={discountForm.value_type}
              onChange={(e) =>
                setDiscountForm({ ...discountForm, value_type: e.target.value as DiscountValueType })
              }
              label="Value type"
            >
              <option value="percentage">Percentage</option>
              <option value="fixed">Fixed</option>
            </Select>
            <Input
              label="Value"
              type="number"
              value={discountForm.value}
              onChange={(e) => setDiscountForm({ ...discountForm, value: e.target.value })}
            />
            <Input
              label="Reason"
              value={discountForm.reason_text}
              onChange={(e) => setDiscountForm({ ...discountForm, reason_text: e.target.value })}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setDiscountDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitLineDiscount} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Apply'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
