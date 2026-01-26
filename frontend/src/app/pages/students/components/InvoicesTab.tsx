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
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../auth/AuthContext'
import { api } from '../../../services/api'
import { formatDate, formatMoney } from '../../../utils/format'
import type {
  ApiResponse,
  DiscountValueType,
  InvoiceDetail,
  InvoiceLine,
  InvoiceSummary,
  ItemOption,
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
  const [loading, setLoading] = useState(false)
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([])
  const [invoiceSearch, setInvoiceSearch] = useState('')
  const [showCancelledInvoices, setShowCancelledInvoices] = useState(false)
  const [activeTermId, setActiveTermId] = useState<number | null>(null)
  const [termInvoiceExists, setTermInvoiceExists] = useState(false)
  const [termInvoiceLoading, setTermInvoiceLoading] = useState(false)
  const [termInvoiceMessage, setTermInvoiceMessage] = useState<string | null>(null)
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceDetail | null>(null)
  const [lineForm, setLineForm] = useState({
    line_type: 'item',
    item_id: '',
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
  const [items, setItems] = useState<ItemOption[]>([])
  const [kits, setKits] = useState<KitOption[]>([])

  const loadInvoices = useCallback(async () => {
    try {
      const params: Record<string, string | number> = { student_id: studentId, limit: 200, page: 1 }
      if (invoiceSearch.trim()) {
        params.search = invoiceSearch.trim()
      }
      const response = await api.get<ApiResponse<PaginatedResponse<InvoiceSummary>>>('/invoices', {
        params,
      })
      setInvoices(response.data.data.items)
    } catch {
      onError('Failed to load invoices.')
    }
  }, [studentId, invoiceSearch, onError])

  const loadActiveTerm = async () => {
    try {
      const response = await api.get<ApiResponse<{ id: number } | null>>('/terms/active')
      if (response.data.data?.id) {
        setActiveTermId(response.data.data.id)
      } else {
        setActiveTermId(null)
      }
    } catch {
      setActiveTermId(null)
    }
  }

  const refreshTermInvoiceState = useCallback(
    async (termId: number) => {
      try {
        const response = await api.get<ApiResponse<PaginatedResponse<InvoiceSummary>>>('/invoices', {
          params: { student_id: studentId, term_id: termId, limit: 200, page: 1 },
        })
        const hasTermInvoice = response.data.data.items.some((invoice) => {
          const status = invoice.status?.toLowerCase()
          if (status === 'cancelled' || status === 'void') {
            return false
          }
          return ['school_fee', 'transport'].includes(invoice.invoice_type)
        })
        setTermInvoiceExists(hasTermInvoice)
      } catch {
        setTermInvoiceExists(false)
      }
    },
    [studentId]
  )

  const loadItemsAndKits = async () => {
    try {
      const [itemsResponse, kitsResponse] = await Promise.all([
        api.get<ApiResponse<ItemOption[]>>('/items', { params: { include_inactive: true } }),
        api.get<ApiResponse<KitOption[]>>('/items/kits', { params: { include_inactive: true } }),
      ])
      setItems(itemsResponse.data.data)
      setKits(kitsResponse.data.data)
    } catch {
      onError('Failed to load catalog items.')
    }
  }

  useEffect(() => {
    loadInvoices()
    loadActiveTerm()
  }, [loadInvoices])

  useEffect(() => {
    if (activeTermId) {
      refreshTermInvoiceState(activeTermId)
    }
  }, [activeTermId, refreshTermInvoiceState])

  const visibleInvoices = showCancelledInvoices
    ? invoices
    : invoices.filter((invoice) => {
        const status = invoice.status?.toLowerCase()
        return status !== 'cancelled' && status !== 'void'
      })

  const generateTermInvoices = async () => {
    if (!activeTermId) return
    setTermInvoiceLoading(true)
    try {
      await api.post('/invoices/generate-term-invoices/student', {
        term_id: activeTermId,
        student_id: studentId,
      })
      setTermInvoiceMessage('Term invoices generated.')
      await loadInvoices()
      onDebtChange()
      await refreshTermInvoiceState(activeTermId)
    } catch {
      onError('Failed to generate term invoices.')
    } finally {
      setTermInvoiceLoading(false)
    }
  }

  const openInvoiceDetail = async (invoice: InvoiceSummary) => {
    try {
      const response = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${invoice.id}`)
      setSelectedInvoice(response.data.data)
    } catch {
      onError('Failed to load invoice.')
    }
  }

  const closeInvoiceDetail = () => {
    setSelectedInvoice(null)
    setLineDialogOpen(false)
  }

  const openAddLine = async () => {
    if (!selectedInvoice) return
    await loadItemsAndKits()
    setLineForm({ line_type: 'item', item_id: '', kit_id: '', quantity: 1, discount_amount: '' })
    setLineDialogOpen(true)
  }

  const submitLine = async () => {
    if (!selectedInvoice) return
    setLoading(true)
    try {
      if (lineForm.line_type === 'item' && !lineForm.item_id) {
        onError('Select an item to add to the invoice.')
        setLoading(false)
        return
      }
      if (lineForm.line_type === 'kit' && !lineForm.kit_id) {
        onError('Select a kit to add to the invoice.')
        setLoading(false)
        return
      }

      const payload: Record<string, number | null> = {
        item_id: null,
        kit_id: null,
        quantity: Number(lineForm.quantity),
        discount_amount: lineForm.discount_amount ? Number(lineForm.discount_amount) : 0,
      }
      if (lineForm.line_type === 'item') {
        payload.item_id = Number(lineForm.item_id)
      } else {
        payload.kit_id = Number(lineForm.kit_id)
      }

      const invoiceId = selectedInvoice.id
      await api.post(`/invoices/${invoiceId}/lines`, payload)
      const refreshed = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${invoiceId}`)
      setSelectedInvoice(refreshed.data.data)
      setLineDialogOpen(false)
      await loadInvoices()
      onDebtChange()
    } catch {
      onError('Failed to add invoice line.')
    } finally {
      setLoading(false)
    }
  }

  const removeLine = async (lineId: number) => {
    if (!selectedInvoice) return
    setLoading(true)
    try {
      await api.delete(`/invoices/${selectedInvoice.id}/lines/${lineId}`)
      const refreshed = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${selectedInvoice.id}`)
      setSelectedInvoice(refreshed.data.data)
      await loadInvoices()
      onDebtChange()
    } catch {
      onError('Failed to remove invoice line.')
    } finally {
      setLoading(false)
    }
  }

  const openIssueInvoice = () => {
    setIssueDueDate(selectedInvoice?.due_date ?? getDefaultDueDate())
    setIssueDialogOpen(true)
  }

  const submitIssueInvoice = async () => {
    if (!selectedInvoice) return
    setLoading(true)
    try {
      await api.post(`/invoices/${selectedInvoice.id}/issue`, {
        due_date: issueDueDate || null,
      })
      const refreshed = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${selectedInvoice.id}`)
      setSelectedInvoice(refreshed.data.data)
      setIssueDialogOpen(false)
      await loadInvoices()
      onDebtChange()
    } catch {
      onError('Failed to issue invoice.')
    } finally {
      setLoading(false)
    }
  }

  const cancelInvoice = async () => {
    if (!selectedInvoice) return
    setLoading(true)
    try {
      await api.post(`/invoices/${selectedInvoice.id}/cancel`)
      const refreshed = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${selectedInvoice.id}`)
      setSelectedInvoice(refreshed.data.data)
      await loadInvoices()
      onDebtChange()
    } catch {
      onError('Failed to cancel invoice.')
    } finally {
      setLoading(false)
    }
  }

  const openDiscountDialog = (lineId: number) => {
    setDiscountLineId(lineId)
    setDiscountForm({ value_type: 'percentage', value: '', reason_text: '' })
    setDiscountDialogOpen(true)
  }

  const submitLineDiscount = async () => {
    if (!discountLineId) return
    setLoading(true)
    try {
      await api.post('/discounts/apply', {
        invoice_line_id: discountLineId,
        value_type: discountForm.value_type,
        value: Number(discountForm.value),
        reason_text: discountForm.reason_text.trim() || null,
      })
      if (selectedInvoice) {
        const refreshed = await api.get<ApiResponse<InvoiceDetail>>(`/invoices/${selectedInvoice.id}`)
        setSelectedInvoice(refreshed.data.data)
      }
      await loadInvoices()
      onDebtChange()
      setDiscountDialogOpen(false)
    } catch {
      onError('Failed to apply discount.')
    } finally {
      setLoading(false)
    }
  }

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
      <Dialog open={Boolean(selectedInvoice)} onClose={closeInvoiceDetail} fullWidth maxWidth="lg">
        <DialogTitle>
          Invoice {selectedInvoice?.invoice_number ?? ''}
          {selectedInvoice ? ` · ${selectedInvoice.status}` : ''}
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

      {/* Add Line Dialog */}
      <Dialog open={lineDialogOpen} onClose={() => setLineDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add invoice line</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl>
            <InputLabel>Line type</InputLabel>
            <Select
              value={lineForm.line_type}
              label="Line type"
              onChange={(event) => setLineForm({ ...lineForm, line_type: event.target.value })}
            >
              <MenuItem value="item">Item</MenuItem>
              <MenuItem value="kit">Kit</MenuItem>
            </Select>
          </FormControl>
          {lineForm.line_type === 'item' ? (
            <FormControl>
              <InputLabel>Item</InputLabel>
              <Select
                value={lineForm.item_id}
                label="Item"
                onChange={(event) => setLineForm({ ...lineForm, item_id: event.target.value })}
              >
                {items.map((item) => (
                  <MenuItem key={item.id} value={String(item.id)}>
                    {item.name} ({item.sku_code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          ) : (
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
          )}
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
