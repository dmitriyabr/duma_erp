import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { USERS_LIST_LIMIT } from '../../constants/pagination'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { formatMoney } from '../../utils/format'
import {
  Typography,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  Input,
  Textarea,
  Checkbox,
  Autocomplete,
  Spinner,
} from '../../components/ui'

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
  const { data: usersData } = useApi<{ items: UserRow[] }>('/users', {
    params: { limit: USERS_LIST_LIMIT },
  }, [])

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
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-4">
        {isEdit ? 'Edit payment' : 'New payment'}
      </Typography>

      {(error || createPurposeError || createPaymentError) && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error || createPurposeError || createPaymentError}
        </Alert>
      )}

      <div className="grid gap-4 max-w-[600px]">
        <Autocomplete<PORow>
          options={poOptions}
          getOptionLabel={(option) => `${option.po_number} - ${option.supplier_name} (${formatMoney(option.expected_total)})`}
          value={selectedPO}
          onChange={async (newValue) => {
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
          onInputChange={(newInputValue) => {
            if (newInputValue) {
              loadPOs(newInputValue)
            } else {
              // Если поле очищено, загружаем начальный список
              loadPOs()
            }
          }}
          loading={loadingPOs}
          label="Purchase Order (optional)"
          placeholder="Search by PO number or supplier name"
          isOptionEqualToValue={(option, value) => option.id === value.id}
        />
        <Select
          value={purposeId === '' ? '' : String(purposeId)}
          onChange={(event) => handlePurposeSelect(event.target.value)}
          label="Category / Purpose"
          required
        >
          <option value="">Select purpose</option>
          {purposes.map((purpose) => (
            <option key={purpose.id} value={purpose.id}>
              {purpose.name}
            </option>
          ))}
          <option value="create" className="italic text-primary">
            + Add new category
          </option>
        </Select>
        <Input
          label="Payee name (optional)"
          value={payeeName}
          onChange={(event) => setPayeeName(event.target.value)}
        />
        <Input
          label="Payment date"
          type="date"
          value={paymentDate}
          onChange={(event) => setPaymentDate(event.target.value)}
          required
        />
        <Input
          label="Amount"
          type="number"
          value={!amount || Number(amount) === 0 ? '' : amount}
          onChange={(event) => setAmount(event.target.value)}
          onFocus={(event) => event.currentTarget.select()}
          onWheel={(event) => (event.currentTarget as HTMLInputElement).blur()}
          min={0}
          step={0.01}
          required
        />
        <Select
          value={paymentMethod}
          onChange={(event) => setPaymentMethod(event.target.value)}
          label="Payment method"
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
          onChange={(event) => setReferenceNumber(event.target.value)}
        />
        <Textarea
          label="Reference / proof (text, optional if file uploaded)"
          value={proofText}
          onChange={(event) => setProofText(event.target.value)}
          rows={3}
          helperText="Reference or confirmation file below is required"
        />
        <div>
          <label className="inline-block">
            <input
              ref={proofFileInputRef}
              type="file"
              className="hidden"
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
            <Button
              variant="outlined"
              disabled={uploadingProof}
              onClick={() => proofFileInputRef.current?.click()}
            >
              {uploadingProof ? <Spinner size="small" /> : 'Upload confirmation (image/PDF)'}
            </Button>
          </label>
          {proofFileName && (
            <Typography variant="body2" color="secondary" className="ml-2 inline-block">
              {proofFileName}
            </Typography>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            checked={companyPaid}
            onChange={(event) => setCompanyPaid(event.target.checked)}
          />
          <span className="text-sm font-medium text-slate-700">Company paid</span>
        </div>
        {!companyPaid && (
          <Select
            value={employeePaidId === '' ? '' : String(employeePaidId)}
            onChange={(event) => setEmployeePaidId(event.target.value ? Number(event.target.value) : '')}
            label="Employee who paid"
          >
            <option value="">Select employee</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name}
              </option>
            ))}
          </Select>
        )}
      </div>

      <div className="flex gap-2 mt-6">
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSubmit} disabled={creatingPayment || isEdit}>
          {creatingPayment ? <Spinner size="small" /> : isEdit ? 'Save (not editable)' : 'Create payment'}
        </Button>
      </div>

      <Dialog
        open={newPurposeDialogOpen}
        onClose={() => setNewPurposeDialogOpen(false)}
        maxWidth="sm"
      >
        <DialogTitle>Create new category</DialogTitle>
        <DialogContent>
          <div className="grid gap-4 mt-2">
            <Input
              label="Category name"
              value={newPurposeName}
              onChange={(event) => setNewPurposeName(event.target.value)}
              required
              placeholder="e.g., Uniforms, Stationery, Furniture"
              helperText="Category for classifying purchases and payments"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewPurposeDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={createNewPurpose}
            disabled={creatingPurpose || !newPurposeName.trim()}
          >
            {creatingPurpose ? <Spinner size="small" /> : 'Create & select'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
