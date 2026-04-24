import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../../auth/AuthContext'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import type { ApiResponse } from '../../types/api'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Card, CardContent } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { BudgetFundingSection } from '../../components/budgets/BudgetFundingSection'

interface PurposeRow {
  id: number
  name: string
  is_active: boolean
  purpose_type: 'expense' | 'fee'
}

interface ClaimResponse {
  id: number
  claim_number: string
  employee_id: number
  purpose_id: number
  expense_amount: number
  fee_amount: number
  payee_name: string | null
  description: string
  expense_date: string
  proof_text: string | null
  proof_attachment_id: number | null
  fee_proof_text: string | null
  fee_proof_attachment_id: number | null
  status: string
  edit_comment: string | null
  auto_created_from_payment: boolean
  budget_id: number | null
  funding_source: 'personal_funds' | 'budget'
}

export const EditExpenseClaimPage = () => {
  const { claimId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const resolvedId = claimId ? Number(claimId) : null

  const { data: claim, loading: claimLoading, error: claimError } = useApi<ClaimResponse>(
    resolvedId ? `/compensations/claims/${resolvedId}` : null
  )
  const { data: purposesData, loading: purposesLoading, error: purposesError } = useApi<PurposeRow[]>(
    '/procurement/payment-purposes',
    { params: { include_inactive: false, purpose_type: 'expense' } },
    []
  )
  const purposes = useMemo(() => purposesData ?? [], [purposesData])

  const [purposeId, setPurposeId] = useState<number | ''>('')
  const [fundingSource, setFundingSource] = useState<'personal_funds' | 'budget'>('personal_funds')
  const [budgetId, setBudgetId] = useState<number | ''>('')
  const [expenseDate, setExpenseDate] = useState('')
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

  const { execute: updateClaim, loading: updating, error: updateError } = useApiMutation()
  const { execute: submitClaim, loading: submitting, error: submitError } = useApiMutation()

  useEffect(() => {
    if (!claim) return
    setPurposeId(claim.purpose_id)
    setFundingSource(claim.funding_source ?? 'personal_funds')
    setBudgetId(claim.budget_id ?? '')
    setExpenseDate(claim.expense_date)
    setAmount(String(claim.expense_amount))
    setPayeeName(claim.payee_name ?? '')
    setDescription(claim.description)
    setProofText(claim.proof_text ?? '')
    setProofAttachmentId(claim.proof_attachment_id ?? null)
    setFeeAmount(String(claim.fee_amount ?? 0))
    setFeeProofText(claim.fee_proof_text ?? '')
    setFeeProofAttachmentId(claim.fee_proof_attachment_id ?? null)
  }, [claim])

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

  const validateForm = () => {
    if (!purposeId) return 'Select category (purpose).'
    if (fundingSource === 'budget' && !budgetId) return 'Select budget for budget-funded claim.'
    const amountValue = Number(amount)
    if (!amountValue || amountValue <= 0) return 'Amount must be greater than 0.'
    if (!expenseDate) return 'Select expense date.'
    if (!description.trim()) return 'Description is required.'
    const hasProofText = Boolean(proofText.trim())
    const hasProofFile = proofAttachmentId != null
    if (!hasProofText && !hasProofFile) return 'Proof (text) or receipt file is required.'

    const feeAmountValue = feeAmount.trim() ? Number(feeAmount) : 0
    if (Number.isNaN(feeAmountValue) || feeAmountValue < 0) return 'Transaction fee must be 0 or greater.'
    if (feeAmountValue > 0) {
      const hasFeeProofText = Boolean(feeProofText.trim())
      const hasFeeProofFile = feeProofAttachmentId != null
      if (!hasFeeProofText && !hasFeeProofFile) {
        return 'Fee proof (text) or file is required when fee is provided.'
      }
    }
    return null
  }

  const handleSave = async () => {
    if (!resolvedId) return
    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)

    const feeAmountValue = feeAmount.trim() ? Number(feeAmount) : 0
    const result = await updateClaim(() =>
      api.patch(`/compensations/claims/${resolvedId}`, {
        budget_id: fundingSource === 'budget' && budgetId ? Number(budgetId) : null,
        funding_source: fundingSource,
        purpose_id: Number(purposeId),
        amount: Number(amount),
        payee_name: payeeName.trim() || null,
        description: description.trim(),
        expense_date: expenseDate,
        proof_text: proofText.trim() || null,
        proof_attachment_id: proofAttachmentId,
        fee_amount: feeAmountValue > 0 ? feeAmountValue : 0,
        fee_proof_text: feeProofText.trim() || null,
        fee_proof_attachment_id: feeProofAttachmentId,
      })
    )
    if (result) {
      navigate(`/compensations/claims/${resolvedId}`)
    }
  }

  const handleResubmit = async () => {
    if (!resolvedId) return
    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)

    const saveResult = await updateClaim(() =>
      api.patch(`/compensations/claims/${resolvedId}`, {
        budget_id: fundingSource === 'budget' && budgetId ? Number(budgetId) : null,
        funding_source: fundingSource,
        purpose_id: Number(purposeId),
        amount: Number(amount),
        payee_name: payeeName.trim() || null,
        description: description.trim(),
        expense_date: expenseDate,
        proof_text: proofText.trim() || null,
        proof_attachment_id: proofAttachmentId,
        fee_amount: feeAmount.trim() ? Number(feeAmount) : 0,
        fee_proof_text: feeProofText.trim() || null,
        fee_proof_attachment_id: feeProofAttachmentId,
      })
    )
    if (!saveResult) return

    const submitResult = await submitClaim(() => api.post(`/compensations/claims/${resolvedId}/submit`))
    if (submitResult) {
      navigate(`/compensations/claims/${resolvedId}`)
    }
  }

  if (claimLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!claim || !resolvedId) {
    return <Alert severity="error">{claimError || 'Claim not found.'}</Alert>
  }

  const isOwner = user?.id === claim.employee_id
  const canEditStatus =
    !claim.auto_created_from_payment &&
    (claim.status === 'pending_approval' || claim.status === 'needs_edit' || claim.status === 'draft')
  if (!isOwner) {
    return <Alert severity="error">You can only edit your own claims.</Alert>
  }
  if (!canEditStatus) {
    return <Alert severity="error">Only non-final manual claims can be edited.</Alert>
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <Typography variant="h4">Edit expense claim</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {claim.claim_number}
          </Typography>
        </div>
        <Button variant="outlined" onClick={() => navigate(`/compensations/claims/${resolvedId}`)}>
          Back
        </Button>
      </div>

      {(error || claimError || purposesError || updateError || submitError) && (
        <Alert severity="error" className="mb-4">
          {error || claimError || purposesError || updateError || submitError}
        </Alert>
      )}

      {claim.edit_comment && (
        <Alert severity="warning" className="mb-4">
          <strong>Needs edit comment:</strong> {claim.edit_comment}
        </Alert>
      )}

      <Card>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Category (purpose)"
              value={purposeId}
              onChange={(e) => setPurposeId(e.target.value === '' ? '' : Number(e.target.value))}
              disabled={purposesLoading}
              required
            >
              <option value="">Select category</option>
              {purposes.map((p) => (
                <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>

            <BudgetFundingSection
              fundingSource={fundingSource}
              onFundingSourceChange={(value) => {
                setFundingSource(value)
                if (value === 'personal_funds') {
                  setBudgetId('')
                }
              }}
              budgetId={budgetId}
              onBudgetIdChange={setBudgetId}
              employeeId={claim.employee_id}
              purposeId={purposeId}
              effectiveDate={expenseDate}
            />

            <Input
              label="Expense date"
              type="date"
              value={expenseDate}
              onChange={(e) => setExpenseDate(e.target.value)}
              required
            />

            <Input
              label="Amount"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              required
            />

            <Input
              label="Payee / vendor (optional)"
              value={payeeName}
              onChange={(e) => setPayeeName(e.target.value)}
              placeholder="Shell / Uber / Local shop"
            />
          </div>

          <div className="mt-4">
            <Textarea
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
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
                  disabled={uploadingProof}
                  accept="image/*,application/pdf"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) uploadProofFile(file)
                    e.target.value = ''
                  }}
                />
                <Button type="button" variant="outlined" disabled={uploadingProof} onClick={() => proofFileInputRef.current?.click()}>
                  {uploadingProof ? 'Uploading...' : 'Upload receipt'}
                </Button>

                {uploadingProof && <Spinner size="small" />}
                {proofAttachmentId != null && (
                  <Typography variant="body2" className="truncate max-w-[320px]">
                    {proofFileName ?? `Attachment #${proofAttachmentId}`}
                  </Typography>
                )}
                {proofAttachmentId != null && (
                  <Button type="button" variant="text" color="secondary" onClick={() => {
                    setProofAttachmentId(null)
                    setProofFileName(null)
                  }}>
                    Remove
                  </Button>
                )}
              </div>
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
                placeholder="0.00"
                min={0}
              />

              <div className="hidden md:block" />

              <Textarea
                label="Fee proof (text)"
                value={feeProofText}
                onChange={(e) => setFeeProofText(e.target.value)}
                rows={3}
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
                    disabled={uploadingFeeProof}
                    accept="image/*,application/pdf"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) uploadFeeProofFile(file)
                      e.target.value = ''
                    }}
                  />
                  <Button type="button" variant="outlined" disabled={uploadingFeeProof} onClick={() => feeProofFileInputRef.current?.click()}>
                    {uploadingFeeProof ? 'Uploading...' : 'Upload fee proof'}
                  </Button>

                  {uploadingFeeProof && <Spinner size="small" />}
                  {feeProofAttachmentId != null && (
                    <Typography variant="body2" className="truncate max-w-[320px]">
                      {feeProofFileName ?? `Attachment #${feeProofAttachmentId}`}
                    </Typography>
                  )}
                  {feeProofAttachmentId != null && (
                    <Button type="button" variant="text" color="secondary" onClick={() => {
                      setFeeProofAttachmentId(null)
                      setFeeProofFileName(null)
                    }}>
                      Remove
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outlined" onClick={handleSave} disabled={updating || submitting || uploadingProof || uploadingFeeProof}>
              {updating ? <Spinner size="small" /> : 'Save changes'}
            </Button>
            {claim.status === 'needs_edit' && (
              <Button onClick={handleResubmit} disabled={updating || submitting || uploadingProof || uploadingFeeProof}>
                {submitting ? <Spinner size="small" /> : 'Resubmit for approval'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
