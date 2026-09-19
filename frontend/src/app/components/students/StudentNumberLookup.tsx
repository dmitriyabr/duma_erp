import { useEffect, useRef, useState } from 'react'
import { api } from '../../services/api'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { formatApiErrorMessage } from '../../utils/apiErrors'
import { formatStudentNumberShort } from '../../utils/studentNumber'
import { Alert } from '../ui/Alert'
import { Input } from '../ui/Input'

export interface StudentNumberMatch {
  id: number
  full_name: string
  student_number: string
  billing_account_name: string | null
  billing_account_number: string | null
}

interface Props {
  value: string
  onChange: (value: string) => void
  onSelect: (student: StudentNumberMatch | null) => void
  disabled?: boolean
  excludedStudentId?: number
}

export function StudentNumberLookup({ value, onChange, onSelect, disabled = false, excludedStudentId }: Props) {
  const activeRequest = useRef<AbortController | null>(null)
  const [match, setMatch] = useState<StudentNumberMatch | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const number = value.trim()
  const valid = /^\d{3,8}$/.test(number)

  useEffect(() => {
    if (!valid) return
    const controller = new AbortController()
    activeRequest.current = controller
    const timer = window.setTimeout(async () => {
      setLoading(true)
      try {
        const response = await api.get<ApiResponse<PaginatedResponse<StudentNumberMatch>>>('/students', {
          params: { admission_number: number, page: 1, limit: 1 }, signal: controller.signal,
        })
        if (controller.signal.aborted) return
        const student = response.data.data.items[0] ?? null
        if (student?.id === excludedStudentId) {
          setError('This is the current student. Enter the correct recipient’s number.')
          return
        }
        if (!student) {
          setError(`No student found with number ${number}. Check the number on the invoice.`)
          return
        }
        setMatch(student)
        onSelect(student)
      } catch (err) {
        if (!controller.signal.aborted) setError(formatApiErrorMessage(err))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [value, number, valid, excludedStudentId, onSelect])

  return <div className="space-y-3">
    <Input label="Student number (as shown on invoice)" placeholder="e.g. 2640"
      inputMode="numeric" autoComplete="off" value={value} disabled={disabled}
      onChange={event => {
        activeRequest.current?.abort()
        setMatch(null); setError(null); setLoading(false); onSelect(null)
        onChange(event.target.value)
      }} helperText="Use the student number printed on the invoice, e.g. 2640." />
    {number && !valid && <Alert severity="warning">Use the student number from the invoice, e.g. 2640.</Alert>}
    {loading && <p className="text-sm text-slate-500">Finding student…</p>}
    {error && <Alert severity="error">{error}</Alert>}
    {match && <div className="rounded border border-blue-200 bg-blue-50 p-3" aria-live="polite">
      <strong>{match.full_name} · {formatStudentNumberShort(match.student_number)}</strong>
      <p className="text-sm">{match.billing_account_name} · {match.billing_account_number}</p>
    </div>}
  </div>
}
