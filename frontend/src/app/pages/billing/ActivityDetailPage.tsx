import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api, unwrapResponse } from '../../services/api'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import type { PaginatedResponse } from '../../types/api'
import { formatDate, formatMoney } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Chip } from '../../components/ui/Chip'
import { Input } from '../../components/ui/Input'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { Autocomplete } from '../../components/ui/Autocomplete'
import { canManageActivities } from '../../utils/permissions'

interface StudentOption {
  id: number
  full_name: string
  student_number: string
  grade_name?: string | null
}

interface ActivityParticipant {
  id: number
  student_id: number
  student_name: string
  student_number: string
  grade_name?: string | null
  status: string
  selected_amount: string
  invoice_id?: number | null
  invoice_number?: string | null
  invoice_status?: string | null
  invoice_total?: string | null
  invoice_amount_due?: string | null
  excluded_reason?: string | null
  added_manually: boolean
}

interface ActivityDetail {
  id: number
  activity_number: string
  code?: string | null
  name: string
  description?: string | null
  activity_date?: string | null
  due_date?: string | null
  term_name?: string | null
  status: string
  audience_type: string
  amount: string
  requires_full_payment: boolean
  participants_total: number
  planned_count: number
  invoiced_count: number
  paid_count: number
  cancelled_count: number
  skipped_count: number
  total_invoiced_amount: string
  total_outstanding_amount: string
  notes?: string | null
  participants: ActivityParticipant[]
}

interface GenerationResult {
  activity_id: number
  invoices_created: number
  participants_skipped: number
  affected_student_ids: number[]
}

const audienceLabels: Record<string, string> = {
  all_active: 'All active',
  grades: 'Selected grades',
  manual: 'Manual',
}

const chipColorByStatus: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error'> = {
  draft: 'default',
  published: 'primary',
  closed: 'success',
  cancelled: 'error',
  planned: 'warning',
  invoiced: 'primary',
  paid: 'success',
}

