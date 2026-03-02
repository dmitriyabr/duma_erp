import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import type { ApiResponse, PaginatedResponse } from '../../types/api'
import { useAuth } from '../../auth/AuthContext'
import { isAccountant } from '../../utils/permissions'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Typography } from '../../components/ui/Typography'
import { Dialog, DialogActions, DialogCloseButton, DialogContent, DialogTitle } from '../../components/ui/Dialog'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Autocomplete } from '../../components/ui/Autocomplete'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'

type EmployeeStatus = 'active' | 'inactive' | 'terminated'

interface EmployeeResponse {
  id: number
  employee_number: string
  user_id: number | null
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

type UserRole = 'SuperAdmin' | 'Admin' | 'User' | 'Accountant'

interface UserOption {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
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
  const canCreateUser = user?.role === 'SuperAdmin'
  const resolvedId = employeeId ? Number(employeeId) : null
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [createUserDialogOpen, setCreateUserDialogOpen] = useState(false)
  const [userSearch, setUserSearch] = useState('')
  const [selectedUser, setSelectedUser] = useState<UserOption | null>(null)
  const debouncedUserSearch = useDebouncedValue(userSearch, 300)
  const [createUserForm, setCreateUserForm] = useState({
    email: '',
    full_name: '',
    phone: '',
    role: 'User' as UserRole,
    password: '',
  })

  const { data: employee, error, loading, refetch } = useApi<EmployeeResponse>(
    resolvedId ? `/employees/${resolvedId}` : null
  )
  const { execute: deleteEmployee, loading: deleting, error: deleteError } = useApiMutation<{
    deleted: boolean
  }>()
  const { execute: linkUser, loading: linking, error: linkError } =
    useApiMutation<EmployeeResponse>()
  const { execute: createUser, loading: creatingUser, error: createUserError } =
    useApiMutation<UserOption>()
  const userLookupUrl = useMemo(() => {
    if (readOnly || !linkDialogOpen) return null
    const params = new URLSearchParams()
    params.append('page', '1')
    params.append('limit', '20')
    params.append('is_active', 'true')
    if (debouncedUserSearch.trim()) {
      params.append('search', debouncedUserSearch.trim())
    }
    return `/users?${params.toString()}`
  }, [readOnly, linkDialogOpen, debouncedUserSearch])
  const { data: usersData } = useApi<PaginatedResponse<UserOption>>(userLookupUrl)
  const userOptions = usersData?.items || []

  const openCreateUserDialog = () => {
    if (!employee) return
    setCreateUserForm({
      email: employee.email ?? '',
      full_name: `${employee.first_name} ${employee.second_name ?? ''} ${employee.surname}`.replace(/\s+/g, ' ').trim(),
      phone: employee.mobile_phone ?? '',
      role: 'User',
      password: '',
    })
    setCreateUserDialogOpen(true)
  }

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

  const handleLinkUser = async () => {
    if (!employee || !selectedUser) return
    const updated = await linkUser(() =>
      api.put<ApiResponse<EmployeeResponse>>(`/employees/${employee.id}`, {
        user_id: selectedUser.id,
      })
    )
    if (!updated) return
    setLinkDialogOpen(false)
    setSelectedUser(null)
    setUserSearch('')
    await refetch()
  }

  const handleUnlinkUser = async () => {
    if (!employee) return
    if (!window.confirm('Unlink user from this employee?')) return
    const updated = await linkUser(() =>
      api.put<ApiResponse<EmployeeResponse>>(`/employees/${employee.id}`, {
        user_id: null,
      })
    )
    if (!updated) return
    await refetch()
  }

  const handleCreateUser = async () => {
    if (!employee) return
    const created = await createUser(() =>
      api.post<ApiResponse<UserOption>>('/users', {
        email: createUserForm.email.trim(),
        full_name: createUserForm.full_name.trim(),
        phone: createUserForm.phone.trim() || null,
        role: createUserForm.role,
        password: createUserForm.password.trim() || null,
        employee_id: employee.id,
      })
    )
    if (!created) return
    setCreateUserDialogOpen(false)
    await refetch()
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
            <Button variant="outlined" onClick={() => setLinkDialogOpen(true)} disabled={linking}>
              {employee.user_id ? 'Change linked user' : 'Link user'}
            </Button>
            {employee.user_id && (
              <Button variant="outlined" onClick={handleUnlinkUser} disabled={linking}>
                Unlink user
              </Button>
            )}
            {canCreateUser && !employee.user_id && (
              <Button variant="outlined" onClick={openCreateUserDialog} disabled={creatingUser}>
                Create user
              </Button>
            )}
            <Button variant="outlined" color="error" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </>
        )}
      </div>

      {(deleteError || linkError || createUserError) && (
        <Alert severity="error" className="mb-4">
          {deleteError || linkError || createUserError}
        </Alert>
      )}

      <Typography variant="h4" className="mb-2">
        {employee.first_name} {employee.second_name ? `${employee.second_name} ` : ''}
        {employee.surname}
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-5">
        Employee #{employee.employee_number}
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-5">
        Linked user: {employee.user_id ? `#${employee.user_id}` : 'Not linked'}
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

      <Dialog open={linkDialogOpen} onClose={() => setLinkDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setLinkDialogOpen(false)} />
        <DialogTitle>Link user</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Autocomplete<UserOption>
              label="User"
              options={userOptions}
              value={selectedUser}
              onChange={(value) => setSelectedUser(value)}
              onInputChange={(value) => setUserSearch(value)}
              getOptionValue={(option) => option.id}
              getOptionLabel={(option) => `${option.full_name} (${option.email}) - ${option.role}`}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              placeholder="Type name or email"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setLinkDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleLinkUser} disabled={!selectedUser || linking}>
            {linking ? <Spinner size="small" /> : 'Link user'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={createUserDialogOpen}
        onClose={() => setCreateUserDialogOpen(false)}
        maxWidth="md"
      >
        <DialogCloseButton onClose={() => setCreateUserDialogOpen(false)} />
        <DialogTitle>Create user for employee</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Input
              label="Email"
              value={createUserForm.email}
              onChange={(e) => setCreateUserForm({ ...createUserForm, email: e.target.value })}
              type="email"
              required
            />
            <Input
              label="Full name"
              value={createUserForm.full_name}
              onChange={(e) => setCreateUserForm({ ...createUserForm, full_name: e.target.value })}
              required
            />
            <Input
              label="Phone"
              value={createUserForm.phone}
              onChange={(e) => setCreateUserForm({ ...createUserForm, phone: e.target.value })}
            />
            <Select
              label="Role"
              value={createUserForm.role}
              onChange={(e) =>
                setCreateUserForm({
                  ...createUserForm,
                  role: e.target.value as UserRole,
                })
              }
            >
              <option value="User">User</option>
              <option value="Admin">Admin</option>
              <option value="Accountant">Accountant</option>
            </Select>
            <Input
              label="Password"
              value={createUserForm.password}
              onChange={(e) => setCreateUserForm({ ...createUserForm, password: e.target.value })}
              type="password"
              placeholder="Optional"
              helperText="Leave empty to create user without login access"
            />
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCreateUserDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreateUser}
            disabled={!createUserForm.email.trim() || !createUserForm.full_name.trim() || creatingUser}
          >
            {creatingUser ? <Spinner size="small" /> : 'Create and link'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
