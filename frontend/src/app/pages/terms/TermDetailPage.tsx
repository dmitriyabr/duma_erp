import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { isAccountant } from '../../utils/permissions'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api, unwrapResponse } from '../../services/api'
import { formatDate, formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Input } from '../../components/ui/Input'
import { Menu, MenuItem } from '../../components/ui/Menu'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

interface PriceSettingRow {
  grade: string
  school_fee_amount: number
}

interface TransportPricingRow {
  zone_id: number
  zone_name: string
  zone_code: string
  transport_fee_amount: number
}

interface TermDetail {
  id: number
  year: number
  term_number: number
  display_name: string
  status: 'Draft' | 'Active' | 'Closed'
  start_date?: string | null
  end_date?: string | null
  price_settings: PriceSettingRow[]
  transport_pricings: TransportPricingRow[]
}

interface GenerationResult {
  school_fee_invoices_created: number
  transport_invoices_created: number
  students_skipped: number
  total_students_processed: number
}

const statusColor = (status: TermDetail['status']) => {
  if (status === 'Active') return 'success'
  if (status === 'Closed') return 'default'
  return 'warning'
}

export const TermDetailPage = () => {
  const { termId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const resolvedId = termId ? Number(termId) : null
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null)
  const [resultDialogOpen, setResultDialogOpen] = useState(false)
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [studentDialogOpen, setStudentDialogOpen] = useState(false)
  const [studentId, setStudentId] = useState('')
  const [studentIdError, setStudentIdError] = useState<string | null>(null)

  const termApi = useApi<TermDetail>(
    resolvedId != null && !Number.isNaN(resolvedId) ? `/terms/${resolvedId}` : null
  )
  const { grades } = useReferencedData()
  const activateMutation = useApiMutation<unknown>()
  const closeMutation = useApiMutation<unknown>()
  const generateAllMutation = useApiMutation<GenerationResult>()
  const generateSingleMutation = useApiMutation<GenerationResult>()

  const term = useMemo(() => {
    const data = termApi.data
    if (!data) return null
    return {
      ...data,
      price_settings: data.price_settings.map((e) => ({
        ...e,
        school_fee_amount: Number(e.school_fee_amount),
      })),
      transport_pricings: data.transport_pricings.map((e) => ({
        ...e,
        transport_fee_amount: Number(e.transport_fee_amount),
      })),
    }
  }, [termApi.data])

  const gradeNameMap = useMemo(() => new Map(grades.map((g) => [g.code, g.name])), [grades])
  const error =
    termApi.error ??
    activateMutation.error ??
    closeMutation.error ??
    generateAllMutation.error ??
    generateSingleMutation.error
  const loading =
    activateMutation.loading ||
    closeMutation.loading ||
    generateAllMutation.loading ||
    generateSingleMutation.loading

  const handleActivate = async () => {
    if (!resolvedId) return
    const ok = await activateMutation.execute(() =>
      api.post(`/terms/${resolvedId}/activate`).then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) termApi.refetch()
  }

  const handleClose = async () => {
    if (!resolvedId) return
    const ok = await closeMutation.execute(() =>
      api.post(`/terms/${resolvedId}/close`).then((r) => ({ data: { data: unwrapResponse(r) } }))
    )
    if (ok != null) termApi.refetch()
  }

  const openMenu = (event: React.MouseEvent<HTMLButtonElement>) => {
    setMenuAnchor(event.currentTarget)
  }

  const closeMenu = () => {
    setMenuAnchor(null)
  }

  const showResult = (data: GenerationResult) => {
    setResult(data)
    setResultDialogOpen(true)
  }

  const generateAll = async () => {
    if (!resolvedId) return
    const data = await generateAllMutation.execute(() =>
      api
        .post('/invoices/generate-term-invoices', { term_id: resolvedId })
        .then((r) => ({ data: { data: unwrapResponse<GenerationResult>(r) } }))
    )
    if (data != null) {
      showResult(data)
      closeMenu()
    }
  }

  const generateSingle = async () => {
    if (!resolvedId) return
    setStudentIdError(null)
    const studentIdValue = Number(studentId)
    if (!studentIdValue) {
      setStudentIdError('Enter student ID.')
      return
    }
    const data = await generateSingleMutation.execute(() =>
      api
        .post('/invoices/generate-term-invoices/student', {
          term_id: resolvedId,
          student_id: studentIdValue,
        })
        .then((r) => ({ data: { data: unwrapResponse<GenerationResult>(r) } }))
    )
    if (data != null) {
      showResult(data)
      setStudentDialogOpen(false)
      setStudentId('')
    }
  }

  if (termApi.loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!term) {
    return (
      <div>
        {error && <Alert severity="error">{error}</Alert>}
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4 flex-wrap gap-4">
        <div>
          <Typography variant="h4">
            {term.display_name}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {formatDate(term.start_date)} → {formatDate(term.end_date)}
          </Typography>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <Chip label={term.status} color={statusColor(term.status)} />
          {!readOnly && (
            <>
              <Button variant="outlined" onClick={() => navigate(`/billing/terms/${term.id}/edit`)}>
                Edit
              </Button>
              {term.status !== 'Active' && term.status !== 'Closed' && (
                <Button variant="contained" onClick={handleActivate} disabled={loading}>
                  {loading ? <Spinner size="small" /> : 'Activate'}
                </Button>
              )}
              {term.status === 'Active' && (
                <Button variant="contained" color="warning" onClick={handleClose} disabled={loading}>
                  {loading ? <Spinner size="small" /> : 'Close'}
                </Button>
              )}
              <Button variant="outlined" onClick={openMenu}>
                Generate invoices
              </Button>
            </>
          )}
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="mt-6">
        <Typography variant="h6" className="mb-4">
          School fees by grade
        </Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Grade</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {term.price_settings.map((entry) => (
                <TableRow key={entry.grade}>
                  <TableCell>{gradeNameMap.get(entry.grade) ?? entry.grade}</TableCell>
                  <TableCell align="right">{formatMoney(entry.school_fee_amount)}</TableCell>
                </TableRow>
              ))}
              {!term.price_settings.length && (
                <TableRow>
                  <td colSpan={2} className="px-4 py-8 text-center">
                    <Typography color="secondary">No pricing data</Typography>
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="mt-6">
        <Typography variant="h6" className="mb-4">
          Transport fees by zone
        </Typography>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Zone</TableHeaderCell>
                <TableHeaderCell>Code</TableHeaderCell>
                <TableHeaderCell align="right">Amount</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {term.transport_pricings.map((entry) => (
                <TableRow key={entry.zone_id}>
                  <TableCell>{entry.zone_name}</TableCell>
                  <TableCell>{entry.zone_code}</TableCell>
                  <TableCell align="right">{formatMoney(entry.transport_fee_amount)}</TableCell>
                </TableRow>
              ))}
              {!term.transport_pricings.length && (
                <TableRow>
                  <td colSpan={3} className="px-4 py-8 text-center">
                    <Typography color="secondary">No transport pricing data</Typography>
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
        <MenuItem onClick={generateAll}>All students</MenuItem>
        <MenuItem
          onClick={() => {
            setStudentDialogOpen(true)
            closeMenu()
          }}
        >
          Single student
        </MenuItem>
      </Menu>

      <Dialog
        open={studentDialogOpen}
        onClose={() => {
          setStudentDialogOpen(false)
          setStudentIdError(null)
        }}
        maxWidth="sm"
      >
        <DialogCloseButton onClose={() => {
          setStudentDialogOpen(false)
          setStudentIdError(null)
        }} />
        <DialogTitle>Generate invoices for student</DialogTitle>
        <DialogContent>
          <div className="space-y-4 mt-4">
            {studentIdError && (
              <Alert severity="error" onClose={() => setStudentIdError(null)}>
                {studentIdError}
              </Alert>
            )}
            <Input
              label="Student ID"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              type="number"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setStudentDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={generateSingle} disabled={loading}>
            {loading ? <Spinner size="small" /> : 'Generate'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={resultDialogOpen} onClose={() => setResultDialogOpen(false)} maxWidth="sm">
        <DialogCloseButton onClose={() => setResultDialogOpen(false)} />
        <DialogTitle>Invoice generation result</DialogTitle>
        <DialogContent>
          <div className="space-y-2 mt-4">
            <Typography>School fee invoices: {result?.school_fee_invoices_created ?? 0}</Typography>
            <Typography>Transport invoices: {result?.transport_invoices_created ?? 0}</Typography>
            <Typography>Students skipped: {result?.students_skipped ?? 0}</Typography>
            <Typography>Total processed: {result?.total_students_processed ?? 0}</Typography>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setResultDialogOpen(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
