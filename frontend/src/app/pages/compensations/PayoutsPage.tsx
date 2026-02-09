import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import { api } from '../../services/api'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatDate, formatMoney } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { FileDropzone } from '../../components/ui/FileDropzone'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

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
  const { user } = useAuth()
  const canCreatePayout = user?.role === 'SuperAdmin'
  const readOnly = !canCreatePayout
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [employeeBalances, setEmployeeBalances] = useState<EmployeeBalanceRow[]>([])
  const [validationError, setValidationError] = useState<string | null>(null)

  const payoutsUrl = useMemo(() => `/compensations/payouts?page=${page + 1}&limit=${limit}`, [page, limit])
  const { data: payoutsData, loading, error, refetch } = useApi<PaginatedResponse<PayoutRow>>(payoutsUrl)
  const { data: employeesData } = useApi<{ items: UserRow[] }>('/users', {
    params: { limit: USERS_LIST_LIMIT },
  }, [])
  const { execute: createPayout, loading: creating, error: createError } = useApiMutation()

  const payouts = payoutsData?.items || []
  const total = payoutsData?.total || 0
  const employees = useMemo(() => employeesData?.items || [], [employeesData])

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

  const uploadProofFile = useCallback(async (file: File) => {
    setUploadingProof(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setProofAttachmentId(res.data.data.id)
      setProofFileName(file.name)
      setValidationError(null)
    } catch {
      setProofAttachmentId(null)
      setProofFileName(null)
      setValidationError('Failed to upload confirmation file.')
    } finally {
      setUploadingProof(false)
    }
  }, [])

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
    if (readOnly) return
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
    setUploadingProof(false)
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
    <div>
      <Typography variant="h4" className="mb-4">
        Payouts
      </Typography>

      <div className="mb-6">
        <Typography variant="h6" className="mb-4">
          Employee Balances
        </Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Employee</TableHeaderCell>
                <TableHeaderCell align="right">Total Approved</TableHeaderCell>
                <TableHeaderCell align="right">Total Paid</TableHeaderCell>
                <TableHeaderCell align="right">Balance</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {employeeBalances.map((balance) => (
                <TableRow key={balance.employee_id}>
                  <TableCell>{balance.employee_name}</TableCell>
                  <TableCell align="right">{formatMoney(balance.total_approved)}</TableCell>
                  <TableCell align="right">{formatMoney(balance.total_paid)}</TableCell>
                  <TableCell align="right">
                    <Typography className={balance.balance > 0 ? 'text-error' : ''}>
                      {formatMoney(balance.balance)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {!readOnly && balance.balance > 0 ? (
                      <Button size="small" variant="outlined" onClick={() => openPayoutDialog(balance.employee_id)}>
                        Pay
                      </Button>
                    ) : (
                      <Typography variant="body2" color="secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {!employeeBalances.length && (
                <TableRow>
                  <td colSpan={5} className="px-4 py-8 text-center">
                    <Typography color="secondary">No employee balances found</Typography>
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="mb-4">
        <Typography variant="h6" className="mb-4">
          Recent Payouts
        </Typography>
      </div>

      {(error || createError || validationError) && (
        <Alert severity="error" className="mb-4">
          {error || createError || validationError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Payout Number</TableHeaderCell>
              <TableHeaderCell>Employee</TableHeaderCell>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell>Method</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
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
                  <Button size="small" variant="outlined" onClick={() => navigate(`/compensations/payouts/${payout.id}`)}>
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!payouts.length && !loading && (
              <TableRow>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <Typography color="secondary">No payouts found</Typography>
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
        />
      </div>

      <Dialog open={payoutDialogOpen} onClose={() => setPayoutDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setPayoutDialogOpen(false)} />
        <DialogTitle>Create payout</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Select
              label="Employee"
              value={selectedEmployeeId ? String(selectedEmployeeId) : ''}
              onChange={(e) => setSelectedEmployeeId(Number(e.target.value))}
              required
            >
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.full_name}
                </option>
              ))}
            </Select>
            <Input
              label="Payout date"
              type="date"
              value={payoutDate}
              onChange={(e) => setPayoutDate(e.target.value)}
              required
            />
            <Input
              label="Amount"
              type="number"
              value={!amount || Number(amount) === 0 ? '' : amount}
              onChange={(e) => setAmount(e.target.value)}
              onFocus={(e) => e.currentTarget.select()}
              onWheel={(e) => e.currentTarget.blur()}
              min={0}
              step={0.01}
              required
            />
            <Select
              label="Payment method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              required
            >
              <option value="mpesa">M-Pesa</option>
              <option value="bank">Bank Transfer</option>
              <option value="cash">Cash</option>
              <option value="other">Other</option>
            </Select>
            <Input
              label="Reference number"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
            />
            <Textarea
              label="Reference / proof (text, optional if file uploaded)"
              value={proofText}
              onChange={(e) => setProofText(e.target.value)}
              rows={3}
              helperText="Reference or confirmation file below is required"
            />
            <FileDropzone
              title="Upload confirmation (image/PDF)"
              description="Drag & drop here, or click to choose. Upload starts immediately."
              fileName={proofFileName}
              disabled={uploadingProof}
              loading={uploadingProof}
              accept="image/*,.pdf,application/pdf"
              onFileSelected={uploadProofFile}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setPayoutDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreatePayout}
            disabled={
              loading ||
              creating ||
              (!proofText.trim() && proofAttachmentId == null)
            }
          >
            Create payout
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
