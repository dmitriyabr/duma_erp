import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi } from '../../hooks/useApi'
import { isAccountant } from '../../utils/permissions'
import { formatDate } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

interface TermRow {
  id: number
  year: number
  term_number: number
  display_name: string
  status: 'Draft' | 'Active' | 'Closed'
  start_date?: string | null
  end_date?: string | null
}

const statusColor = (status: TermRow['status']) => {
  if (status === 'Active') return 'success'
  if (status === 'Closed') return 'default'
  return 'warning'
}

export const TermsListPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const { data: terms, loading, error } = useApi<TermRow[]>('/terms')

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <Typography variant="h4">
          Terms
        </Typography>
        {!readOnly && (
          <Button variant="contained" onClick={() => navigate('/billing/terms/new')}>
            New term
          </Button>
        )}
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Dates</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(terms || []).map((term) => (
              <TableRow key={term.id}>
                <TableCell>{term.display_name}</TableCell>
                <TableCell>
                  <Chip size="small" label={term.status} color={statusColor(term.status)} />
                </TableCell>
                <TableCell>
                  {formatDate(term.start_date)} → {formatDate(term.end_date)}
                </TableCell>
                <TableCell align="right">
                  <div className="flex gap-2 justify-end">
                    <Button size="small" variant="outlined" onClick={() => navigate(`/billing/terms/${term.id}`)}>
                      View
                    </Button>
                    {!readOnly && (
                      <Button size="small" variant="outlined" onClick={() => navigate(`/billing/terms/${term.id}/edit`)}>
                        Edit
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={4} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!(terms || []).length && !loading && (
              <TableRow>
                <td colSpan={4} className="px-4 py-8 text-center">
                  <Typography color="secondary">No terms found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
