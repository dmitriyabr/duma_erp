import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Link,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { formatDate, formatMoney } from '../../utils/format'

interface AgedRow {
  student_id: number
  student_name: string
  total: string
  current: string
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
  last_payment_date: string | null
}

interface Summary {
  total: string
  current: string
  bucket_31_60: string
  bucket_61_90: string
  bucket_90_plus: string
}

interface AgedReceivablesData {
  as_at_date: string
  rows: AgedRow[]
  summary: Summary
}

type SortKey = 'student_name' | 'total' | 'current' | 'bucket_31_60' | 'bucket_61_90' | 'bucket_90_plus' | 'last_payment_date'

function parseNum(s: string): number {
  const n = parseFloat(String(s).replace(/,/g, ''))
  return Number.isNaN(n) ? 0 : n
}

export const AgedReceivablesPage = () => {
  const [searchParams] = useSearchParams()
  const asAtParam = searchParams.get('as_at_date') ?? undefined
  const [data, setData] = useState<AgedReceivablesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [orderBy, setOrderBy] = useState<SortKey>('total')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')

  const sortedRows = useMemo(() => {
    if (!data?.rows.length) return []
    const rows = [...data.rows]
    rows.sort((a, b) => {
      let cmp = 0
      if (orderBy === 'student_name') {
        cmp = (a.student_name ?? '').localeCompare(b.student_name ?? '')
      } else if (orderBy === 'last_payment_date') {
        const da = a.last_payment_date ?? ''
        const db = b.last_payment_date ?? ''
        cmp = da.localeCompare(db)
      } else {
        cmp = parseNum(a[orderBy]) - parseNum(b[orderBy])
      }
      return order === 'asc' ? cmp : -cmp
    })
    return rows
  }, [data?.rows, orderBy, order])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setForbidden(false)
    const params = asAtParam ? { as_at_date: asAtParam } : {}
    api
      .get<ApiResponse<AgedReceivablesData>>('/reports/aged-receivables', { params })
      .then((res) => {
        if (!cancelled && res.data?.data) setData(res.data.data)
      })
      .catch((err) => {
        if (!cancelled) {
          if (err.response?.status === 403) setForbidden(true)
          else setError(err.response?.data?.message ?? 'Failed to load report')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [asAtParam])

  const handleSort = (key: SortKey) => {
    if (orderBy === key) {
      setOrder(order === 'asc' ? 'desc' : 'asc')
    } else {
      setOrderBy(key)
      setOrder(key === 'student_name' ? 'asc' : 'desc')
    }
  }

  if (forbidden) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Students Debt</Typography>
        <Alert severity="warning">
          You do not have access to reports. This section is available to Admin and SuperAdmin.
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>Students Debt</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Student debts by aging (as at {data ? formatDate(data.as_at_date) : '—'}).
      </Typography>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
      )}

      {!loading && data && (
        <>
          <TableContainer component={Card} sx={{ mb: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sortDirection={orderBy === 'student_name' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'student_name'}
                      direction={orderBy === 'student_name' ? order : 'asc'}
                      onClick={() => handleSort('student_name')}
                    >
                      <strong>Student</strong>
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right" sortDirection={orderBy === 'total' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'total'}
                      direction={orderBy === 'total' ? order : 'desc'}
                      onClick={() => handleSort('total')}
                    >
                      <strong>Total</strong>
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right" sortDirection={orderBy === 'current' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'current'}
                      direction={orderBy === 'current' ? order : 'desc'}
                      onClick={() => handleSort('current')}
                    >
                      <strong>Current (0-30 days)</strong>
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right" sortDirection={orderBy === 'bucket_31_60' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'bucket_31_60'}
                      direction={orderBy === 'bucket_31_60' ? order : 'desc'}
                      onClick={() => handleSort('bucket_31_60')}
                    >
                      <strong>31-60 days</strong>
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right" sortDirection={orderBy === 'bucket_61_90' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'bucket_61_90'}
                      direction={orderBy === 'bucket_61_90' ? order : 'desc'}
                      onClick={() => handleSort('bucket_61_90')}
                    >
                      <strong>61-90 days</strong>
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right" sortDirection={orderBy === 'bucket_90_plus' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'bucket_90_plus'}
                      direction={orderBy === 'bucket_90_plus' ? order : 'desc'}
                      onClick={() => handleSort('bucket_90_plus')}
                    >
                      <strong>90+ days</strong>
                    </TableSortLabel>
                  </TableCell>
                  <TableCell sortDirection={orderBy === 'last_payment_date' ? order : false}>
                    <TableSortLabel
                      active={orderBy === 'last_payment_date'}
                      direction={orderBy === 'last_payment_date' ? order : 'desc'}
                      onClick={() => handleSort('last_payment_date')}
                    >
                      <strong>Last Payment</strong>
                    </TableSortLabel>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedRows.map((row) => (
                  <TableRow key={row.student_id}>
                    <TableCell>
                      <Link
                        component={RouterLink}
                        to={`/students/${row.student_id}`}
                        sx={{ color: 'inherit', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                      >
                        {row.student_name}
                      </Link>
                    </TableCell>
                    <TableCell align="right">{formatMoney(row.total)}</TableCell>
                    <TableCell align="right">{formatMoney(row.current)}</TableCell>
                    <TableCell align="right">{formatMoney(row.bucket_31_60)}</TableCell>
                    <TableCell align="right">{formatMoney(row.bucket_61_90)}</TableCell>
                    <TableCell align="right">{formatMoney(row.bucket_90_plus)}</TableCell>
                    <TableCell>{row.last_payment_date ? formatDate(row.last_payment_date) : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Summary</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Typography variant="body2"><strong>Total:</strong> {formatMoney(data.summary.total)}</Typography>
                <Typography variant="body2"><strong>Current (0-30 days):</strong> {formatMoney(data.summary.current)}</Typography>
                <Typography variant="body2"><strong>31-60 days:</strong> {formatMoney(data.summary.bucket_31_60)}</Typography>
                <Typography variant="body2"><strong>61-90 days:</strong> {formatMoney(data.summary.bucket_61_90)}</Typography>
                <Typography variant="body2" color="error.main"><strong>90+ days:</strong> {formatMoney(data.summary.bucket_90_plus)}</Typography>
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      {!loading && !data && !error && (
        <Typography color="text.secondary">No data.</Typography>
      )}
    </Box>
  )
}
