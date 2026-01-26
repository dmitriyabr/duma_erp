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
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

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
  const [employeeBalances, setEmployeeBalances] = useState<EmployeeBalanceRow[]>([])
  const [payouts, setPayouts] = useState<PayoutRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [payoutDialogOpen, setPayoutDialogOpen] = useState(false)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | ''>('')
  const [payoutDate, setPayoutDate] = useState(getDefaultPayoutDate())
  const [amount, setAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('mpesa')
  const [referenceNumber, setReferenceNumber] = useState('')
  const [proofText, setProofText] = useState('')

  const [employees, setEmployees] = useState<UserRow[]>([])

  const loadEmployees = useCallback(async () => {
    try {
      const response = await api.get<ApiResponse<{ items: UserRow[] }>>('/users', {
        params: { limit: 100 },
      })
      setEmployees(response.data.data.items)
    } catch {
      setError('Failed to load employees.')
    }
  }, [])

  const loadBalances = useCallback(async () => {
    try {
      // Загружаем всех сотрудников и для каждого получаем баланс
      const employeesResponse = await api.get<ApiResponse<{ items: UserRow[] }>>('/users', {
        params: { limit: 100 },
      })
      const allEmployees = employeesResponse.data.data.items

      const balancesPromises = allEmployees.map(async (emp) => {
        try {
          const balanceResponse = await api.get<ApiResponse<{ employee_id: number; total_approved: number; total_paid: number; balance: number }>>(
            `/compensations/payouts/employees/${emp.id}/balance`
          )
          const balanceData = balanceResponse.data.data
          return {
            ...balanceData,
            employee_id: emp.id,
            employee_name: emp.full_name,
          }
        } catch {
          return {
            employee_id: emp.id,
            employee_name: emp.full_name,
            total_approved: 0,
            total_paid: 0,
            balance: 0,
          }
        }
      })

      const balances = await Promise.all(balancesPromises)
      // Фильтруем только тех, у кого есть баланс > 0 или были выплаты
      const withBalance = balances.filter((b) => b.balance > 0 || b.total_paid > 0)
      setEmployeeBalances(withBalance)
    } catch {
      setError('Failed to load employee balances.')
    }
  }, [])

  const loadPayouts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<PayoutRow>>>(
        '/compensations/payouts',
        { params: { page: page + 1, limit } }
      )
      setPayouts(response.data.data.items)
      setTotal(response.data.data.total)
    } catch {
      setError('Failed to load payouts.')
    } finally {
      setLoading(false)
    }
  }, [page, limit])

  useEffect(() => {
    loadEmployees()
    loadBalances()
  }, [loadEmployees, loadBalances])

  useEffect(() => {
    loadPayouts()
  }, [loadPayouts])

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
    setPayoutDialogOpen(true)
  }

  const handleCreatePayout = async () => {
    if (!selectedEmployeeId || !amount || !payoutDate) {
      setError('Fill required fields: employee, amount, date.')
      return
    }
    const amountValue = Number(amount)
    if (amountValue <= 0) {
      setError('Amount must be greater than 0.')
      return
    }
    if (!proofText.trim()) {
      setError('Proof is required (proof text).')
      return
    }

    setLoading(true)
    setError(null)
    try {
      await api.post('/compensations/payouts', {
        employee_id: Number(selectedEmployeeId),
        payout_date: payoutDate,
        amount: amountValue,
        payment_method: paymentMethod,
        reference_number: referenceNumber.trim() || null,
        proof_text: proofText.trim(),
      })
      setPayoutDialogOpen(false)
      await loadBalances()
      await loadPayouts()
    } catch {
      setError('Failed to create payout.')
    } finally {
      setLoading(false)
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

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
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
            label="Proof text"
            value={proofText}
            onChange={(event) => setProofText(event.target.value)}
            multiline
            minRows={3}
            required
            helperText="Required: describe or paste proof of payment"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPayoutDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreatePayout} disabled={loading}>
            Create payout
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
