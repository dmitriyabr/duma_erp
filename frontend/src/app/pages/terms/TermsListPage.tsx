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
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
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
  const [terms, setTerms] = useState<TermRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTerms = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<TermRow[]>>('/terms')
      setTerms(response.data.data)
    } catch {
      setError('Failed to load terms.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTerms()
  }, [])

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
          {terms.map((term) => (
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
          {!terms.length && !loading ? (
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
