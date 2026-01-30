import {
  Alert,
  Box,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

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
  const { data: terms, loading, error } = useApi<TermRow[]>('/terms')

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Terms
        </Typography>
        <Button variant="contained" onClick={() => navigate('/billing/terms/new')}>
          New term
        </Button>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Dates</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => navigate(`/billing/terms/${term.id}`)}>
                  View
                </Button>
                <Button size="small" onClick={() => navigate(`/billing/terms/${term.id}/edit`)}>
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!(terms || []).length && !loading ? (
            <TableRow>
              <TableCell colSpan={4} align="center">
                No terms found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </Box>
  )
}
