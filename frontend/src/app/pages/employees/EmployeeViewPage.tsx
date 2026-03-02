import { useNavigate, useParams } from 'react-router-dom'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useAuth } from '../../auth/AuthContext'
import { isAccountant } from '../../utils/permissions'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Typography } from '../../components/ui/Typography'

type EmployeeStatus = 'active' | 'inactive' | 'terminated'

interface EmployeeResponse {
  id: number
  employee_number: string
  surname: string
  first_name: string
  second_name: string | null
  gender: string | null
  marital_status: string | null
  nationality: string | null
  date_of_birth: string | null
  mobile_phone: string | null
  email: string | null
  physical_address: string | null
  town: string | null
  postal_address: string | null
  postal_code: string | null
  job_title: string | null
  employee_start_date: string | null
  salary: string | null
  national_id_number: string | null
  kra_pin_number: string | null
  nssf_number: string | null
  nhif_number: string | null
  bank_name: string | null
  bank_branch_name: string | null
  bank_code: string | null
  branch_code: string | null
  bank_account_number: string | null
  bank_account_holder_name: string | null
  next_of_kin_name: string | null
  next_of_kin_relationship: string | null
  next_of_kin_phone: string | null
  next_of_kin_address: string | null
  has_mortgage_relief: boolean
  has_insurance_relief: boolean
  status: EmployeeStatus
  notes: string | null
  national_id_attachment_id: number | null
  kra_pin_attachment_id: number | null
  nssf_attachment_id: number | null
  nhif_attachment_id: number | null
  bank_doc_attachment_id: number | null
}

const Value = ({ label, value }: { label: string; value: string | number | null | undefined }) => (
  <div className="rounded border border-slate-200 p-3">
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p className="text-sm text-slate-800">{value || '—'}</p>
  </div>
)

const AttachmentLink = ({ label, id }: { label: string; id: number | null }) => (
  <div className="rounded border border-slate-200 p-3">
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    {id ? (
      <a
        href={`/api/v1/attachments/${id}/download`}
        target="_blank"
        rel="noreferrer"
        className="text-sm text-primary underline"
      >
        Open file
      </a>
    ) : (
      <p className="text-sm text-slate-800">—</p>
    )}
  </div>
)

export const EmployeeViewPage = () => {
  const { employeeId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const readOnly = isAccountant(user)
  const resolvedId = employeeId ? Number(employeeId) : null

  const { data: employee, error, loading } = useApi<EmployeeResponse>(
    resolvedId ? `/employees/${resolvedId}` : null
  )
  const { execute: deleteEmployee, loading: deleting, error: deleteError } = useApiMutation<{
    deleted: boolean
  }>()

  const handleDelete = async () => {
    if (!employee) return
    if (!window.confirm('Delete this employee? This action cannot be undone.')) return
    const result = await deleteEmployee(() =>
      api.delete<ApiResponse<{ deleted: boolean }>>(`/employees/${employee.id}`)
    )
    if (result?.deleted) {
      navigate('/employees')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner size="medium" />
      </div>
    )
  }

  if (!employee) {
    return <Alert severity="error">{error || 'Employee not found'}</Alert>
  }

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <Button onClick={() => navigate('/employees')}>Back to list</Button>
        {!readOnly && (
          <>
            <Button variant="outlined" onClick={() => navigate(`/employees/${employee.id}/edit`)}>
              Edit employee
            </Button>
            <Button variant="outlined" color="error" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </>
        )}
      </div>

      {deleteError && <Alert severity="error" className="mb-4">{deleteError}</Alert>}

      <Typography variant="h4" className="mb-2">
        {employee.first_name} {employee.second_name ? `${employee.second_name} ` : ''}
        {employee.surname}
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-5">
        Employee #{employee.employee_number}
      </Typography>

      <div className="grid gap-6">
        <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Value label="Status" value={employee.status} />
          <Value label="Job title" value={employee.job_title} />
          <Value label="Salary (KES)" value={employee.salary} />
          <Value label="Date of birth" value={employee.date_of_birth} />
          <Value label="Employee start date" value={employee.employee_start_date} />
          <Value label="Gender" value={employee.gender} />
          <Value label="Marital status" value={employee.marital_status} />
          <Value label="Nationality" value={employee.nationality} />
        </div>

        <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Value label="Mobile phone" value={employee.mobile_phone} />
          <Value label="Email" value={employee.email} />
          <Value label="Town" value={employee.town} />
          <Value label="Postal address" value={employee.postal_address} />
          <Value label="Postal code" value={employee.postal_code} />
          <Value label="Physical address" value={employee.physical_address} />
        </div>

        <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Value label="National ID" value={employee.national_id_number} />
          <Value label="KRA PIN" value={employee.kra_pin_number} />
          <Value label="NSSF" value={employee.nssf_number} />
          <Value label="NHIF / SHA" value={employee.nhif_number} />
        </div>

        <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Value label="Bank name" value={employee.bank_name} />
          <Value label="Branch name" value={employee.bank_branch_name} />
          <Value label="Bank code" value={employee.bank_code} />
          <Value label="Branch code" value={employee.branch_code} />
          <Value label="Account number" value={employee.bank_account_number} />
          <Value label="Account holder" value={employee.bank_account_holder_name} />
        </div>

        <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <Value label="Next of kin name" value={employee.next_of_kin_name} />
          <Value label="Relationship" value={employee.next_of_kin_relationship} />
          <Value label="Next of kin phone" value={employee.next_of_kin_phone} />
          <Value label="Next of kin address" value={employee.next_of_kin_address} />
          <Value
            label="Mortgage relief"
            value={employee.has_mortgage_relief ? 'Yes' : 'No'}
          />
          <Value
            label="Insurance relief"
            value={employee.has_insurance_relief ? 'Yes' : 'No'}
          />
        </div>

        <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
          <AttachmentLink label="National ID file" id={employee.national_id_attachment_id} />
          <AttachmentLink label="KRA PIN file" id={employee.kra_pin_attachment_id} />
          <AttachmentLink label="NSSF file" id={employee.nssf_attachment_id} />
          <AttachmentLink label="NHIF file" id={employee.nhif_attachment_id} />
          <AttachmentLink label="Bank document" id={employee.bank_doc_attachment_id} />
        </div>

        <Value label="Notes" value={employee.notes} />
      </div>
    </div>
  )
}
