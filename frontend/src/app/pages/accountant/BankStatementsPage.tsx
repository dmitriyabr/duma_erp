import { useMemo, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import {
  Alert,
  Button,
  Input,
  Select,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Typography,
  Spinner,
} from '../../components/ui'

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
    <div>
      <Typography variant="h4" className="font-bold mb-4">
        Bank transfers
      </Typography>

      {error ? (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      ) : null}

      <div className="flex gap-4 items-center flex-wrap mb-4">
        <Input
          label="Start date"
          type="date"
          value={dates.start}
          onChange={(e) => setDates((p) => ({ ...p, start: e.target.value }))}
          className="w-44"
        />
        <Input
          label="End date"
          type="date"
          value={dates.end}
          onChange={(e) => setDates((p) => ({ ...p, end: e.target.value }))}
          className="w-44"
        />
        <Select
          value={matched}
          onChange={(e) => setMatched(e.target.value as typeof matched)}
          className="w-44"
        >
          <option value="all">All</option>
          <option value="matched">Matched</option>
          <option value="unmatched">Unmatched</option>
        </Select>
        <Select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value as typeof entityType)}
          className="w-56"
        >
          <option value="all">All entity types</option>
          <option value="procurement_payment">Procurement payments</option>
          <option value="compensation_payout">Compensation payouts</option>
        </Select>
        <Select
          value={txnType}
          onChange={(e) => setTxnType(e.target.value as typeof txnType)}
          className="w-40"
        >
          <option value="all">All types</option>
          {(txnTypes || []).map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
        <Input
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-w-[240px]"
        />
        <Button variant="contained" onClick={onApplyFilters} disabled={loading}>
          Apply
        </Button>
        <Button variant="outlined" onClick={() => void refetch()} disabled={loading}>
          Refresh
        </Button>
      </div>

      {loading ? (
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
              <TableHeaderCell>Matched document</TableHeaderCell>
              <TableHeaderCell>Proof</TableHeaderCell>
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
                <TableRow key={t.id}>
                  <TableCell>{t.value_date}</TableCell>
                  <TableCell>{t.txn_type || '—'}</TableCell>
                  <TableCell className="max-w-[720px] truncate">
                    {t.description}
                  </TableCell>
                  <TableCell align="right">{amountAbs}</TableCell>
                  <TableCell>
                    {m ? (
                      m.entity_type === 'procurement_payment' ? (
                        <RouterLink to={`/procurement/payments/${m.entity_id}`}>
                          <Button size="small">
                            {m.entity_number}
                          </Button>
                        </RouterLink>
                      ) : (
                        <RouterLink to={`/compensations/payouts/${m.entity_id}`}>
                          <Button size="small">
                            {m.entity_number}
                          </Button>
                        </RouterLink>
                      )
                    ) : (
                      <Typography variant="body2" color="secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {m?.proof_attachment_id ? (
                      <a
                        href={`/attachment/${m.proof_attachment_id}/download`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Button size="small">
                          Download
                        </Button>
                      </a>
                    ) : (
                      <Typography variant="body2" color="secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
            {!data?.items.length ? (
              <TableRow>
                <td colSpan={6} className="px-4 py-3">
                  No bank transfers found.
                </td>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
