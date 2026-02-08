import {
  Alert,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'

function getDefaultDateRange(): { start: string; end: string } {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

type MatchedEntityType = 'procurement_payment' | 'compensation_payout'

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
  value_date: string
  description: string
  amount: string
  account_owner_reference: string | null
  txn_type: string | null
  match: BankTransactionMatchInfo | null
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

export const BankStatementsPage = () => {
  const [dates, setDates] = useState(getDefaultDateRange)
  const [matched, setMatched] = useState<'all' | 'matched' | 'unmatched'>('all')
  const [entityType, setEntityType] = useState<'all' | MatchedEntityType>('all')
  const [txnType, setTxnType] = useState<'all' | string>('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const txnTypesUrl = useMemo(() => {
    const params = new URLSearchParams()
    if (dates.start) params.set('date_from', dates.start)
    if (dates.end) params.set('date_to', dates.end)
    return `/bank-statements/txn-types?${params.toString()}`
  }, [dates.start, dates.end])

  const { data: txnTypes } = useApi<string[]>(txnTypesUrl)

  const url = useMemo(() => {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('limit', '100')
    if (dates.start) params.set('date_from', dates.start)
    if (dates.end) params.set('date_to', dates.end)
    if (txnType !== 'all' && txnType.trim()) params.set('txn_type', txnType.trim())
    if (matched === 'matched') params.set('matched', 'true')
    if (matched === 'unmatched') params.set('matched', 'false')
    if (entityType !== 'all') params.set('entity_type', entityType)
    if (search.trim()) params.set('search', search.trim())
    return `/bank-statements/transactions?${params.toString()}`
  }, [dates.start, dates.end, txnType, matched, entityType, search, page])

  const { data, loading, error, refetch } =
    useApi<PaginatedResponse<BankTransactionResponse>>(url)

  const onApplyFilters = () => {
    setPage(1)
    void refetch()
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Bank transfers
      </Typography>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
        <TextField
          label="Start date"
          type="date"
          value={dates.start}
          onChange={(e) => setDates((p) => ({ ...p, start: e.target.value }))}
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 180 }}
        />
        <TextField
          label="End date"
          type="date"
          value={dates.end}
          onChange={(e) => setDates((p) => ({ ...p, end: e.target.value }))}
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 180 }}
        />
        <Select
          size="small"
          value={matched}
          onChange={(e) => setMatched(e.target.value as typeof matched)}
          sx={{ width: 180 }}
        >
          <MenuItem value="all">All</MenuItem>
          <MenuItem value="matched">Matched</MenuItem>
          <MenuItem value="unmatched">Unmatched</MenuItem>
        </Select>
        <Select
          size="small"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value as typeof entityType)}
          sx={{ width: 220 }}
        >
          <MenuItem value="all">All entity types</MenuItem>
          <MenuItem value="procurement_payment">Procurement payments</MenuItem>
          <MenuItem value="compensation_payout">Compensation payouts</MenuItem>
        </Select>
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
        <TextField
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="small"
          sx={{ minWidth: 240 }}
        />
        <Button variant="contained" onClick={onApplyFilters} disabled={loading}>
          Apply
        </Button>
        <Button variant="outlined" onClick={() => void refetch()} disabled={loading}>
          Refresh
        </Button>
      </Box>

      {loading ? (
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
              <TableCell>Matched document</TableCell>
              <TableCell>Proof</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(data?.items || []).map((t) => {
              const m = t.match
              const amountAbs = (() => {
                const n = Number.parseFloat(String(t.amount).replace(/,/g, ''))
                return Number.isNaN(n) ? t.amount : Math.abs(n).toFixed(2)
              })()
              return (
                <TableRow key={t.id} hover>
                  <TableCell>{t.value_date}</TableCell>
                  <TableCell>{t.txn_type || '—'}</TableCell>
                  <TableCell sx={{ maxWidth: 720, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {t.description}
                  </TableCell>
                  <TableCell align="right">{amountAbs}</TableCell>
                  <TableCell>
                    {m ? (
                      m.entity_type === 'procurement_payment' ? (
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
                      )
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {m?.proof_attachment_id ? (
                      <Button
                        size="small"
                        component="a"
                        href={`/attachment/${m.proof_attachment_id}/download`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Download
                      </Button>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
            {!data?.items.length ? (
              <TableRow>
                <TableCell colSpan={6}>No bank transfers found.</TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      )}
    </Box>
  )
}
