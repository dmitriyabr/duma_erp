import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material'
import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface PurposeRow {
  id: number
  name: string
}

interface UserRow {
  id: number
  full_name: string
}

interface PORow {
  id: number
  po_number: string
  supplier_name: string
  status: string
  expected_total: number
  purpose_id: number
}

const getDefaultPaymentDate = () => {
  return new Date().toISOString().slice(0, 10)
}

export const ProcurementPaymentFormPage = () => {
  const { paymentId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const isEdit = Boolean(paymentId)
  const resolvedId = paymentId ? Number(paymentId) : null

  const [poId, setPoId] = useState<number | ''>('')
  const [poOptions, setPoOptions] = useState<PORow[]>([])
  const [selectedPO, setSelectedPO] = useState<PORow | null>(null)
  const [purposeId, setPurposeId] = useState<number | ''>('')
  const [payeeName, setPayeeName] = useState('')
  const [paymentDate, setPaymentDate] = useState(getDefaultPaymentDate())
  const [amount, setAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('mpesa')
  const [referenceNumber, setReferenceNumber] = useState('')
  const [proofText, setProofText] = useState('')
  const [proofAttachmentId, setProofAttachmentId] = useState<number | null>(null)
  const [proofFileName, setProofFileName] = useState<string | null>(null)
  const [uploadingProof, setUploadingProof] = useState(false)
  const proofFileInputRef = React.useRef<HTMLInputElement>(null)
  const [companyPaid, setCompanyPaid] = useState(true)
  const [employeePaidId, setEmployeePaidId] = useState<number | ''>('')

  const [loadingPOs, setLoadingPOs] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newPurposeDialogOpen, setNewPurposeDialogOpen] = useState(false)
  const [newPurposeName, setNewPurposeName] = useState('')

  const { data: purposesData, refetch: refetchPurposes } = useApi<PurposeRow[]>(
    '/procurement/payment-purposes',
    { params: { include_inactive: true } }
  )
  const { data: usersData } = useApi<{ items: UserRow[] }>('/users', { params: { limit: 100 } })

  const purposes = purposesData || []
  const users = usersData?.items || []

  const { execute: createPurpose, loading: creatingPurpose, error: createPurposeError } =
    useApiMutation<PurposeRow>()
  const { execute: createPayment, loading: creatingPayment, error: createPaymentError } =
    useApiMutation<void>()

  const loadPOs = useCallback(async (search: string = '') => {
    setLoadingPOs(true)
    try {
      const params: Record<string, string | number> = {
        limit: 100,
        page: 1,
      }
      if (search.trim()) {
        params.supplier_name = search.trim()
      }
      const response = await api.get<ApiResponse<{ items: PORow[] }>>('/procurement/purchase-orders', {
        params,
      })
      // Фильтруем только активные закупки (не cancelled, не closed)
      const activePOs = response.data.data.items.filter(
        (po) => po.status !== 'cancelled' && po.status !== 'closed'
      )
      setPoOptions(activePOs)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        return
      }
      // Ignore other errors
    } finally {
      setLoadingPOs(false)
    }
  }, [])

  useEffect(() => {
    // Если передан po_id в query параметрах, загружаем его сначала
    const poIdParam = searchParams.get('po_id')
    if (poIdParam) {
      const poIdNum = Number(poIdParam)
      // Загружаем данные PO, чтобы получить purpose_id
      api
        .get<ApiResponse<PORow>>(`/procurement/purchase-orders/${poIdNum}`)
        .then((response) => {
          const po = response.data.data
          setPoId(po.id)
          setPurposeId(po.purpose_id)
          setSelectedPO(po)
          // Добавляем PO в список опций
          setPoOptions([po])
        })
        .catch((err) => {
          if (axios.isAxiosError(err) && err.response?.status === 401) {
            return
          }
          // Ignore other errors
        })
    } else {
      // Загружаем список PO только если нет выбранного PO
      loadPOs()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, loadPOs])

  const handlePurposeSelect = (value: number | string) => {
    if (value === 'create') {
      setNewPurposeName('')
      setNewPurposeDialogOpen(true)
      return
    }
    setPurposeId(Number(value))
  }

  const createNewPurpose = async () => {
    if (!newPurposeName.trim()) {
      setError('Enter purpose name.')
      return
    }

    setError(null)
    const newPurpose = await createPurpose(() =>
      api.post<ApiResponse<PurposeRow>>('/procurement/payment-purposes', {
        name: newPurposeName.trim(),
      })
    )

    if (newPurpose) {
      // Перезагружаем весь список, чтобы получить актуальные данные
      refetchPurposes()
      setPurposeId(newPurpose.id)
      setNewPurposeDialogOpen(false)
      setNewPurposeName('')
    }
  }

  const handleSubmit = async () => {
    if (!purposeId || !amount || !paymentDate) {
      setError('Fill required fields: purpose, amount, date.')
      return
    }
    const amountValue = Number(amount)
    if (amountValue <= 0) {
      setError('Amount must be greater than 0.')
      return
    }
    const hasProofText = Boolean(proofText.trim())
    const hasProofFile = proofAttachmentId != null
    if (!hasProofText && !hasProofFile) {
      setError('Reference / proof (text) or confirmation file is required.')
      return
    }

    if (isEdit && resolvedId) {
      // Payments are typically not editable after creation, but handle if needed
      setError('Payments cannot be edited after creation.')
      return
    }

    setError(null)
    const payload: Record<string, unknown> = {
      po_id: poId ? Number(poId) : null,
      purpose_id: Number(purposeId),
      payee_name: payeeName.trim() || null,
      payment_date: paymentDate,
      amount: amountValue,
      payment_method: paymentMethod,
      reference_number: referenceNumber.trim() || null,
      proof_text: proofText.trim() || null,
      proof_attachment_id: proofAttachmentId ?? null,
      company_paid: companyPaid,
      employee_paid_id: employeePaidId ? Number(employeePaidId) : null,
    }

    const result = await createPayment(() => api.post('/procurement/payments', payload))
    if (result !== null) {
      navigate('/procurement/payments')
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        {isEdit ? 'Edit payment' : 'New payment'}
      </Typography>

      {(error || createPurposeError || createPaymentError) ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || createPurposeError || createPaymentError}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gap: 2, maxWidth: 600 }}>
        <Autocomplete
          options={poOptions}
          getOptionLabel={(option) => `${option.po_number} - ${option.supplier_name} (${formatMoney(option.expected_total)})`}
          value={selectedPO}
          onChange={async (_, newValue) => {
            setSelectedPO(newValue)
            setPoId(newValue ? newValue.id : '')
            if (newValue) {
              // Загружаем полные данные PO, чтобы получить purpose_id
              try {
                const response = await api.get<ApiResponse<PORow>>(
                  `/procurement/purchase-orders/${newValue.id}`
                )
                setPurposeId(response.data.data.purpose_id)
                // Обновляем selectedPO с полными данными
                setSelectedPO(response.data.data)
              } catch (err) {
                if (axios.isAxiosError(err) && err.response?.status === 401) {
                  return
                }
                // Если не удалось загрузить, используем purpose_id из списка
                if (newValue.purpose_id) {
                  setPurposeId(newValue.purpose_id)
                }
              }
            } else {
              setPurposeId('')
            }
          }}
          onInputChange={(_, newInputValue) => {
            if (newInputValue) {
              loadPOs(newInputValue)
            } else {
              // Если поле очищено, загружаем начальный список
              loadPOs()
            }
          }}
          loading={loadingPOs}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Purchase Order (optional)"
              placeholder="Search by PO number or supplier name"
              InputLabelProps={{ shrink: true }}
            />
          )}
          isOptionEqualToValue={(option, value) => option.id === value.id}
        />
        <FormControl required>
          <InputLabel>Category / Purpose</InputLabel>
          <Select
            value={purposeId}
            label="Category / Purpose"
            onChange={(event) => handlePurposeSelect(event.target.value)}
          >
            {purposes.map((purpose) => (
              <MenuItem key={purpose.id} value={purpose.id}>
                {purpose.name}
              </MenuItem>
            ))}
            <MenuItem value="create" sx={{ fontStyle: 'italic', color: 'primary.main' }}>
              + Add new category
            </MenuItem>
          </Select>
        </FormControl>
        <TextField
          label="Payee name (optional)"
          value={payeeName}
          onChange={(event) => setPayeeName(event.target.value)}
        />
        <TextField
          label="Payment date"
          type="date"
          value={paymentDate}
          onChange={(event) => setPaymentDate(event.target.value)}
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
                } catch (err) {
                  if (axios.isAxiosError(err) && err.response?.status === 401) {
                    return
                  }
                  setError('Failed to upload confirmation file.')
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
        <FormControlLabel
          control={
            <Checkbox checked={companyPaid} onChange={(event) => setCompanyPaid(event.target.checked)} />
          }
          label="Company paid"
        />
        {!companyPaid ? (
          <FormControl>
            <InputLabel>Employee who paid</InputLabel>
            <Select
              value={employeePaidId}
              label="Employee who paid"
              onChange={(event) => setEmployeePaidId(Number(event.target.value))}
            >
              <MenuItem value="">Select employee</MenuItem>
              {users.map((user) => (
                <MenuItem key={user.id} value={user.id}>
                  {user.full_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : null}
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
        <Button onClick={() => navigate('/procurement/payments')}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={creatingPayment || isEdit}>
          {isEdit ? 'Save (not editable)' : 'Create payment'}
        </Button>
      </Box>

      <Dialog
        open={newPurposeDialogOpen}
        onClose={() => setNewPurposeDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Create new category</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Category name"
            value={newPurposeName}
            onChange={(event) => setNewPurposeName(event.target.value)}
            fullWidth
            required
            autoFocus
            placeholder="e.g., Uniforms, Stationery, Furniture"
            InputLabelProps={{ shrink: true }}
            helperText="Category for classifying purchases and payments"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewPurposeDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={createNewPurpose}
            disabled={creatingPurpose || !newPurposeName.trim()}
          >
            Create & select
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
