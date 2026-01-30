import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../auth/AuthContext'
import { useApi, useApiMutation } from '../../../hooks/useApi'
import { api } from '../../../services/api'
import { INVOICE_LIST_LIMIT } from '../../../constants/pagination'
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

interface InvoicesTabProps {
  studentId: number
  onError: (message: string) => void
  onDebtChange: () => void
}

export const InvoicesTab = ({ studentId, onError, onDebtChange }: InvoicesTabProps) => {
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
    '/invoices',
    {
      params: {
        student_id: studentId,
        limit: INVOICE_LIST_LIMIT,
        page: 1,
        ...(invoiceSearch.trim() && { search: invoiceSearch.trim() }),
      },
    },
    [studentId, invoiceSearch]
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

  const invoices = invoicesApi.data?.items ?? []
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

  const visibleInvoices = showCancelledInvoices
    ? invoices
    : invoices.filter((invoice) => {
        const status = invoice.status?.toLowerCase()
        return status !== 'cancelled' && status !== 'void'
      })

  const generateTermInvoices = async () => {
    if (!activeTermId) return
    generateTermMutation.reset()
    const ok = await generateTermMutation.execute(() =>
      api
        .post('/invoices/generate-term-invoices/student', {
          term_id: activeTermId,
          student_id: studentId,
        })
        .then((r) => ({ data: { data: (r.data as { data?: unknown })?.data ?? true } }))
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
        .then((r) => ({ data: { data: (r.data as { data: InvoiceDetail }).data } }))
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
        .then((r) => ({ data: { data: (r.data as { data?: unknown })?.data ?? true } }))
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
        .then((r) => ({ data: { data: (r.data as { data?: unknown })?.data ?? true } }))
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
        .then((r) => ({ data: { data: (r.data as { data?: unknown })?.data ?? true } }))
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
        .then((r) => ({ data: { data: (r.data as { data?: unknown })?.data ?? true } }))
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
    <Box>
      {termInvoiceMessage ? (
        <Box sx={{ mb: 2, p: 1, bgcolor: 'success.light', borderRadius: 1 }}>
          <Typography variant="body2">{termInvoiceMessage}</Typography>
        </Box>
      ) : null}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Typography variant="h6">Invoices</Typography>
          <TextField
            size="small"
            label="Search invoice #"
            value={invoiceSearch}
            onChange={(event) => setInvoiceSearch(event.target.value)}
          />
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={showCancelledInvoices}
                onChange={(event) => setShowCancelledInvoices(event.target.checked)}
              />
            }
            label="Show cancelled"
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {user?.role === 'SuperAdmin' ? (
            <Button
              variant="outlined"
              onClick={generateTermInvoices}
              disabled={!activeTermId || termInvoiceExists || termInvoiceLoading}
            >
              Invoice term
            </Button>
          ) : null}
          <Button variant="contained" onClick={() => navigate(`/students/${studentId}/invoices/new`)}>
            Sell item
          </Button>
        </Box>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Invoice #</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Total</TableCell>
            <TableCell>Due</TableCell>
            <TableCell>Issue date</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => openInvoiceDetail(invoice)}>
                  View
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!visibleInvoices.length ? (
            <TableRow>
              <TableCell colSpan={7} align="center">
                No invoices yet
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      {/* Invoice Detail Dialog */}
      <Dialog open={Boolean(selectedInvoiceId)} onClose={closeInvoiceDetail} fullWidth maxWidth="lg">
        <DialogTitle>
          Invoice {selectedInvoice?.invoice_number ?? ''}
          {selectedInvoice ? ` · ${selectedInvoice.status}` : invoiceDetailApi.loading ? ' (loading…)' : ''}
        </DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2 }}>
          {selectedInvoice ? (
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Chip label={`Total ${formatMoney(parseNumber(selectedInvoice.total))}`} />
              <Chip label={`Due ${formatMoney(parseNumber(selectedInvoice.amount_due))}`} />
              <Chip label={`Paid ${formatMoney(parseNumber(selectedInvoice.paid_total))}`} />
              <Chip
                label={`Issue ${selectedInvoice.issue_date ? formatDate(selectedInvoice.issue_date) : '—'}`}
              />
            </Box>
          ) : null}
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Description</TableCell>
                <TableCell>Qty</TableCell>
                <TableCell>Unit</TableCell>
                <TableCell>Total</TableCell>
                <TableCell>Discount</TableCell>
                <TableCell>Net</TableCell>
                <TableCell align="right">Actions</TableCell>
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
                    {selectedInvoice.status === 'draft' ? (
                      <Button size="small" onClick={() => removeLine(line.id)}>
                        Remove
                      </Button>
                    ) : null}
                    <Button size="small" onClick={() => openDiscountDialog(line.id)}>
                      Discount
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!selectedInvoice?.lines.length ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    No lines
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </DialogContent>
        <DialogActions>
          {canDownloadInvoicePdf ? (
            <Button
              startIcon={<PictureAsPdfIcon />}
              onClick={downloadInvoicePdf}
              disabled={downloadingPdf}
            >
              {downloadingPdf ? 'Downloading…' : 'Download PDF'}
            </Button>
          ) : null}
          {selectedInvoice?.status === 'draft' ? <Button onClick={openAddLine}>Add line</Button> : null}
          {selectedInvoice?.status === 'draft' ? <Button onClick={openIssueInvoice}>Issue</Button> : null}
          {selectedInvoice && selectedInvoice.status !== 'paid' ? (
            <Button color="warning" onClick={cancelInvoice}>
              Cancel invoice
            </Button>
          ) : null}
          <Button onClick={closeInvoiceDetail}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Add Line Dialog — API supports only kit_id for invoice lines */}
      <Dialog open={lineDialogOpen} onClose={() => setLineDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add invoice line</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Kit</InputLabel>
            <Select
              value={lineForm.kit_id}
              label="Kit"
              onChange={(event) => setLineForm({ ...lineForm, kit_id: event.target.value })}
            >
              {kits.map((kit) => (
                <MenuItem key={kit.id} value={String(kit.id)}>
                  {kit.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Quantity"
            type="number"
            value={lineForm.quantity}
            onChange={(event) => setLineForm({ ...lineForm, quantity: Number(event.target.value) })}
          />
          <TextField
            label="Discount amount"
            type="number"
            value={lineForm.discount_amount}
            onChange={(event) => setLineForm({ ...lineForm, discount_amount: event.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLineDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitLine} disabled={loading}>
            Add line
          </Button>
        </DialogActions>
      </Dialog>

      {/* Issue Dialog */}
      <Dialog open={issueDialogOpen} onClose={() => setIssueDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Issue invoice</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Due date"
            type="date"
            value={issueDueDate}
            onChange={(event) => setIssueDueDate(event.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIssueDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitIssueInvoice} disabled={loading}>
            Issue
          </Button>
        </DialogActions>
      </Dialog>

      {/* Discount Dialog */}
      <Dialog
        open={discountDialogOpen}
        onClose={() => setDiscountDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Apply discount</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Value type</InputLabel>
            <Select
              value={discountForm.value_type}
              label="Value type"
              onChange={(event) =>
                setDiscountForm({ ...discountForm, value_type: event.target.value as DiscountValueType })
              }
            >
              <MenuItem value="percentage">Percentage</MenuItem>
              <MenuItem value="fixed">Fixed</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Value"
            type="number"
            value={discountForm.value}
            onChange={(event) => setDiscountForm({ ...discountForm, value: event.target.value })}
          />
          <TextField
            label="Reason"
            value={discountForm.reason_text}
            onChange={(event) => setDiscountForm({ ...discountForm, reason_text: event.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDiscountDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitLineDiscount} disabled={loading}>
            Apply
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
