import axios from 'axios'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  MenuItem,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { isAccountant } from '../../utils/permissions'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'

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
  if (isAccountant(user)) {
    return <Navigate to="/access-denied" replace />
  }

  const fileInputRef = useRef<HTMLInputElement | null>(null)
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
    useApi<BankStatementImportListItem[]>('/bank-statements/imports')

  const selectedImport = useMemo(
    () => (imports || []).find((i) => i.id === selectedImportId) || null,
    [imports, selectedImportId]
  )

  useEffect(() => {
    if (!selectedImportId && imports && imports.length) {
      setSelectedImportId(imports[0].id)
    }
  }, [imports, selectedImportId])

  const detailUrl = useMemo(() => {
    if (!selectedImportId) return null
    const params = new URLSearchParams()
    params.set('page', '1')
    params.set('limit', '100')
    if (onlyUnmatched) params.set('only_unmatched', 'true')
    if (txnType !== 'all' && txnType.trim()) params.set('txn_type', txnType.trim())
    return `/bank-statements/imports/${selectedImportId}?${params.toString()}`
  }, [selectedImportId, onlyUnmatched, txnType])

  const txnTypesUrl = useMemo(() => {
    const params = new URLSearchParams()
    if (selectedImport?.range_from) params.set('date_from', selectedImport.range_from)
    if (selectedImport?.range_to) params.set('date_to', selectedImport.range_to)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return `/bank-statements/txn-types${suffix}`
  }, [selectedImport?.range_from, selectedImport?.range_to])

  const { data: txnTypes } = useApi<string[]>(txnTypesUrl)

  const reconciliationUrl = useMemo(() => {
    if (!selectedImportId) return null
    const params = new URLSearchParams()
    if (ignoreRange) params.set('ignore_range', 'true')
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return `/bank-statements/imports/${selectedImportId}/reconciliation${suffix}`
  }, [selectedImportId, ignoreRange])

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
    const file = fileInputRef.current?.files?.[0]
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
      setSelectedFileName(null)
      await refetchImports()
      setSelectedImportId(result.id)
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 401) return
      setError('Failed to import bank statement.')
    }
  }

  const handleAutoMatch = async () => {
    if (!selectedImportId) return
    setError(null)
    setSuccess(null)

    const result = await autoMatchMutation.execute(() =>
      api.post(`/bank-statements/imports/${selectedImportId}/auto-match`)
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

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Bank reconciliation
      </Typography>

      {effectiveError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {effectiveError}
        </Alert>
      ) : null}
      {success ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      ) : null}

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Button variant="outlined" component="label" disabled={uploadMutation.loading}>
          {selectedFileName ? 'Change CSV' : 'Select CSV'}
          <input
            ref={fileInputRef}
            type="file"
            hidden
            accept=".csv,text/csv"
            onChange={(e) => {
              const file = e.currentTarget.files?.[0]
              setSelectedFileName(file ? file.name : null)
            }}
          />
        </Button>
        <Button
          variant="contained"
          onClick={handleUpload}
          disabled={uploadMutation.loading || !selectedFileName}
        >
          {uploadMutation.loading ? 'Importing…' : 'Import statement'}
        </Button>
        {selectedFileName ? (
          <Typography variant="body2" color="text.secondary">
            Selected: {selectedFileName}
          </Typography>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Select a CSV, then click “Import statement”.
          </Typography>
        )}
        <Divider flexItem orientation="vertical" />
        <Button variant="outlined" onClick={refreshAll} disabled={importsLoading || detailLoading || reconciliationLoading}>
          Refresh
        </Button>
        <Button
          variant="contained"
          onClick={handleAutoMatch}
          disabled={!selectedImportId || autoMatchMutation.loading}
        >
          {autoMatchMutation.loading ? 'Matching…' : 'Auto-match'}
        </Button>
        <FormControlLabel
          control={
            <Switch
              checked={onlyUnmatched}
              onChange={(e) => setOnlyUnmatched(e.target.checked)}
            />
          }
          label="Show only unmatched"
        />
        <Select
          size="small"
          value={txnType}
          onChange={(e) => setTxnType(e.target.value as typeof txnType)}
          sx={{ width: 160 }}
        >
          <MenuItem value="all">All types</MenuItem>
          {(txnTypes || []).map((t) => (
            <MenuItem key={t} value={t}>
              {t}
            </MenuItem>
          ))}
        </Select>
        <FormControlLabel
          control={
            <Switch
              checked={ignoreRange}
              onChange={(e) => setIgnoreRange(e.target.checked)}
            />
          }
          label="Ignore date range"
        />
      </Box>

      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 3 }}>
        <Box sx={{ minWidth: 320, flex: 1 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Imports
          </Typography>
          {importsLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={18} /> <Typography>Loading…</Typography>
            </Box>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>File</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(imports || []).map((imp) => (
                  <TableRow
                    key={imp.id}
                    hover
                    selected={imp.id === selectedImportId}
                    onClick={() => setSelectedImportId(imp.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{imp.id}</TableCell>
                    <TableCell>{imp.file_name}</TableCell>
                    <TableCell>{new Date(imp.created_at).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
                {!imports?.length ? (
                  <TableRow>
                    <TableCell colSpan={3}>No imports yet</TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          )}
        </Box>

        <Box sx={{ minWidth: 360, flex: 1 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Summary
          </Typography>
          {reconciliationLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={18} /> <Typography>Loading…</Typography>
            </Box>
          ) : reconciliation ? (
            <Box sx={{ display: 'grid', gap: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                Range: {reconciliation.range_from || '—'} → {reconciliation.range_to || '—'}
              </Typography>
              <Typography>Unmatched transactions: {reconciliation.unmatched_transactions}</Typography>
              <Typography>
                Unmatched procurement payments: {reconciliation.unmatched_procurement_payments.length}
              </Typography>
              <Typography>
                Unmatched compensation payouts: {reconciliation.unmatched_compensation_payouts.length}
              </Typography>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Select an import to see summary.
            </Typography>
          )}
        </Box>
      </Box>

      <Typography variant="h6" sx={{ mb: 1 }}>
        Statement rows
      </Typography>
      {detailLoading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={18} /> <Typography>Loading…</Typography>
        </Box>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Description</TableCell>
              <TableCell align="right">Amount</TableCell>
              <TableCell>Match</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(importDetail?.rows.items || []).map((r) => {
              const m = r.transaction.match
              return (
                <TableRow key={r.id} hover>
                  <TableCell>{r.transaction.value_date}</TableCell>
                  <TableCell>{r.transaction.txn_type || '—'}</TableCell>
                  <TableCell sx={{ maxWidth: 640, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {r.transaction.description}
                  </TableCell>
                  <TableCell align="right">{r.transaction.amount}</TableCell>
                  <TableCell>
                    {m ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        {m.entity_type === 'procurement_payment' ? (
                          <Button
                            size="small"
                            component={RouterLink}
                            to={`/procurement/payments/${m.entity_id}`}
                          >
                            {m.entity_number}
                          </Button>
                        ) : (
                          <Button
                            size="small"
                            component={RouterLink}
                            to={`/compensations/payouts/${m.entity_id}`}
                          >
                            {m.entity_number}
                          </Button>
                        )}
                        {m.proof_attachment_id ? (
                          <Button
                            size="small"
                            component="a"
                            href={`/attachment/${m.proof_attachment_id}/download`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Proof
                          </Button>
                        ) : null}
                        <Button
                          size="small"
                          color="warning"
                          onClick={() => unmatchTransaction(r.transaction.id)}
                          disabled={unmatchMutation.loading}
                        >
                          Unmatch
                        </Button>
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography variant="body2" color="text.secondary">
                          Unmatched
                        </Typography>
                        <Button size="small" onClick={() => openManualMatch(r.transaction.id)}>
                          Manual match
                        </Button>
                      </Box>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
            {!importDetail?.rows.items.length ? (
              <TableRow>
                <TableCell colSpan={5}>
                  {selectedImportId ? 'No rows found for this filter.' : 'Select an import.'}
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      )}

      <Box sx={{ mt: 3, display: 'grid', gap: 3 }}>
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Unmatched procurement payments (company paid)
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Number</TableCell>
                <TableCell>Payee</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(reconciliation?.unmatched_procurement_payments || []).slice(0, 50).map((p) => (
                <TableRow key={p.id} hover>
                  <TableCell>{p.payment_date}</TableCell>
                  <TableCell>{p.payment_number}</TableCell>
                  <TableCell>{p.payee_name || '—'}</TableCell>
                  <TableCell align="right">{p.amount}</TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, flexWrap: 'wrap' }}>
                      <Button
                        size="small"
                        onClick={() => openManualMatchForEntity('procurement_payment', p.id)}
                      >
                        Manual match
                      </Button>
                      <Button size="small" component={RouterLink} to={`/procurement/payments/${p.id}`}>
                        Open
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
              {!reconciliation?.unmatched_procurement_payments?.length ? (
                <TableRow>
                  <TableCell colSpan={5}>No unmatched payments</TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </Box>

        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Unmatched compensation payouts
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Number</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(reconciliation?.unmatched_compensation_payouts || []).slice(0, 50).map((p) => (
                <TableRow key={p.id} hover>
                  <TableCell>{p.payout_date}</TableCell>
                  <TableCell>{p.payout_number}</TableCell>
                  <TableCell align="right">{p.amount}</TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, flexWrap: 'wrap' }}>
                      <Button
                        size="small"
                        onClick={() => openManualMatchForEntity('compensation_payout', p.id)}
                      >
                        Manual match
                      </Button>
                      <Button size="small" component={RouterLink} to={`/compensations/payouts/${p.id}`}>
                        Open
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
              {!reconciliation?.unmatched_compensation_payouts?.length ? (
                <TableRow>
                  <TableCell colSpan={4}>No unmatched payouts</TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </Box>
      </Box>

      <Dialog open={manualMatchTxnId !== null} onClose={closeManualMatch} maxWidth="sm" fullWidth>
        <DialogTitle>Manual match</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Pick an unmatched internal document by amount (± 1.00). This is a read-write operation (Admin/SuperAdmin).
          </Typography>
          <Box sx={{ display: 'grid', gap: 2 }}>
            <Box>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                Entity type
              </Typography>
              <Select
                size="small"
                fullWidth
                value={manualMatchType}
                onChange={(e) => {
                  const t = e.target.value as MatchedEntityType
                  setManualMatchType(t)
                  setManualMatchEntityId('')
                }}
              >
                <MenuItem value="procurement_payment">Procurement payment (company paid)</MenuItem>
                <MenuItem value="compensation_payout">Compensation payout</MenuItem>
              </Select>
            </Box>
            <Box>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                Entity
              </Typography>
              <Select
                size="small"
                fullWidth
                displayEmpty
                value={manualMatchEntityId}
                onChange={(e) => setManualMatchEntityId(e.target.value as number)}
              >
                <MenuItem value="">
                  <em>Select…</em>
                </MenuItem>
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
                  <MenuItem key={opt.id} value={opt.id}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              <Typography variant="caption" color="text.secondary">
                Candidates are filtered from “unmatched” lists by amount (± 1.00).
              </Typography>
            </Box>
          </Box>
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
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Pick an unmatched bank transaction to match to this document (amount tolerance: ± 1.00).
          </Typography>
          <Box sx={{ display: 'grid', gap: 2 }}>
            <Box>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                Bank transaction
              </Typography>
              <Select
                size="small"
                fullWidth
                displayEmpty
                value={manualMatchTxnForEntityId}
                onChange={(e) => setManualMatchTxnForEntityId(e.target.value as number)}
              >
                <MenuItem value="">
                  <em>Select…</em>
                </MenuItem>
                {txnCandidatesForEntity.map((opt) => (
                  <MenuItem key={opt.id} value={opt.id}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              <Typography variant="caption" color="text.secondary">
                Candidates are filtered to unmatched statement rows by amount (± 1.00).
              </Typography>
            </Box>
          </Box>
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
    </Box>
  )
}
