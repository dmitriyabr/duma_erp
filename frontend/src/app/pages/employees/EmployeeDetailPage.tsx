import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Switch } from '../../components/ui/Switch'
import { Spinner } from '../../components/ui/Spinner'

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

export const EmployeeDetailPage = () => {
  const { employeeId } = useParams()
  const navigate = useNavigate()
  const resolvedId = employeeId ? Number(employeeId) : null

  const { data: employee, error, loading, refetch } = useApi<EmployeeResponse>(
    resolvedId ? `/employees/${resolvedId}` : null
  )
  const { execute: updateEmployee, loading: saving, error: saveError } = useApiMutation<EmployeeResponse>()
  const { execute: deleteEmployee, loading: deleting, error: deleteError } = useApiMutation<{
    deleted: boolean
  }>()

  const [form, setForm] = useState<EmployeeResponse | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  useEffect(() => {
    if (employee) {
      setForm(employee)
    }
  }, [employee])

  const handleFieldChange = (field: keyof EmployeeResponse, value: unknown) => {
    if (!form) return
    setForm({ ...form, [field]: value } as EmployeeResponse)
  }

  const submitSave = async () => {
    if (!resolvedId || !form) return
    setLocalError(null)

    const payload = {
      surname: form.surname.trim(),
      first_name: form.first_name.trim(),
      second_name: form.second_name?.trim() || null,
      gender: form.gender || null,
      marital_status: form.marital_status || null,
      nationality: form.nationality || null,
      date_of_birth: form.date_of_birth || null,
      mobile_phone: form.mobile_phone?.trim() || null,
      email: form.email?.trim() || null,
      physical_address: form.physical_address?.trim() || null,
      town: form.town?.trim() || null,
      postal_address: form.postal_address?.trim() || null,
      postal_code: form.postal_code?.trim() || null,
      job_title: form.job_title?.trim() || null,
      employee_start_date: form.employee_start_date || null,
      national_id_number: form.national_id_number?.trim() || null,
      kra_pin_number: form.kra_pin_number?.trim() || null,
      nssf_number: form.nssf_number?.trim() || null,
      nhif_number: form.nhif_number?.trim() || null,
      bank_name: form.bank_name?.trim() || null,
      bank_branch_name: form.bank_branch_name?.trim() || null,
      bank_code: form.bank_code?.trim() || null,
      branch_code: form.branch_code?.trim() || null,
      bank_account_number: form.bank_account_number?.trim() || null,
      bank_account_holder_name: form.bank_account_holder_name?.trim() || null,
      next_of_kin_name: form.next_of_kin_name?.trim() || null,
      next_of_kin_relationship: form.next_of_kin_relationship?.trim() || null,
      next_of_kin_phone: form.next_of_kin_phone?.trim() || null,
      next_of_kin_address: form.next_of_kin_address?.trim() || null,
      has_mortgage_relief: form.has_mortgage_relief,
      has_insurance_relief: form.has_insurance_relief,
      status: form.status,
      notes: form.notes?.trim() || null,
      national_id_attachment_id: form.national_id_attachment_id,
      kra_pin_attachment_id: form.kra_pin_attachment_id,
      nssf_attachment_id: form.nssf_attachment_id,
      nhif_attachment_id: form.nhif_attachment_id,
      bank_doc_attachment_id: form.bank_doc_attachment_id,
    }

    const updated = await updateEmployee(() =>
      api.put<ApiResponse<EmployeeResponse>>(`/employees/${resolvedId}`, payload)
    )
    if (!updated) return
    setForm(updated)
    await refetch()
  }

  const uploadAndSetAttachment = async (field: keyof EmployeeResponse) => {
    if (!resolvedId) return
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.pdf,image/*'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      try {
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        const attachmentId = response.data.data.id
        await updateEmployee(() =>
          api.put<ApiResponse<EmployeeResponse>>(`/employees/${resolvedId}`, {
            [field]: attachmentId,
          })
        )
        await refetch()
      } catch (e) {
        setLocalError('Failed to upload file.')
      }
    }
    input.click()
  }

  const handleDelete = async () => {
    if (!resolvedId) return
    if (!window.confirm('Delete this employee? This action cannot be undone.')) return
    const result = await deleteEmployee(() =>
      api.delete<ApiResponse<{ deleted: boolean }>>(`/employees/${resolvedId}`)
    )
    if (result?.deleted) {
      navigate('/employees')
    }
  }

  if (loading && !form) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner size="medium" />
      </div>
    )
  }

  if (!form) {
    return (
      <div>
        {error && <Alert severity="error">{String(error)}</Alert>}
      </div>
    )
  }

  return (
    <div>
      <Button onClick={() => navigate('/employees')} className="mb-4">
        Back to list
      </Button>
      <Button variant="outlined" onClick={() => navigate(`/employees/${resolvedId}`)} className="mb-4 ml-2">
        Back to details
      </Button>

      <Typography variant="h4" className="mb-2">
        Edit: {form.first_name} {form.second_name ? `${form.second_name} ` : ''}{form.surname}
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-4">
        Employee #{form.employee_number}
      </Typography>

      {(error || saveError || deleteError || localError) && (
        <Alert severity="error" className="mb-4" onClose={() => setLocalError(null)}>
          {String(error || saveError || deleteError || localError)}
        </Alert>
      )}

      <div className="grid gap-6">
        {/* Personal & job info */}
        <div className="grid gap-4 max-w-[920px]">
          <Typography variant="h5">Personal & job</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="First name"
              value={form.first_name}
              onChange={(e) => handleFieldChange('first_name', e.target.value)}
              required
            />
            <Input
              label="Second name"
              value={form.second_name ?? ''}
              onChange={(e) => handleFieldChange('second_name', e.target.value)}
            />
            <Input
              label="Surname / Last name"
              value={form.surname}
              onChange={(e) => handleFieldChange('surname', e.target.value)}
              required
            />
            <Input
              label="Job title / Role"
              value={form.job_title ?? ''}
              onChange={(e) => handleFieldChange('job_title', e.target.value)}
            />
            <Input
              label="Date of birth"
              type="date"
              value={form.date_of_birth ?? ''}
              onChange={(e) => handleFieldChange('date_of_birth', e.target.value)}
            />
            <Input
              label="Nationality"
              value={form.nationality ?? ''}
              onChange={(e) => handleFieldChange('nationality', e.target.value)}
            />
            <Input
              label="Employee start date"
              type="date"
              value={form.employee_start_date ?? ''}
              onChange={(e) => handleFieldChange('employee_start_date', e.target.value)}
            />
            <Select
              label="Status"
              value={form.status}
              onChange={(e) => handleFieldChange('status', e.target.value as EmployeeStatus)}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="terminated">Terminated</option>
            </Select>
          </div>
        </div>

        {/* Contacts & address */}
        <div className="grid gap-4 max-w-[920px]">
          <Typography variant="h5">Contacts & address</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="Mobile phone"
              value={form.mobile_phone ?? ''}
              onChange={(e) => handleFieldChange('mobile_phone', e.target.value)}
            />
            <Input
              label="Email"
              type="email"
              value={form.email ?? ''}
              onChange={(e) => handleFieldChange('email', e.target.value)}
            />
            <Input
              label="Town"
              value={form.town ?? ''}
              onChange={(e) => handleFieldChange('town', e.target.value)}
            />
            <Input
              label="Postal address"
              value={form.postal_address ?? ''}
              onChange={(e) => handleFieldChange('postal_address', e.target.value)}
            />
            <Input
              label="Postal code"
              value={form.postal_code ?? ''}
              onChange={(e) => handleFieldChange('postal_code', e.target.value)}
            />
          </div>
          <Textarea
            label="Physical address"
            value={form.physical_address ?? ''}
            onChange={(e) => handleFieldChange('physical_address', e.target.value)}
            rows={2}
          />
        </div>

        {/* IDs & attachments */}
        <div className="grid gap-4 max-w-[920px]">
          <Typography variant="h5">ID & tax numbers</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="National ID Number"
              value={form.national_id_number ?? ''}
              onChange={(e) => handleFieldChange('national_id_number', e.target.value)}
            />
            <Input
              label="KRA PIN Number"
              value={form.kra_pin_number ?? ''}
              onChange={(e) => handleFieldChange('kra_pin_number', e.target.value)}
            />
            <Input
              label="NSSF Number"
              value={form.nssf_number ?? ''}
              onChange={(e) => handleFieldChange('nssf_number', e.target.value)}
            />
            <Input
              label="NHIF / SHA Number"
              value={form.nhif_number ?? ''}
              onChange={(e) => handleFieldChange('nhif_number', e.target.value)}
            />
          </div>
          <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <div className="flex items-center gap-2">
              <Button variant="outlined" size="small" onClick={() => uploadAndSetAttachment('national_id_attachment_id')}>
                {form.national_id_attachment_id ? 'Replace ID file' : 'Upload ID file'}
              </Button>
              {form.national_id_attachment_id && (
                <a
                  href={`/api/v1/attachments/${form.national_id_attachment_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-primary underline"
                >
                  View
                </a>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outlined" size="small" onClick={() => uploadAndSetAttachment('kra_pin_attachment_id')}>
                {form.kra_pin_attachment_id ? 'Replace KRA PIN file' : 'Upload KRA PIN file'}
              </Button>
              {form.kra_pin_attachment_id && (
                <a
                  href={`/api/v1/attachments/${form.kra_pin_attachment_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-primary underline"
                >
                  View
                </a>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outlined" size="small" onClick={() => uploadAndSetAttachment('nssf_attachment_id')}>
                {form.nssf_attachment_id ? 'Replace NSSF file' : 'Upload NSSF file'}
              </Button>
              {form.nssf_attachment_id && (
                <a
                  href={`/api/v1/attachments/${form.nssf_attachment_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-primary underline"
                >
                  View
                </a>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outlined" size="small" onClick={() => uploadAndSetAttachment('nhif_attachment_id')}>
                {form.nhif_attachment_id ? 'Replace NHIF file' : 'Upload NHIF file'}
              </Button>
              {form.nhif_attachment_id && (
                <a
                  href={`/api/v1/attachments/${form.nhif_attachment_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-primary underline"
                >
                  View
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Bank */}
        <div className="grid gap-4 max-w-[920px]">
          <Typography variant="h5">Bank details</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="Bank name"
              value={form.bank_name ?? ''}
              onChange={(e) => handleFieldChange('bank_name', e.target.value)}
            />
            <Input
              label="Branch name"
              value={form.bank_branch_name ?? ''}
              onChange={(e) => handleFieldChange('bank_branch_name', e.target.value)}
            />
            <Input
              label="Bank code"
              value={form.bank_code ?? ''}
              onChange={(e) => handleFieldChange('bank_code', e.target.value)}
            />
            <Input
              label="Branch code"
              value={form.branch_code ?? ''}
              onChange={(e) => handleFieldChange('branch_code', e.target.value)}
            />
            <Input
              label="Account number"
              value={form.bank_account_number ?? ''}
              onChange={(e) => handleFieldChange('bank_account_number', e.target.value)}
            />
            <Input
              label="Account holder name"
              value={form.bank_account_holder_name ?? ''}
              onChange={(e) => handleFieldChange('bank_account_holder_name', e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outlined" size="small" onClick={() => uploadAndSetAttachment('bank_doc_attachment_id')}>
              {form.bank_doc_attachment_id ? 'Replace bank doc' : 'Upload bank doc'}
            </Button>
            {form.bank_doc_attachment_id && (
              <a
                href={`/api/v1/attachments/${form.bank_doc_attachment_id}/download`}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-primary underline"
              >
                View
              </a>
            )}
          </div>
        </div>

        {/* Next of kin & relief */}
        <div className="grid gap-4 max-w-[920px]">
          <Typography variant="h5">Next of kin & reliefs</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="Next of kin name"
              value={form.next_of_kin_name ?? ''}
              onChange={(e) => handleFieldChange('next_of_kin_name', e.target.value)}
            />
            <Input
              label="Relationship"
              value={form.next_of_kin_relationship ?? ''}
              onChange={(e) => handleFieldChange('next_of_kin_relationship', e.target.value)}
            />
            <Input
              label="Next of kin phone"
              value={form.next_of_kin_phone ?? ''}
              onChange={(e) => handleFieldChange('next_of_kin_phone', e.target.value)}
            />
          </div>
          <Textarea
            label="Next of kin address"
            value={form.next_of_kin_address ?? ''}
            onChange={(e) => handleFieldChange('next_of_kin_address', e.target.value)}
            rows={2}
          />
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <div className="flex items-center gap-2">
              <Switch
                checked={form.has_mortgage_relief}
                onChange={(e) => handleFieldChange('has_mortgage_relief', e.target.checked)}
              />
              <span className="text-sm text-slate-700">Has mortgage relief</span>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.has_insurance_relief}
                onChange={(e) => handleFieldChange('has_insurance_relief', e.target.checked)}
              />
              <span className="text-sm text-slate-700">Has insurance reliefs</span>
            </div>
          </div>
        </div>

        {/* Notes & actions */}
        <div className="grid gap-4 max-w-[920px]">
          <Typography variant="h5">Notes</Typography>
          <Textarea
            label="Internal notes"
            value={form.notes ?? ''}
            onChange={(e) => handleFieldChange('notes', e.target.value)}
            rows={3}
          />
          <div className="flex gap-2 mt-2">
            <Button variant="outlined" onClick={() => navigate('/employees')}>
              Cancel
            </Button>
            <Button variant="outlined" color="error" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
            <Button variant="contained" onClick={submitSave} disabled={saving}>
              {saving ? <Spinner size="small" /> : 'Save changes'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

