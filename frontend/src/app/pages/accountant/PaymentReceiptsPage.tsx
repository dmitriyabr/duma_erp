import {
  Alert,
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PaginatedResponse } from '../../types/api'
import { useApi } from '../../hooks/useApi'
import { api } from '../../services/api'
import { downloadAttachment } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'
import { useAuth } from '../../auth/AuthContext'

interface PaymentRow {
  id: number
  payment_number: string
  receipt_number: string | null
  student_id: number
  amount: string
  payment_method: string
  payment_date: string
  status: string
  confirmation_attachment_id: number | null
}

export const PaymentReceiptsPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAccountant = user?.role === 'Accountant'
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const url = useMemo(() => {
    const params: Record<string, string | number> = { page: page + 1, limit }
    if (statusFilter !== 'all') params.status = statusFilter
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/payments?${sp.toString()}`
  }, [page, limit, statusFilter, dateFrom, dateTo])

  const { data, loading, error } = useApi<PaginatedResponse<PaymentRow>>(url)
  const payments = data?.items ?? []
  const total = data?.total ?? 0

  const downloadReceiptPdf = async (paymentId: number, receiptNumber: string) => {
    try {
      const res = await api.get(`/payments/${paymentId}/receipt/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `receipt_${receiptNumber || paymentId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // ignore
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Incoming Payments
        </Typography>
        {!isAccountant && (
          <Button variant="contained" onClick={() => navigate('/students')}>
            New payment (via student)
          </Button>
        )}
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="completed">Completed</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
            <MenuItem value="cancelled">Cancelled</MenuItem>
          </Select>
        </FormControl>
        <TextField
          label="Date from"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160 }}
        />
        <TextField
          label="Date to"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160 }}
        />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Date</TableCell>
            <TableCell>Receipt #</TableCell>
            <TableCell>Student ID</TableCell>
            <TableCell>Method</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="center">File</TableCell>
            <TableCell></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={8}>Loading…</TableCell>
            </TableRow>
          ) : (
            payments.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDate(row.payment_date)}</TableCell>
                <TableCell>{row.receipt_number || row.payment_number}</TableCell>
                <TableCell>{row.student_id}</TableCell>
                <TableCell>{row.payment_method}</TableCell>
                <TableCell align="right">{formatMoney(Number(row.amount))}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell align="center">
                  {row.status === 'completed' && (
                    <Tooltip title="Receipt PDF">
                      <IconButton
                        size="small"
                        onClick={() =>
                          downloadReceiptPdf(row.id, row.receipt_number || row.payment_number)
                        }
                      >
                        <PictureAsPdfIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                  {row.confirmation_attachment_id != null && (
                    <Tooltip title="Download attachment">
                      <IconButton
                        size="small"
                        onClick={() => downloadAttachment(row.confirmation_attachment_id!)}
                      >
                        <DownloadIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell>
                  <Button
                    size="small"
                    onClick={() => navigate(`/students/${row.student_id}`)}
                  >
                    View student
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={limit}
        onRowsPerPageChange={(e) => {
          setLimit(Number(e.target.value))
          setPage(0)
        }}
        rowsPerPageOptions={[25, 50, 100]}
      />
    </Box>
  )
}
