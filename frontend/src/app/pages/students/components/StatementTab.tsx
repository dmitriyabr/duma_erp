import { useEffect, useState } from 'react'
import { api } from '../../../services/api'
import { useApiMutation } from '../../../hooks/useApi'
import { formatDateTime, formatMoney } from '../../../utils/format'
import type { ApiResponse, StatementResponse } from '../types'
import { getMonthToDateRange, parseNumber } from '../types'
import { Typography } from '../../../components/ui/Typography'
import { Button } from '../../../components/ui/Button'
import { Input } from '../../../components/ui/Input'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../../components/ui/Table'
import { Spinner } from '../../../components/ui/Spinner'

interface StatementTabProps {
  studentId: number
  onError: (message: string) => void
}

export const StatementTab = ({ studentId, onError }: StatementTabProps) => {
  const { execute: loadStatement, loading, error } = useApiMutation<StatementResponse>()
  const [statementForm, setStatementForm] = useState({ date_from: '', date_to: '' })
  const [statement, setStatement] = useState<StatementResponse | null>(null)
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (!initialized) {
      setStatementForm(getMonthToDateRange())
      setInitialized(true)
    }
  }, [initialized])

  const fetchStatement = async () => {
    if (!statementForm.date_from || !statementForm.date_to) return
    const result = await loadStatement(() =>
      api.get<ApiResponse<StatementResponse>>(
        `/payments/students/${studentId}/statement`,
        { params: { date_from: statementForm.date_from, date_to: statementForm.date_to } }
      )
    )

    if (result) {
      setStatement(result)
    } else if (error) {
      onError('Failed to load statement.')
    }
  }

  return (
    <div>
      <div className="flex gap-4 flex-wrap mb-4">
        <Input
          label="From"
          type="date"
          value={statementForm.date_from}
          onChange={(e) => setStatementForm({ ...statementForm, date_from: e.target.value })}
          className="w-48"
        />
        <Input
          label="To"
          type="date"
          value={statementForm.date_to}
          onChange={(e) => setStatementForm({ ...statementForm, date_to: e.target.value })}
          className="w-48"
        />
        <Button variant="contained" onClick={fetchStatement} disabled={loading}>
          {loading ? <Spinner size="small" /> : 'Load statement'}
        </Button>
      </div>
      {statement && (
        <div className="mb-4">
          <Typography variant="body2">
            Opening balance: {formatMoney(parseNumber(statement.opening_balance))}
          </Typography>
          <Typography variant="body2" className="mt-1">
            Closing balance: {formatMoney(parseNumber(statement.closing_balance))}
          </Typography>
        </div>
      )}
      {statement && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Date</TableHeaderCell>
                <TableHeaderCell>Description</TableHeaderCell>
                <TableHeaderCell>Reference</TableHeaderCell>
                <TableHeaderCell align="right">Credit</TableHeaderCell>
                <TableHeaderCell align="right">Debit</TableHeaderCell>
                <TableHeaderCell align="right">Balance</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {statement.entries.map((entry, idx) => (
                <TableRow key={`${entry.reference ?? 'entry'}-${idx}`}>
                  <TableCell>{formatDateTime(entry.date)}</TableCell>
                  <TableCell>{entry.description}</TableCell>
                  <TableCell>{entry.reference ?? '—'}</TableCell>
                  <TableCell align="right">
                    {entry.credit ? formatMoney(parseNumber(entry.credit)) : '—'}
                  </TableCell>
                  <TableCell align="right">
                    {entry.debit ? formatMoney(parseNumber(entry.debit)) : '—'}
                  </TableCell>
                  <TableCell align="right">{formatMoney(parseNumber(entry.balance))}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
