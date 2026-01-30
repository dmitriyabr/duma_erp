import {
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { api } from '../../../services/api'
import { useApiMutation } from '../../../hooks/useApi'
import { formatDateTime, formatMoney } from '../../../utils/format'
import type { ApiResponse, StatementResponse } from '../types'
import { getMonthToDateRange, parseNumber } from '../types'

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
    <Box>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField
          label="From"
          type="date"
          value={statementForm.date_from}
          onChange={(event) => setStatementForm({ ...statementForm, date_from: event.target.value })}
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          label="To"
          type="date"
          value={statementForm.date_to}
          onChange={(event) => setStatementForm({ ...statementForm, date_to: event.target.value })}
          InputLabelProps={{ shrink: true }}
        />
        <Button variant="contained" onClick={fetchStatement} disabled={loading}>
          Load statement
        </Button>
      </Box>
      {statement ? (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2">
            Opening balance: {formatMoney(parseNumber(statement.opening_balance))}
          </Typography>
          <Typography variant="body2">
            Closing balance: {formatMoney(parseNumber(statement.closing_balance))}
          </Typography>
        </Box>
      ) : null}
      {statement ? (
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Reference</TableCell>
              <TableCell>Credit</TableCell>
              <TableCell>Debit</TableCell>
              <TableCell>Balance</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {statement.entries.map((entry, idx) => (
              <TableRow key={`${entry.reference ?? 'entry'}-${idx}`}>
                <TableCell>{formatDateTime(entry.date)}</TableCell>
                <TableCell>{entry.description}</TableCell>
                <TableCell>{entry.reference ?? '—'}</TableCell>
                <TableCell>{entry.credit ? formatMoney(parseNumber(entry.credit)) : '—'}</TableCell>
                <TableCell>{entry.debit ? formatMoney(parseNumber(entry.debit)) : '—'}</TableCell>
                <TableCell>{formatMoney(parseNumber(entry.balance))}</TableCell>
              </TableRow>
            ))}
            {!statement.entries.length ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No entries
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      ) : null}
    </Box>
  )
}
