import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { unwrapResponse } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import type { PaginatedResponse } from '../../types/api'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Card, CardContent } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'

interface PurposeRow {
  id: number
  name: string
  is_active: boolean
  purpose_type: 'expense' | 'fee'
}

interface ExpenseClaimResponse {
  id: number
  claim_number: string
}

interface UserRow {
  id: number
  full_name: string
  is_active: boolean
}

const today = () => new Date().toISOString().slice(0, 10)

export const NewExpenseClaimPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()

  const readOnly = user?.role === 'Accountant'
  const canChooseEmployee = user?.role === 'SuperAdmin' || user?.role === 'Admin'

  const [employeeId, setEmployeeId] = useState<number | ''>('')
  const [purposeId, setPurposeId] = useState<number | ''>('')
  const [expenseDate, setExpenseDate] = useState(today())
  const [amount, setAmount] = useState('')
  const [payeeName, setPayeeName] = useState('')
  const [description, setDescription] = useState('')
  const [proofText, setProofText] = useState('')
  const [proofAttachmentId, setProofAttachmentId] = useState<number | null>(null)
  const [proofFileName, setProofFileName] = useState<string | null>(null)
  const [uploadingProof, setUploadingProof] = useState(false)
  const proofFileInputRef = useRef<HTMLInputElement>(null)

  const [feeAmount, setFeeAmount] = useState('')
  const [feeProofText, setFeeProofText] = useState('')
  const [feeProofAttachmentId, setFeeProofAttachmentId] = useState<number | null>(null)
  const [feeProofFileName, setFeeProofFileName] = useState<string | null>(null)
  const [uploadingFeeProof, setUploadingFeeProof] = useState(false)
  const feeProofFileInputRef = useRef<HTMLInputElement>(null)

  const [error, setError] = useState<string | null>(null)

  const { data: purposesData, loading: purposesLoading, error: purposesError } = useApi<PurposeRow[]>(
    '/procurement/payment-purposes',
    { params: { include_inactive: false, purpose_type: 'expense' } },
    []
  )
  const purposes = useMemo(() => purposesData ?? [], [purposesData])

  const { data: employeesData, loading: employeesLoading, error: employeesError } = useApi<PaginatedResponse<UserRow>>(
    canChooseEmployee ? '/users' : null,
    canChooseEmployee ? { params: { page: 1, limit: 500, is_active: true } } : undefined,
    [canChooseEmployee]
  )
  const employees = useMemo(() => employeesData?.items ?? [], [employeesData])

  useEffect(() => {
    if (!canChooseEmployee) return
    if (employeeId !== '') return
    if (!user?.id) return
    setEmployeeId(user.id)
  }, [canChooseEmployee, employeeId, user?.id])

  const { execute: createClaim, loading: creating, error: createError } = useApiMutation<ExpenseClaimResponse>()

  const uploadProofFile = useCallback(async (file: File) => {
    const isPdf = file.type === 'application/pdf'
    const isImage = file.type.startsWith('image/')
    if (!isPdf && !isImage) {
      setError('Only images or PDF files are supported.')
      return
    }

    setUploadingProof(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setProofAttachmentId(res.data.data.id)
      setProofFileName(file.name)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) return
      setError('Failed to upload receipt file.')
      setProofAttachmentId(null)
      setProofFileName(null)
    } finally {
      setUploadingProof(false)
    }
  }, [])

  const uploadFeeProofFile = useCallback(async (file: File) => {
    const isPdf = file.type === 'application/pdf'
    const isImage = file.type.startsWith('image/')
    if (!isPdf && !isImage) {
      setError('Only images or PDF files are supported.')
      return
    }

    setUploadingFeeProof(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setFeeProofAttachmentId(res.data.data.id)
      setFeeProofFileName(file.name)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) return
      setError('Failed to upload fee proof file.')
      setFeeProofAttachmentId(null)
      setFeeProofFileName(null)
    } finally {
      setUploadingFeeProof(false)
    }
  }, [])

  const submit = async () => {
    if (readOnly) return
    if (!purposeId) {
      setError('Select category (purpose).')
      return
    }
    const amountValue = Number(amount)
    if (!amountValue || amountValue <= 0) {
      setError('Amount must be greater than 0.')
      return
    }
    if (!expenseDate) {
      setError('Select expense date.')
      return
    }
    if (!description.trim()) {
      setError('Description is required.')
      return
    }
    const hasProofText = Boolean(proofText.trim())
    const hasProofFile = proofAttachmentId != null
    if (!hasProofText && !hasProofFile) {
      setError('Proof (text) or receipt file is required.')
      return
    }

    const feeAmountValue = feeAmount.trim() ? Number(feeAmount) : 0
    if (Number.isNaN(feeAmountValue) || feeAmountValue < 0) {
      setError('Transaction fee must be 0 or greater.')
      return
    }
    if (feeAmountValue > 0) {
      const hasFeeProofText = Boolean(feeProofText.trim())
      const hasFeeProofFile = feeProofAttachmentId != null
      if (!hasFeeProofText && !hasFeeProofFile) {
        setError('Fee proof (text) or file is required when fee is provided.')
        return
      }
    }

    setError(null)
    const created = await createClaim(async () => {
      const res = await api.post('/compensations/claims', {
        employee_id: canChooseEmployee && employeeId ? Number(employeeId) : undefined,
        purpose_id: Number(purposeId),
        amount: amountValue,
        payee_name: payeeName.trim() || null,
        description: description.trim(),
        expense_date: expenseDate,
        proof_text: proofText.trim() || null,
        proof_attachment_id: proofAttachmentId,
        fee_amount: feeAmountValue > 0 ? feeAmountValue : 0,
        fee_proof_text: feeProofText.trim() || null,
        fee_proof_attachment_id: feeProofAttachmentId,
        submit: true,
      })
      return { data: { data: unwrapResponse<ExpenseClaimResponse>(res) } }
    })

    if (created) {
      navigate(`/compensations/claims/${created.id}`)
    } else if (createError) {
      setError(createError)
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <Typography variant="h4">New expense claim</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            Out-of-pocket purchase reimbursement (no PO/GRN required)
          </Typography>
        </div>
        <Button variant="outlined" onClick={() => navigate(-1)}>
          Back
        </Button>
      </div>

      {(error || purposesError || employeesError || createError) && (
        <Alert severity="error" className="mb-4">
          {error || purposesError || employeesError || createError}
        </Alert>
      )}

      <Card>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {canChooseEmployee && (
              <div>
                <Select
                  label="Employee"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value === '' ? '' : Number(e.target.value))}
                  disabled={readOnly || employeesLoading}
                >
                  <option value="">Me (default)</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.full_name}
                    </option>
                  ))}
                </Select>
                {employeesLoading && (
                  <Typography variant="caption" color="secondary" className="mt-1">
                    Loading employees...
                  </Typography>
                )}
              </div>
            )}

            <div>
              <Select
                label="Category (purpose)"
                value={purposeId}
                onChange={(e) => setPurposeId(e.target.value === '' ? '' : Number(e.target.value))}
                disabled={readOnly || purposesLoading}
                required
              >
                <option value="">Select category</option>
                {purposes.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
              {purposesLoading && (
                <Typography variant="caption" color="secondary" className="mt-1">
                  Loading categories...
                </Typography>
              )}
            </div>

            <Input
              label="Expense date"
              type="date"
              value={expenseDate}
              onChange={(e) => setExpenseDate(e.target.value)}
              disabled={readOnly}
              required
            />

            <Input
              label="Amount"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={readOnly}
              placeholder="0.00"
              required
            />

            <Input
              label="Payee / vendor (optional)"
              value={payeeName}
              onChange={(e) => setPayeeName(e.target.value)}
              disabled={readOnly}
              placeholder="Shell / Uber / Local shop"
            />
          </div>

          <div className="mt-4">
            <Textarea
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              disabled={readOnly}
              placeholder="What was purchased and why"
              required
            />
          </div>

          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Textarea
              label="Proof (text)"
              value={proofText}
              onChange={(e) => setProofText(e.target.value)}
              rows={3}
              disabled={readOnly}
              placeholder="Receipt number / transaction reference"
              required={proofAttachmentId == null}
            />

            <div>
              <Typography variant="subtitle2" color="secondary" className="mb-1">
                Proof (file)
              </Typography>
              <div className="flex items-center gap-3 flex-wrap">
                <input
                  ref={proofFileInputRef}
                  type="file"
                  className="hidden"
                  disabled={readOnly || uploadingProof}
                  accept="image/*,application/pdf"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) uploadProofFile(file)
                    e.target.value = ''
                  }}
                />
                <Button
                  type="button"
                  variant="outlined"
                  disabled={readOnly || uploadingProof}
                  onClick={() => proofFileInputRef.current?.click()}
                >
                  {uploadingProof ? 'Uploading...' : 'Upload receipt'}
                </Button>

                {uploadingProof && <Spinner size="small" />}
                {proofAttachmentId != null && (
                  <Typography variant="body2" className="truncate max-w-[320px]">
                    {proofFileName ?? `Attachment #${proofAttachmentId}`}
                  </Typography>
                )}
                {proofAttachmentId != null && !readOnly && (
                  <Button
                    type="button"
                    variant="text"
                    color="secondary"
                    onClick={() => {
                      setProofAttachmentId(null)
                      setProofFileName(null)
                    }}
                  >
                    Remove
                  </Button>
                )}
              </div>
              <Typography variant="caption" color="secondary" className="mt-2">
                Upload image/PDF receipt (max 10MB). You can also provide proof text instead.
              </Typography>
            </div>
          </div>

          <div className="mt-6">
            <Typography variant="subtitle1" className="mb-2">
              Transaction fee (optional)
            </Typography>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Fee amount"
                type="number"
                value={feeAmount}
                onChange={(e) => setFeeAmount(e.target.value)}
                disabled={readOnly}
                placeholder="0.00"
                min={0}
              />

              <div className="hidden md:block" />

              <Textarea
                label="Fee proof (text)"
                value={feeProofText}
                onChange={(e) => setFeeProofText(e.target.value)}
                rows={3}
                disabled={readOnly}
                placeholder="M-Pesa fee SMS / reference"
                required={feeAmount.trim() !== '' && Number(feeAmount) > 0 && feeProofAttachmentId == null}
              />

              <div>
                <Typography variant="subtitle2" color="secondary" className="mb-1">
                  Fee proof (file)
                </Typography>
                <div className="flex items-center gap-3 flex-wrap">
                  <input
                    ref={feeProofFileInputRef}
                    type="file"
                    className="hidden"
                    disabled={readOnly || uploadingFeeProof}
                    accept="image/*,application/pdf"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) uploadFeeProofFile(file)
                      e.target.value = ''
                    }}
                  />
                  <Button
                    type="button"
                    variant="outlined"
                    disabled={readOnly || uploadingFeeProof}
                    onClick={() => feeProofFileInputRef.current?.click()}
                  >
                    {uploadingFeeProof ? 'Uploading...' : 'Upload fee proof'}
                  </Button>

                  {uploadingFeeProof && <Spinner size="small" />}
                  {feeProofAttachmentId != null && (
                    <Typography variant="body2" className="truncate max-w-[320px]">
                      {feeProofFileName ?? `Attachment #${feeProofAttachmentId}`}
                    </Typography>
                  )}
                  {feeProofAttachmentId != null && !readOnly && (
                    <Button
                      type="button"
                      variant="text"
                      color="secondary"
                      onClick={() => {
                        setFeeProofAttachmentId(null)
                        setFeeProofFileName(null)
                      }}
                    >
                      Remove
                    </Button>
                  )}
                </div>
                <Typography variant="caption" color="secondary" className="mt-2">
                  Upload image/PDF proof (max 10MB). You can also provide proof text instead.
                </Typography>
              </div>
            </div>
          </div>

          {!readOnly && (
            <div className="mt-6 flex justify-end">
              <Button onClick={submit} disabled={creating || uploadingProof || uploadingFeeProof}>
                {creating ? <Spinner size="small" /> : 'Submit claim'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {readOnly && (
        <Alert severity="info" className="mt-4">
          Accountant role is read-only and cannot create claims.
        </Alert>
      )}
    </div>
  )
}
