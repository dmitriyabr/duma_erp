import axios from 'axios'
import { useCallback, useMemo, useRef, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { isSuperAdmin } from '../../utils/permissions'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import {
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  Switch,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

type MatchedEntityType = 'procurement_payment' | 'compensation_payout'

interface BankStatementImportListItem {
  id: number
  attachment_id: number
  file_name: string
  range_from?: string | null
  range_to?: string | null
  created_by_id: number
  created_at: string
}

interface BankTransactionMatchInfo {
  id: number
  entity_type: MatchedEntityType
  entity_id: number
  entity_number: string
  match_method: string
  confidence: string
  matched_at: string
  proof_attachment_id: number | null
}

interface BankTransactionResponse {
  id: number
  transaction_date: string
  value_date: string
  description: string
  debit_raw: string | null
  credit_raw: string | null
  amount: string
  account_owner_reference: string | null
  txn_type: string | null
  match: BankTransactionMatchInfo | null
}

interface BankStatementImportTransactionResponse {
  id: number
  row_index: number
  raw_row: Record<string, string>
  transaction: BankTransactionResponse
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

interface BankStatementImportDetail {
  statement_import: BankStatementImportListItem
  rows: PaginatedResponse<BankStatementImportTransactionResponse>
}

interface AutoMatchResult {
  matched: number
  ambiguous: number
  no_candidates: number
}

const normMoney = (value: string): string => {
  const cleaned = value.replace(/,/g, '').trim()
  const n = Number.parseFloat(cleaned)
  if (Number.isNaN(n)) return cleaned
  return n.toFixed(2)
}

const moneyNumber = (value: string): number | null => {
  const cleaned = value.replace(/,/g, '').trim()
  const n = Number.parseFloat(cleaned)
  if (Number.isNaN(n)) return null
  return n
}

const withinOne = (a: string, b: string): boolean => {
  const an = moneyNumber(a)
  const bn = moneyNumber(b)
  if (an == null || bn == null) return false
  return Math.abs(an - bn) <= 1.0 + 1e-9
}

const absMoney = (value: string): string => {
  const n = Number.parseFloat(value.replace(/,/g, '').trim())
  if (Number.isNaN(n)) return value
  return Math.abs(n).toFixed(2)
}

interface UnmatchedProcurementPayment {
  id: number
  payment_number: string
  payment_date: string
  amount: string
  payee_name: string | null
  reference_number: string | null
}

interface UnmatchedCompensationPayout {
  id: number
  payout_number: string
  payout_date: string
  amount: string
  reference_number: string | null
}

interface ImportReconciliationSummary {
  import_id: number
  range_from: string | null
  range_to: string | null
  unmatched_transactions: number
  unmatched_procurement_payments: UnmatchedProcurementPayment[]
  unmatched_compensation_payouts: UnmatchedCompensationPayout[]
}

export const BankReconciliationPage = () => {
  const { user } = useAuth()
  const accessDenied = !isSuperAdmin(user)

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null)
  const [selectedImportId, setSelectedImportId] = useState<number | null>(null)
  const [onlyUnmatched, setOnlyUnmatched] = useState(true)
  const [ignoreRange, setIgnoreRange] = useState(false)
  const [txnType, setTxnType] = useState<'all' | string>('all')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [manualMatchTxnId, setManualMatchTxnId] = useState<number | null>(null)
  const [manualMatchType, setManualMatchType] = useState<MatchedEntityType>('procurement_payment')
  const [manualMatchEntityId, setManualMatchEntityId] = useState<number | ''>('')
  const [manualMatchEntity, setManualMatchEntity] = useState<{
    type: MatchedEntityType
    id: number
  } | null>(null)
  const [manualMatchTxnForEntityId, setManualMatchTxnForEntityId] = useState<number | ''>('')

  const { data: imports, loading: importsLoading, error: importsError, refetch: refetchImports } =
    useApi<BankStatementImportListItem[]>(accessDenied ? null : '/bank-statements/imports')

  const effectiveImportId = selectedImportId ?? (imports && imports.length ? imports[0].id : null)

  const selectedImport = useMemo(
    () => (imports || []).find((i) => i.id === effectiveImportId) || null,
    [imports, effectiveImportId]
  )

  const detailUrl = useMemo(() => {
    if (accessDenied || !effectiveImportId) return null
    const params = new URLSearchParams()
    params.set('page', '1')
    params.set('limit', '100')
    if (onlyUnmatched) params.set('only_unmatched', 'true')
    if (txnType !== 'all' && txnType.trim()) params.set('txn_type', txnType.trim())
    return `/bank-statements/imports/${effectiveImportId}?${params.toString()}`
  }, [accessDenied, effectiveImportId, onlyUnmatched, txnType])

  const txnTypesUrl = useMemo(() => {
    if (accessDenied) return null
    const params = new URLSearchParams()
    if (selectedImport?.range_from) params.set('date_from', selectedImport.range_from)
    if (selectedImport?.range_to) params.set('date_to', selectedImport.range_to)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return `/bank-statements/txn-types${suffix}`
  }, [accessDenied, selectedImport])

  const { data: txnTypes } = useApi<string[]>(txnTypesUrl)

  const reconciliationUrl = useMemo(() => {
    if (accessDenied || !effectiveImportId) return null
    const params = new URLSearchParams()
    if (ignoreRange) params.set('ignore_range', 'true')
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return `/bank-statements/imports/${effectiveImportId}/reconciliation${suffix}`
  }, [accessDenied, effectiveImportId, ignoreRange])

  const {
    data: importDetail,
    loading: detailLoading,
    error: detailError,
    refetch: refetchDetail,
  } = useApi<BankStatementImportDetail>(detailUrl)

  const {
    data: reconciliation,
    loading: reconciliationLoading,
    error: reconciliationError,
    refetch: refetchReconciliation,
  } = useApi<ImportReconciliationSummary>(reconciliationUrl)

  const uploadMutation = useApiMutation<{
    id: number
    attachment_id: number
    file_name: string
    rows_total: number
    transactions_created: number
    transactions_linked_existing: number
    errors: string[]
  }>()

  const autoMatchMutation = useApiMutation<AutoMatchResult>()
  const manualMatchMutation = useApiMutation<BankTransactionMatchInfo>()
  const unmatchMutation = useApiMutation<{ ok: boolean }>()

  const handleUpload = async () => {
    const file = selectedFile
    if (!file) {
      setError('Select a CSV file.')
      return
    }
    setError(null)
    setSuccess(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const result = await uploadMutation.execute(() =>
        api.post('/bank-statements/imports', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      )
      if (!result) return

      setSuccess(
        `Imported ${result.rows_total} rows (new: ${result.transactions_created}, existing: ${result.transactions_linked_existing}).`
      )
      if (result.errors?.length) {
        setError(`Imported with ${result.errors.length} warnings. First: ${result.errors[0]}`)
      }

      if (fileInputRef.current) fileInputRef.current.value = ''
      setSelectedFile(null)
      setSelectedFileName(null)
      await refetchImports()
      setSelectedImportId(result.id)
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 401) return
      setError('Failed to import bank statement.')
    }
  }

  const openFilePicker = () => {
    setError(null)
    // Reset the input so picking the same file again triggers onChange reliably.
    if (fileInputRef.current) fileInputRef.current.value = ''
    fileInputRef.current?.click()
  }

  const handleAutoMatch = async () => {
    if (!effectiveImportId) return
    setError(null)
    setSuccess(null)

    const result = await autoMatchMutation.execute(() =>
      api.post(`/bank-statements/imports/${effectiveImportId}/auto-match`)
    )
    if (!result) return
    setSuccess(
      `Auto-match done. Matched: ${result.matched}, ambiguous: ${result.ambiguous}, no candidates: ${result.no_candidates}.`
    )
    await refetchDetail()
    await refetchReconciliation()
  }

  const refreshAll = useCallback(async () => {
    setError(null)
    setSuccess(null)
    await refetchImports()
    await refetchDetail()
    await refetchReconciliation()
  }, [refetchImports, refetchDetail, refetchReconciliation])

  const manualCandidates = useMemo(() => {
    if (!manualMatchTxnId) return { procurement: [] as UnmatchedProcurementPayment[], payouts: [] as UnmatchedCompensationPayout[] }
    const row = importDetail?.rows.items.find((r) => r.transaction.id === manualMatchTxnId)
    if (!row) return { procurement: [] as UnmatchedProcurementPayment[], payouts: [] as UnmatchedCompensationPayout[] }
    const target = absMoney(row.transaction.amount)
    const procurement = (reconciliation?.unmatched_procurement_payments || []).filter((p) =>
      withinOne(normMoney(p.amount), target)
    )
    const payouts = (reconciliation?.unmatched_compensation_payouts || []).filter((p) =>
      withinOne(normMoney(p.amount), target)
    )
    return { procurement, payouts }
  }, [manualMatchTxnId, importDetail, reconciliation])

  const openManualMatch = (txnId: number) => {
    setManualMatchTxnId(txnId)
    setManualMatchType('procurement_payment')
    setManualMatchEntityId('')
    setError(null)
    setSuccess(null)
  }

  const closeManualMatch = () => {
    setManualMatchTxnId(null)
    setManualMatchEntityId('')
  }

  const openManualMatchForEntity = (type: MatchedEntityType, id: number) => {
    setManualMatchEntity({ type, id })
    setManualMatchTxnForEntityId('')
    setError(null)
    setSuccess(null)
  }

  const closeManualMatchForEntity = () => {
    setManualMatchEntity(null)
    setManualMatchTxnForEntityId('')
  }

  const txnCandidatesForEntity = useMemo(() => {
    if (!manualMatchEntity) return []

    const entity =
      manualMatchEntity.type === 'procurement_payment'
        ? (reconciliation?.unmatched_procurement_payments || []).find((p) => p.id === manualMatchEntity.id)
        : (reconciliation?.unmatched_compensation_payouts || []).find((p) => p.id === manualMatchEntity.id)

    if (!entity) return []

    const entityAmount = normMoney(entity.amount)

    return (importDetail?.rows.items || [])
      .filter((r) => !r.transaction.match)
      .filter((r) => withinOne(absMoney(r.transaction.amount), entityAmount))
      .map((r) => {
        const desc = r.transaction.description.length > 80
          ? `${r.transaction.description.slice(0, 80)}…`
          : r.transaction.description
        return {
          id: r.transaction.id,
          label: `${r.transaction.value_date} • ${r.transaction.txn_type || '—'} • ${absMoney(r.transaction.amount)} • ${desc}`,
        }
      })
  }, [manualMatchEntity, importDetail, reconciliation])

  const submitManualMatchForEntity = async () => {
    if (!manualMatchEntity) return
    if (!manualMatchTxnForEntityId || typeof manualMatchTxnForEntityId !== 'number') {
      setError('Select a bank transaction to match.')
      return
    }
    setError(null)
    setSuccess(null)
    const result = await manualMatchMutation.execute(() =>
      api.post(`/bank-statements/transactions/${manualMatchTxnForEntityId}/match`, {
        entity_type: manualMatchEntity.type,
        entity_id: manualMatchEntity.id,
      })
    )
    if (!result) return
    setSuccess(`Matched transaction #${manualMatchTxnForEntityId} to ${result.entity_type} #${result.entity_id}.`)
    closeManualMatchForEntity()
    await refetchDetail()
    await refetchReconciliation()
  }

  const submitManualMatch = async () => {
    if (!manualMatchTxnId) return
    if (!manualMatchEntityId || typeof manualMatchEntityId !== 'number') {
      setError('Select an entity to match.')
      return
    }
    setError(null)
    setSuccess(null)
    const result = await manualMatchMutation.execute(() =>
      api.post(`/bank-statements/transactions/${manualMatchTxnId}/match`, {
        entity_type: manualMatchType,
        entity_id: manualMatchEntityId,
      })
    )
    if (!result) return
    setSuccess(`Matched transaction #${manualMatchTxnId} to ${result.entity_type} #${result.entity_id}.`)
    closeManualMatch()
    await refetchDetail()
    await refetchReconciliation()
  }

  const unmatchTransaction = async (txnId: number) => {
    setError(null)
    setSuccess(null)
    const result = await unmatchMutation.execute(() =>
      api.delete(`/bank-statements/transactions/${txnId}/match`)
    )
    if (!result) return
    setSuccess(`Unmatched transaction #${txnId}.`)
    await refetchDetail()
    await refetchReconciliation()
  }

  const effectiveError = error || importsError || detailError || reconciliationError

  if (accessDenied) {
    return <Navigate to="/access-denied" replace />
  }

  return (
    <div>
      <Typography variant="h4" className="font-bold mb-4">
        Bank reconciliation
      </Typography>

      {effectiveError ? (
        <Alert severity="error" className="mb-4">
          {effectiveError}
        </Alert>
      ) : null}
      {success ? (
        <Alert severity="success" className="mb-4">
          {success}
        </Alert>
      ) : null}

      <div className="mb-4">
        {/* Row 1: import + primary actions */}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outlined"
            type="button"
            onClick={openFilePicker}
            disabled={uploadMutation.loading}
          >
            {selectedFileName ? 'Change CSV' : 'Select CSV'}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            className="sr-only"
            accept=".csv,text/csv"
            onChange={(e) => {
              const file = e.currentTarget.files?.[0] || null
              setSelectedFile(file)
              setSelectedFileName(file ? file.name : null)
            }}
          />
          <Button
            variant="contained"
            onClick={handleUpload}
            disabled={uploadMutation.loading || !selectedFile}
          >
            {uploadMutation.loading ? 'Importing…' : 'Import statement'}
          </Button>
          <Typography variant="body2" color="secondary" className="flex-1 min-w-[240px]">
            {selectedFileName ? `Selected: ${selectedFileName}` : 'Select a CSV, then click "Import statement".'}
          </Typography>
          <Button
            variant="outlined"
            onClick={refreshAll}
            disabled={importsLoading || detailLoading || reconciliationLoading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            onClick={handleAutoMatch}
            disabled={!effectiveImportId || autoMatchMutation.loading}
          >
            {autoMatchMutation.loading ? 'Matching…' : 'Auto-match'}
          </Button>
        </div>

        {/* Row 2: filters */}
        <div className="flex flex-wrap items-center gap-6 mt-3">
          <Switch
            checked={onlyUnmatched}
            onChange={(e) => setOnlyUnmatched(e.target.checked)}
            label="Show only unmatched"
          />
          <Select
            containerClassName="w-[240px] min-w-[200px]"
            value={txnType}
            onChange={(e) => setTxnType(e.target.value as typeof txnType)}
          >
            <option value="all">All types</option>
            {(txnTypes || []).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <Switch
            checked={ignoreRange}
            onChange={(e) => setIgnoreRange(e.target.checked)}
            label="Ignore date range"
          />
        </div>
      </div>

      <div className="flex gap-6 flex-wrap mb-6">
        <div className="min-w-[320px] flex-1">
          <Typography variant="h6" className="mb-2">
            Imports
          </Typography>
          {importsLoading ? (
            <div className="flex items-center gap-2">
              <Spinner size="small" /> <Typography>Loading…</Typography>
            </div>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>ID</TableHeaderCell>
                  <TableHeaderCell>File</TableHeaderCell>
                  <TableHeaderCell>Created</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(imports || []).map((imp) => (
                  <TableRow
                    key={imp.id}
                    className={
                      imp.id === effectiveImportId
                        ? 'bg-primary/10 hover:bg-primary/15 cursor-pointer'
                        : 'cursor-pointer hover:bg-slate-100'
                    }
                    onClick={() => setSelectedImportId(imp.id)}
                  >
                    <TableCell>{imp.id}</TableCell>
                    <TableCell>{imp.file_name}</TableCell>
                    <TableCell>{new Date(imp.created_at).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
                {!imports?.length ? (
                  <TableRow>
                    <td colSpan={3} className="px-4 py-3">
                      No imports yet
                    </td>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          )}
        </div>

        <div className="min-w-[360px] flex-1">
          <Typography variant="h6" className="mb-2">
            Summary
          </Typography>
          {reconciliationLoading ? (
            <div className="flex items-center gap-2">
              <Spinner size="small" /> <Typography>Loading…</Typography>
            </div>
          ) : reconciliation ? (
            <div className="grid gap-1">
              <Typography variant="body2" color="secondary">
                Range: {reconciliation.range_from || '—'} → {reconciliation.range_to || '—'}
              </Typography>
              <Typography>Unmatched transactions: {reconciliation.unmatched_transactions}</Typography>
              <Typography>
                Unmatched procurement payments: {reconciliation.unmatched_procurement_payments.length}
              </Typography>
              <Typography>
                Unmatched compensation payouts: {reconciliation.unmatched_compensation_payouts.length}
              </Typography>
            </div>
          ) : (
            <Typography variant="body2" color="secondary">
              Select an import to see summary.
            </Typography>
          )}
        </div>
      </div>

      <Typography variant="h6" className="mb-2">
        Statement rows
      </Typography>
      {detailLoading ? (
        <div className="flex items-center gap-2">
          <Spinner size="small" /> <Typography>Loading…</Typography>
        </div>
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Date</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Description</TableHeaderCell>
              <TableHeaderCell align="right">Amount</TableHeaderCell>
              <TableHeaderCell>Match</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(importDetail?.rows.items || []).map((r) => {
              const m = r.transaction.match
              return (
                <TableRow key={r.id}>
                  <TableCell>{r.transaction.value_date}</TableCell>
                  <TableCell>{r.transaction.txn_type || '—'}</TableCell>
                  <TableCell className="max-w-[640px] truncate">
                    {r.transaction.description}
                  </TableCell>
                  <TableCell align="right">{r.transaction.amount}</TableCell>
                  <TableCell>
                    {m ? (
                      <div className="flex items-center gap-2 flex-wrap">
                        {m.entity_type === 'procurement_payment' ? (
                          <RouterLink to={`/procurement/payments/${m.entity_id}`}>
                            <Button
                              size="small"
                              variant="text"
                              className="px-0 py-0 rounded-none hover:bg-transparent focus:bg-transparent hover:underline underline-offset-4"
                            >
                              {m.entity_number}
                            </Button>
                          </RouterLink>
                        ) : (
                          <RouterLink to={`/compensations/payouts/${m.entity_id}`}>
                            <Button
                              size="small"
                              variant="text"
                              className="px-0 py-0 rounded-none hover:bg-transparent focus:bg-transparent hover:underline underline-offset-4"
                            >
                              {m.entity_number}
                            </Button>
                          </RouterLink>
                        )}
                        {m.proof_attachment_id ? (
                          <a
                            href={`/attachment/${m.proof_attachment_id}/download`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <Button size="small" variant="outlined">
                              Proof
                            </Button>
                          </a>
                        ) : null}
                        <Button
                          size="small"
                          variant="outlined"
                          color="warning"
                          onClick={() => unmatchTransaction(r.transaction.id)}
                          disabled={unmatchMutation.loading}
                        >
                          Unmatch
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 flex-wrap">
                        <Typography variant="body2" color="secondary">
                          Unmatched
                        </Typography>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => openManualMatch(r.transaction.id)}
                        >
                          Manual match
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
            {!importDetail?.rows.items.length ? (
              <TableRow>
                <td colSpan={5} className="px-4 py-3">
                  {effectiveImportId ? 'No rows found for this filter.' : 'Select an import.'}
                </td>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      )}

      <div className="mt-6 grid gap-6">
        <div>
          <Typography variant="h6" className="mb-2">
            Unmatched procurement payments (company paid)
          </Typography>
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Number</TableHeaderCell>
                <TableHeaderCell>Payee</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(reconciliation?.unmatched_procurement_payments || []).slice(0, 50).map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.payment_date}</TableCell>
                  <TableCell>{p.payment_number}</TableCell>
                  <TableCell>{p.payee_name || '—'}</TableCell>
                  <TableCell align="right">{p.amount}</TableCell>
                  <TableCell align="right">
                    <div className="flex justify-end gap-2 flex-wrap">
                      <Button
                        size="small"
                        onClick={() => openManualMatchForEntity('procurement_payment', p.id)}
                      >
                        Manual match
                      </Button>
                      <RouterLink to={`/procurement/payments/${p.id}`}>
                        <Button size="small">Open</Button>
                      </RouterLink>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!reconciliation?.unmatched_procurement_payments?.length ? (
                <TableRow>
                  <td colSpan={5} className="px-4 py-3">
                    No unmatched payments
                  </td>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>

        <div>
          <Typography variant="h6" className="mb-2">
            Unmatched compensation payouts
          </Typography>
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Number</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
                <TableHeaderCell align="right">Actions</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(reconciliation?.unmatched_compensation_payouts || []).slice(0, 50).map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.payout_date}</TableCell>
                  <TableCell>{p.payout_number}</TableCell>
                  <TableCell align="right">{p.amount}</TableCell>
                  <TableCell align="right">
                    <div className="flex justify-end gap-2 flex-wrap">
                      <Button
                        size="small"
                        onClick={() => openManualMatchForEntity('compensation_payout', p.id)}
                      >
                        Manual match
                      </Button>
                      <RouterLink to={`/compensations/payouts/${p.id}`}>
                        <Button size="small">Open</Button>
                      </RouterLink>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!reconciliation?.unmatched_compensation_payouts?.length ? (
                <TableRow>
                  <td colSpan={4} className="px-4 py-3">
                    No unmatched payouts
                  </td>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </div>

      <Dialog open={manualMatchTxnId !== null} onClose={closeManualMatch} maxWidth="sm" fullWidth>
        <DialogTitle>Manual match</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="secondary" className="mb-4">
            Pick an unmatched internal document by amount (± 1.00). This is a read-write operation (Admin/SuperAdmin).
          </Typography>
          <div className="grid gap-4">
            <div>
              <Typography variant="body2" className="mb-1">
                Entity type
              </Typography>
              <Select
                value={manualMatchType}
                onChange={(e) => {
                  const t = e.target.value as MatchedEntityType
                  setManualMatchType(t)
                  setManualMatchEntityId('')
                }}
              >
                <option value="procurement_payment">Procurement payment (company paid)</option>
                <option value="compensation_payout">Compensation payout</option>
              </Select>
            </div>
            <div>
              <Typography variant="body2" className="mb-1">
                Entity
              </Typography>
              <Select
                value={manualMatchEntityId}
                onChange={(e) => setManualMatchEntityId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">Select…</option>
                {(manualMatchType === 'procurement_payment'
                  ? manualCandidates.procurement.map((p) => ({
                      id: p.id,
                      label: `${p.payment_date} • ${p.payment_number} • ${p.amount}${p.payee_name ? ` • ${p.payee_name}` : ''}`,
                    }))
                  : manualCandidates.payouts.map((p) => ({
                      id: p.id,
                      label: `${p.payout_date} • ${p.payout_number} • ${p.amount}`,
                    }))
                ).map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <Typography variant="caption" color="secondary">
                Candidates are filtered from "unmatched" lists by amount (± 1.00).
              </Typography>
            </div>
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeManualMatch}>Cancel</Button>
          <Button variant="contained" onClick={submitManualMatch} disabled={manualMatchMutation.loading}>
            {manualMatchMutation.loading ? 'Matching…' : 'Match'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={manualMatchEntity !== null} onClose={closeManualMatchForEntity} maxWidth="sm" fullWidth>
        <DialogTitle>Manual match</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="secondary" className="mb-4">
            Pick an unmatched bank transaction to match to this document (amount tolerance: ± 1.00).
          </Typography>
          <div className="grid gap-4">
            <div>
              <Typography variant="body2" className="mb-1">
                Bank transaction
              </Typography>
              <Select
                value={manualMatchTxnForEntityId}
                onChange={(e) => setManualMatchTxnForEntityId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">Select…</option>
                {txnCandidatesForEntity.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <Typography variant="caption" color="secondary">
                Candidates are filtered to unmatched statement rows by amount (± 1.00).
              </Typography>
            </div>
          </div>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeManualMatchForEntity}>Cancel</Button>
          <Button
            variant="contained"
            onClick={submitManualMatchForEntity}
            disabled={manualMatchMutation.loading}
          >
            {manualMatchMutation.loading ? 'Matching…' : 'Match'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