export const ActivityDetailPage = () => {
  const { activityId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = canManageActivities(user)
  const resolvedId = activityId ? Number(activityId) : null
  const [search, setSearch] = useState('')
  const [resultMessage, setResultMessage] = useState<string | null>(null)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [excludeDialog, setExcludeDialog] = useState<{ participant: ActivityParticipant | null; reason: string }>({
    participant: null,
    reason: '',
  })
  const [studentSearch, setStudentSearch] = useState('')
  const [selectedStudent, setSelectedStudent] = useState<StudentOption | null>(null)
  const [selectedAmount, setSelectedAmount] = useState('')
  const debouncedStudentSearch = useDebouncedValue(studentSearch, 250)

  const detailApi = useApi<ActivityDetail>(resolvedId ? `/activities/${resolvedId}` : null, {}, [resolvedId])
  const generateMutation = useApiMutation<GenerationResult>()
  const addParticipantMutation = useApiMutation<ActivityDetail>()
  const excludeParticipantMutation = useApiMutation<ActivityDetail>()

  const studentsUrl = useMemo(() => {
    if (!addDialogOpen) return null
    const params = new URLSearchParams()
    params.append('status', 'active')
    params.append('page', '1')
    params.append('limit', '20')
    if (debouncedStudentSearch.trim()) params.append('search', debouncedStudentSearch.trim())
    return `/students?${params.toString()}`
  }, [addDialogOpen, debouncedStudentSearch])
  const studentsApi = useApi<PaginatedResponse<StudentOption>>(studentsUrl)

  const activity = detailApi.data
  const filteredParticipants = useMemo(() => {
    const participants = activity?.participants ?? []
    const needle = search.trim().toLowerCase()
    if (!needle) return participants
    return participants.filter((participant) =>
      participant.student_name.toLowerCase().includes(needle) ||
      participant.student_number.toLowerCase().includes(needle) ||
      (participant.invoice_number ?? '').toLowerCase().includes(needle)
    )
  }, [activity, search])
  const students = studentsApi.data?.items ?? []
  const canGenerateInvoices =
    canManage &&
    activity != null &&
    activity.status !== 'closed' &&
    activity.status !== 'cancelled' &&
    activity.planned_count > 0

  const runGenerate = async () => {
    if (!resolvedId) return
    generateMutation.reset()
    setResultMessage(null)
    const result = await generateMutation.execute(() =>
      api
        .post(`/activities/${resolvedId}/generate-invoices`)
        .then((response) => ({ data: { data: unwrapResponse<GenerationResult>(response) } }))
    )
    if (result) {
      setResultMessage(
        result.invoices_created > 0
          ? `Generated ${result.invoices_created} invoice${result.invoices_created === 1 ? '' : 's'}.`
          : 'No new invoices were generated.'
      )
      await detailApi.refetch()
    }
  }

  const openAddDialog = () => {
    setSelectedStudent(null)
    setSelectedAmount('')
    setStudentSearch('')
    setAddDialogOpen(true)
    addParticipantMutation.reset()
  }

  const submitAddParticipant = async () => {
    if (!resolvedId || !selectedStudent) return
    const result = await addParticipantMutation.execute(() =>
      api
        .post(`/activities/${resolvedId}/participants`, {
          student_id: selectedStudent.id,
          selected_amount: selectedAmount.trim() ? Number(selectedAmount) : undefined,
        })
        .then((response) => ({ data: { data: unwrapResponse<ActivityDetail>(response) } }))
    )
    if (result) {
      setAddDialogOpen(false)
      setResultMessage(`Added ${selectedStudent.full_name} to the activity.`)
      await detailApi.refetch()
    }
  }

  const openExcludeDialog = (participant: ActivityParticipant) => {
    setExcludeDialog({ participant, reason: '' })
    excludeParticipantMutation.reset()
  }

  const submitExcludeParticipant = async () => {
    if (!resolvedId || !excludeDialog.participant) return
    const participant = excludeDialog.participant
    const result = await excludeParticipantMutation.execute(() =>
      api
        .post(`/activities/${resolvedId}/participants/${participant.id}/exclude`, {
          reason: excludeDialog.reason.trim() || null,
        })
        .then((response) => ({ data: { data: unwrapResponse<ActivityDetail>(response) } }))
    )
    if (result) {
      setExcludeDialog({ participant: null, reason: '' })
      setResultMessage(`Excluded ${participant.student_name} from the activity.`)
      await detailApi.refetch()
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div>
          <Typography variant="h4">{activity?.name ?? 'Activity'}</Typography>
          {activity ? (
            <Typography variant="body2" color="secondary" className="mt-1">
              {activity.activity_number}
              {activity.code ? ` · ${activity.code}` : ''}
              {activity.term_name ? ` · ${activity.term_name}` : ''}
            </Typography>
          ) : null}
        </div>
        {canManage && activity && (
          <div className="flex gap-2 flex-wrap">
            <Button variant="outlined" onClick={() => navigate(`/billing/activities/${activity.id}/edit`)}>
              Edit
            </Button>
            <Button variant="outlined" onClick={openAddDialog} disabled={activity.status === 'closed' || activity.status === 'cancelled'}>
              Add student
            </Button>
            <Button variant="contained" onClick={runGenerate} disabled={!canGenerateInvoices || generateMutation.loading}>
              {generateMutation.loading ? 'Generating...' : 'Generate invoices'}
            </Button>
          </div>
        )}
      </div>

      {(detailApi.error || generateMutation.error || addParticipantMutation.error || excludeParticipantMutation.error) && (
        <Alert severity="error" className="mb-4">
          {detailApi.error || generateMutation.error || addParticipantMutation.error || excludeParticipantMutation.error}
        </Alert>
      )}
      {resultMessage && (
        <Alert severity="success" className="mb-4">
          {resultMessage}
        </Alert>
      )}

      {detailApi.loading && !activity ? (
        <div className="py-12 flex justify-center">
          <Spinner size="medium" />
        </div>
      ) : null}

      {activity && (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 mb-6">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <Typography variant="body2" color="secondary">Status</Typography>
              <div className="mt-2 flex flex-wrap gap-2">
                <Chip label={activity.status} color={chipColorByStatus[activity.status] ?? 'default'} />
                <Chip label={audienceLabels[activity.audience_type] ?? activity.audience_type} />
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <Typography variant="body2" color="secondary">Billing</Typography>
              <Typography className="mt-2">Amount: {formatMoney(Number(activity.amount))}</Typography>
              <Typography color="secondary">
                Requires full payment: {activity.requires_full_payment ? 'Yes' : 'No'}
              </Typography>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <Typography variant="body2" color="secondary">Dates</Typography>
              <Typography className="mt-2">Activity: {activity.activity_date ? formatDate(activity.activity_date) : '—'}</Typography>
              <Typography color="secondary">Due: {activity.due_date ? formatDate(activity.due_date) : '—'}</Typography>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <Typography variant="body2" color="secondary">Totals</Typography>
              <Typography className="mt-2">Invoiced: {formatMoney(Number(activity.total_invoiced_amount))}</Typography>
              <Typography color="secondary">Outstanding: {formatMoney(Number(activity.total_outstanding_amount))}</Typography>
            </div>
          </div>

          {(activity.description || activity.notes) && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 mb-6">
              {activity.description && (
                <div className="mb-3">
                  <Typography variant="body2" color="secondary">Description</Typography>
                  <Typography className="mt-1 whitespace-pre-wrap">{activity.description}</Typography>
                </div>
              )}
              {activity.notes && (
                <div>
                  <Typography variant="body2" color="secondary">Notes</Typography>
                  <Typography className="mt-1 whitespace-pre-wrap">{activity.notes}</Typography>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
            <div className="flex gap-2 flex-wrap">
              <Chip label={`Participants ${activity.participants_total}`} />
              <Chip label={`Planned ${activity.planned_count}`} color="warning" />
              <Chip label={`Invoiced ${activity.invoiced_count}`} color="primary" />
              <Chip label={`Paid ${activity.paid_count}`} color="success" />
              {activity.cancelled_count > 0 && (
                <Chip label={`Cancelled ${activity.cancelled_count}`} color="error" />
              )}
              {activity.skipped_count > 0 && (
                <Chip label={`Skipped ${activity.skipped_count}`} color="default" />
              )}
            </div>
            <div className="min-w-[260px] flex-1 max-w-[360px]">
              <Input
                label="Search participants"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Student or invoice"
              />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Student</TableHeaderCell>
                  <TableHeaderCell>Grade</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Invoice</TableHeaderCell>
                  <TableHeaderCell align="right">Amount</TableHeaderCell>
                  <TableHeaderCell align="right">Due</TableHeaderCell>
                  <TableHeaderCell align="right">Actions</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredParticipants.map((participant) => (
                  <TableRow key={participant.id}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span>{participant.student_name}</span>
                        <span className="text-xs text-slate-500">{participant.student_number}</span>
                      </div>
                    </TableCell>
                    <TableCell>{participant.grade_name ?? '—'}</TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Chip
                          size="small"
                          label={participant.invoice_status === 'paid' ? 'paid' : participant.status}
                          color={chipColorByStatus[participant.invoice_status === 'paid' ? 'paid' : participant.status] ?? 'default'}
                        />
                        {participant.excluded_reason && (
                          <span className="text-xs text-slate-500">{participant.excluded_reason}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {participant.invoice_number ? (
                        <div className="flex flex-col">
                          <span className="font-mono text-xs">{participant.invoice_number}</span>
                          <span className="text-xs text-slate-500">{participant.invoice_status}</span>
                        </div>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {formatMoney(Number(participant.invoice_total ?? participant.selected_amount))}
                    </TableCell>
                    <TableCell align="right">
                      {participant.invoice_amount_due != null
                        ? formatMoney(Number(participant.invoice_amount_due))
                        : '—'}
                    </TableCell>
                    <TableCell align="right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => navigate(`/students/${participant.student_id}?tab=invoices`)}
                        >
                          Student
                        </Button>
                        {canManage &&
                          participant.invoice_id != null &&
                          participant.invoice_status !== 'paid' &&
                          participant.invoice_status !== 'cancelled' &&
                          participant.invoice_status !== 'void' && (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() =>
                                navigate('/payments/new', {
                                  state: {
                                    studentId: participant.student_id,
                                    preferredInvoiceId: participant.invoice_id,
                                    preferredInvoiceNumber: participant.invoice_number,
                                  },
                                })
                              }
                            >
                              Payment
                            </Button>
                          )}
                        {canManage &&
                          participant.status !== 'cancelled' &&
                          participant.invoice_status !== 'paid' && (
                            <Button
                              size="small"
                              variant="outlined"
                              color="error"
                              onClick={() => openExcludeDialog(participant)}
                            >
                              Exclude
                            </Button>
                          )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!filteredParticipants.length && (
                  <TableRow>
                    <td colSpan={7} className="px-4 py-8 text-center">
                      <Typography color="secondary">No participants found</Typography>
                    </td>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogCloseButton onClose={() => setAddDialogOpen(false)} />
        <DialogTitle>Add participant</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Autocomplete
              options={students}
              value={selectedStudent}
              onChange={setSelectedStudent}
              onInputChange={setStudentSearch}
              loading={studentsApi.loading}
              label="Student"
              placeholder="Search active students"
              getOptionLabel={(student) => `${student.full_name} (${student.student_number})`}
              getOptionValue={(student) => student.id}
              renderOption={(student) => (
                <div className="flex flex-col">
                  <span>{student.full_name}</span>
                  <span className="text-xs text-slate-500">
                    {student.student_number}
                    {student.grade_name ? ` · ${student.grade_name}` : ''}
                  </span>
                </div>
              )}
            />
            <Input
              label="Amount override"
              type="number"
              value={selectedAmount}
              onChange={(event) => setSelectedAmount(event.target.value)}
              placeholder={activity?.amount ?? ''}
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAddDialogOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submitAddParticipant} disabled={!selectedStudent || addParticipantMutation.loading}>
            {addParticipantMutation.loading ? 'Saving...' : 'Add student'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={excludeDialog.participant != null}
        onClose={() => setExcludeDialog({ participant: null, reason: '' })}
        maxWidth="sm"
        fullWidth
      >
        <DialogCloseButton onClose={() => setExcludeDialog({ participant: null, reason: '' })} />
        <DialogTitle>Exclude participant</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Typography color="secondary">
              {excludeDialog.participant
                ? `Exclude ${excludeDialog.participant.student_name} from this activity. If an unpaid invoice exists, it will be cancelled.`
                : ''}
            </Typography>
            <Input
              label="Reason"
              value={excludeDialog.reason}
              onChange={(event) =>
                setExcludeDialog((state) => ({ ...state, reason: event.target.value }))
              }
              placeholder="Optional reason"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setExcludeDialog({ participant: null, reason: '' })}>
            Cancel
          </Button>
          <Button
            color="error"
            onClick={submitExcludeParticipant}
            disabled={!excludeDialog.participant || excludeParticipantMutation.loading}
          >
            {excludeParticipantMutation.loading ? 'Excluding...' : 'Exclude'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
