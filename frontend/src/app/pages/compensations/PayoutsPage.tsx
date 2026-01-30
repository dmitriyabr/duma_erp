import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
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
  Typography,
} from '@mui/material'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import { api } from '../../services/api'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'

interface EmployeeBalanceRow {
  employee_id: number
  employee_name: string
  total_approved: number
  total_paid: number
  balance: number
}

interface PayoutRow {
  id: number
  payout_number: string
  employee_id: number
  payout_date: string
  amount: number
  payment_method: string
}

interface UserRow {
  id: number
  full_name: string
}

const getDefaultPayoutDate = () => {
  return new Date().toISOString().slice(0, 10)
}

export const PayoutsPage = () => {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [employeeBalances, setEmployeeBalances] = useState<EmployeeBalanceRow[]>([])
  const [validationError, setValidationError] = useState<string | null>(null)

  const payoutsUrl = useMemo(() => `/compensations/payouts?page=${page + 1}&limit=${limit}`, [page, limit])
  const { data: payoutsData, loading, error, refetch } = useApi<PaginatedResponse<PayoutRow>>(payoutsUrl)
  const { data: employeesData } = useApi<{ items: UserRow[] }>('/users', {
    params: { limit: USERS_LIST_LIMIT },
  }, [])
  const { execute: createPayout, loading: _creating, error: createError } = useApiMutation()

  const payouts = payoutsData?.items || []
  const total = payoutsData?.total || 0
  const employees = employeesData?.items || []

  const [payoutDialogOpen, setPayoutDialogOpen] = useState(false)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | ''>('')
  const [payoutDate, setPayoutDate] = useState(getDefaultPayoutDate())
  const [amount, setAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('mpesa')
  const [referenceNumber, setReferenceNumber] = useState('')
  const [proofText, setProofText] = useState('')
  const [proofAttachmentId, setProofAttachmentId] = useState<number | null>(null)
  const [proofFileName, setProofFileName] = useState<string | null>(null)
  const [uploadingProof, setUploadingProof] = useState(false)
  const proofFileInputRef = React.useRef<HTMLInputElement>(null)

  const loadBalances = useCallback(async () => {
    if (!employees.length) return
    try {
      const ids = employees.map((e) => e.id)
      const response = await api.post<ApiResponse<{ balances: Array<{ employee_id: number; total_approved: number; total_paid: number; balance: number }> }>>(
        '/compensations/payouts/employee-balances-batch',
        { employee_ids: ids }
      )
      const balancesList = response.data.data?.balances ?? []
      const byId = Object.fromEntries(employees.map((e) => [e.id, e.full_name]))
      const withNames = balancesList.map((b) => ({
        ...b,
        employee_name: byId[b.employee_id] ?? '',
      }))
      const withBalance = withNames.filter((b) => b.balance > 0 || b.total_paid > 0)
      setEmployeeBalances(withBalance)
    } catch {
      // Ignore
    }
  }, [employees])

  useEffect(() => {
    loadBalances()
  }, [loadBalances])

  const openPayoutDialog = (employeeId: number) => {
    setSelectedEmployeeId(employeeId)
    const balance = employeeBalances.find((b) => b.employee_id === employeeId)
    if (balance) {
      setAmount(balance.balance > 0 ? String(balance.balance) : '')
    } else {
      setAmount('')
    }
    setPayoutDate(getDefaultPayoutDate())
    setPaymentMethod('mpesa')
    setReferenceNumber('')
    setProofText('')
    setProofAttachmentId(null)
    setProofFileName(null)
    if (proofFileInputRef.current) proofFileInputRef.current.value = ''
    setPayoutDialogOpen(true)
  }

  const handleCreatePayout = async () => {
    if (!selectedEmployeeId || !amount || !payoutDate) {
      setValidationError('Fill required fields: employee, amount, date.')
      return
    }
    const amountValue = Number(amount)
    if (amountValue <= 0) {
      setValidationError('Amount must be greater than 0.')
      return
    }
    const hasProofText = Boolean(proofText.trim())
    const hasProofFile = proofAttachmentId != null
    if (!hasProofText && !hasProofFile) {
      setValidationError('Reference / proof (text) or confirmation file is required.')
      return
    }

    setValidationError(null)
    const result = await createPayout(() =>
      api.post('/compensations/payouts', {
        employee_id: Number(selectedEmployeeId),
        payout_date: payoutDate,
        amount: amountValue,
        payment_method: paymentMethod,
        reference_number: referenceNumber.trim() || null,
        proof_text: proofText.trim() || null,
        proof_attachment_id: proofAttachmentId ?? null,
      })
    )

    if (result) {
      setPayoutDialogOpen(false)
      refetch()
      await loadBalances()
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Payouts
      </Typography>

      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Employee Balances
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Employee</TableCell>
              <TableCell align="right">Total Approved</TableCell>
              <TableCell align="right">Total Paid</TableCell>
              <TableCell align="right">Balance</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {employeeBalances.map((balance) => (
              <TableRow key={balance.employee_id}>
                <TableCell>{balance.employee_name}</TableCell>
                <TableCell align="right">{formatMoney(balance.total_approved)}</TableCell>
                <TableCell align="right">{formatMoney(balance.total_paid)}</TableCell>
                <TableCell align="right">
                  <Typography color={balance.balance > 0 ? 'error' : 'inherit'}>
                    {formatMoney(balance.balance)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  {balance.balance > 0 ? (
                    <Button size="small" variant="contained" onClick={() => openPayoutDialog(balance.employee_id)}>
                      Pay
                    </Button>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      —
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!employeeBalances.length ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  No employee balances found
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Box>

      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Recent Payouts
        </Typography>
      </Box>

      {error || createError || validationError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || createError || validationError}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Payout Number</TableCell>
            <TableCell>Employee</TableCell>
            <TableCell>Date</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell>Method</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {payouts.map((payout) => (
            <TableRow key={payout.id}>
              <TableCell>{payout.payout_number}</TableCell>
              <TableCell>
                {employees.find((e) => e.id === payout.employee_id)?.full_name ?? '—'}
              </TableCell>
              <TableCell>{formatDate(payout.payout_date)}</TableCell>
              <TableCell align="right">{formatMoney(payout.amount)}</TableCell>
              <TableCell>{payout.payment_method}</TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => navigate(`/compensations/payouts/${payout.id}`)}>
                  View
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {loading ? (
            <TableRow>
              <TableCell colSpan={6} align="center">
                Loading…
              </TableCell>
            </TableRow>
          ) : null}
          {!payouts.length && !loading ? (
            <TableRow>
              <TableCell colSpan={6} align="center">
                No payouts found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
      />

      <Dialog open={payoutDialogOpen} onClose={() => setPayoutDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Create payout</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <FormControl required>
            <InputLabel>Employee</InputLabel>
            <Select
              value={selectedEmployeeId}
              label="Employee"
              onChange={(event) => setSelectedEmployeeId(Number(event.target.value))}
            >
              {employees.map((emp) => (
                <MenuItem key={emp.id} value={emp.id}>
                  {emp.full_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Payout date"
            type="date"
            value={payoutDate}
            onChange={(event) => setPayoutDate(event.target.value)}
            InputLabelProps={{ shrink: true }}
            required
          />
          <TextField
            label="Amount"
            type="number"
            value={!amount || Number(amount) === 0 ? '' : amount}
            onChange={(event) => setAmount(event.target.value)}
            onFocus={(event) => event.currentTarget.select()}
            onWheel={(event) => event.currentTarget.blur()}
            inputProps={{ min: 0, step: 0.01 }}
            required
          />
          <FormControl required>
            <InputLabel>Payment method</InputLabel>
            <Select
              value={paymentMethod}
              label="Payment method"
              onChange={(event) => setPaymentMethod(event.target.value)}
            >
              <MenuItem value="mpesa">M-Pesa</MenuItem>
              <MenuItem value="bank">Bank Transfer</MenuItem>
              <MenuItem value="cash">Cash</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Reference number"
            value={referenceNumber}
            onChange={(event) => setReferenceNumber(event.target.value)}
          />
          <TextField
            label="Reference / proof (text, optional if file uploaded)"
            value={proofText}
            onChange={(event) => setProofText(event.target.value)}
            multiline
            minRows={2}
            helperText="Reference or confirmation file below is required"
          />
          <Box>
            <Button
              variant="outlined"
              component="label"
              disabled={uploadingProof}
              sx={{ mr: 1 }}
            >
              {uploadingProof ? 'Uploading…' : 'Upload confirmation (image/PDF)'}
              <input
                ref={proofFileInputRef}
                type="file"
                hidden
                accept="image/*,.pdf,application/pdf"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (!file) return
                  setUploadingProof(true)
                  try {
                    const formData = new FormData()
                    formData.append('file', file)
                    const res = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
                      headers: { 'Content-Type': 'multipart/form-data' },
                    })
                    setProofAttachmentId(res.data.data.id)
                    setProofFileName(file.name)
                  } catch {
                    setValidationError('Failed to upload confirmation file.')
                  } finally {
                    setUploadingProof(false)
                  }
                }}
              />
            </Button>
            {proofFileName && (
              <Typography variant="body2" color="text.secondary" component="span">
                {proofFileName}
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPayoutDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreatePayout}
            disabled={
              loading ||
              (!proofText.trim() && proofAttachmentId == null)
            }
          >
            Create payout
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
