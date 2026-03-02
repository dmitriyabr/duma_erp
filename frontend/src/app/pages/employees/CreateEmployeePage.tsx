import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApiMutation } from '../../hooks/useApi'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Textarea } from '../../components/ui/Textarea'
import { Switch } from '../../components/ui/Switch'
import { Spinner } from '../../components/ui/Spinner'

type EmployeeStatus = 'active' | 'inactive' | 'terminated'

interface EmployeeRow {
  id: number
}

type AttachmentField =
  | 'national_id_attachment_id'
  | 'kra_pin_attachment_id'
  | 'nssf_attachment_id'
  | 'nhif_attachment_id'
  | 'bank_doc_attachment_id'

const emptyForm = {
  surname: '',
  first_name: '',
  second_name: '',
  gender: '',
  marital_status: '',
  nationality: '',
  date_of_birth: '',
  mobile_phone: '',
  email: '',
  physical_address: '',
  town: '',
  postal_address: '',
  postal_code: '',
  job_title: '',
  employee_start_date: '',
  national_id_number: '',
  kra_pin_number: '',
  nssf_number: '',
  nhif_number: '',
  bank_name: '',
  bank_branch_name: '',
  bank_code: '',
  branch_code: '',
  bank_account_number: '',
  bank_account_holder_name: '',
  next_of_kin_name: '',
  next_of_kin_relationship: '',
  next_of_kin_phone: '',
  next_of_kin_address: '',
  has_mortgage_relief: false,
  has_insurance_relief: false,
  status: 'active' as EmployeeStatus,
  notes: '',
  national_id_attachment_id: null as number | null,
  kra_pin_attachment_id: null as number | null,
  nssf_attachment_id: null as number | null,
  nhif_attachment_id: null as number | null,
  bank_doc_attachment_id: null as number | null,
}

export const CreateEmployeePage = () => {
  const navigate = useNavigate()
  const [form, setForm] = useState({ ...emptyForm })
  const [localError, setLocalError] = useState<string | null>(null)
  const [pendingFiles, setPendingFiles] = useState<Partial<Record<AttachmentField, File>>>({})

  const { execute: saveEmployee, loading: saving, error: saveError } = useApiMutation<EmployeeRow>()

  const uploadAttachment = async (field: AttachmentField) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.pdf,image/*'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      setLocalError(null)
      setPendingFiles((prev) => ({ ...prev, [field]: file }))
    }
    input.click()
  }

  const submitCreate = async () => {
    const payload = {
      surname: form.surname.trim(),
      first_name: form.first_name.trim(),
      second_name: form.second_name.trim() || null,
      gender: form.gender.trim() || null,
      marital_status: form.marital_status.trim() || null,
      nationality: form.nationality.trim() || null,
      date_of_birth: form.date_of_birth || null,
      job_title: form.job_title.trim() || null,
      mobile_phone: form.mobile_phone.trim() || null,
      email: form.email.trim() || null,
      physical_address: form.physical_address.trim() || null,
      town: form.town.trim() || null,
      postal_address: form.postal_address.trim() || null,
      postal_code: form.postal_code.trim() || null,
      national_id_number: form.national_id_number.trim() || null,
      kra_pin_number: form.kra_pin_number.trim() || null,
      nssf_number: form.nssf_number.trim() || null,
      nhif_number: form.nhif_number.trim() || null,
      employee_start_date: form.employee_start_date || null,
      bank_name: form.bank_name.trim() || null,
      bank_branch_name: form.bank_branch_name.trim() || null,
      bank_code: form.bank_code.trim() || null,
      branch_code: form.branch_code.trim() || null,
      bank_account_number: form.bank_account_number.trim() || null,
      bank_account_holder_name: form.bank_account_holder_name.trim() || null,
      next_of_kin_name: form.next_of_kin_name.trim() || null,
      next_of_kin_relationship: form.next_of_kin_relationship.trim() || null,
      next_of_kin_phone: form.next_of_kin_phone.trim() || null,
      next_of_kin_address: form.next_of_kin_address.trim() || null,
      has_mortgage_relief: form.has_mortgage_relief,
      has_insurance_relief: form.has_insurance_relief,
      notes: form.notes.trim() || null,
      status: form.status,
      national_id_attachment_id: form.national_id_attachment_id,
      kra_pin_attachment_id: form.kra_pin_attachment_id,
      nssf_attachment_id: form.nssf_attachment_id,
      nhif_attachment_id: form.nhif_attachment_id,
      bank_doc_attachment_id: form.bank_doc_attachment_id,
    }

    const employee = await saveEmployee(() => api.post<ApiResponse<EmployeeRow>>('/employees', payload))
    if (!employee) return

    try {
      const attachmentPayload: Partial<Record<AttachmentField, number>> = {}
      for (const [field, file] of Object.entries(pendingFiles) as Array<[AttachmentField, File]>) {
        if (!file) continue
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post<ApiResponse<{ id: number }>>('/attachments', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        attachmentPayload[field] = response.data.data.id
      }

      if (Object.keys(attachmentPayload).length > 0) {
        await api.put<ApiResponse<EmployeeRow>>(`/employees/${employee.id}`, attachmentPayload)
      }
    } catch {
      setLocalError('Employee created, but some files failed to upload.')
    }

    navigate(`/employees/${employee.id}`)
  }

  return (
    <div>
      <Button onClick={() => navigate(-1)} className="mb-4">
        Back
      </Button>
      <Typography variant="h4" className="mb-4">
        New employee
      </Typography>

      {(saveError || localError) && (
        <Alert severity="error" className="mb-4" onClose={() => setLocalError(null)}>
          {saveError || localError}
        </Alert>
      )}

      <div className="grid gap-6 max-w-[920px]">
        <div className="grid gap-4">
          <Typography variant="h5">Personal & job</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="First name"
              value={form.first_name}
              onChange={(event) => setForm({ ...form, first_name: event.target.value })}
              required
            />
            <Input
              label="Second name (optional)"
              value={form.second_name}
              onChange={(event) => setForm({ ...form, second_name: event.target.value })}
            />
            <Input
              label="Surname / Last name"
              value={form.surname}
              onChange={(event) => setForm({ ...form, surname: event.target.value })}
              required
            />
            <Input
              label="Job title / Role"
              value={form.job_title}
              onChange={(event) => setForm({ ...form, job_title: event.target.value })}
            />
            <Input
              label="Date of birth"
              type="date"
              value={form.date_of_birth}
              onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })}
            />
            <Input
              label="Nationality"
              value={form.nationality}
              onChange={(event) => setForm({ ...form, nationality: event.target.value })}
            />
            <Input
              label="Employee start date"
              type="date"
              value={form.employee_start_date}
              onChange={(event) => setForm({ ...form, employee_start_date: event.target.value })}
            />
            <Select
              label="Status"
              value={form.status}
              onChange={(event) => setForm({ ...form, status: event.target.value as EmployeeStatus })}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="terminated">Terminated</option>
            </Select>
          </div>
        </div>

        <div className="grid gap-4">
          <Typography variant="h5">Contacts & address</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="Mobile phone"
              value={form.mobile_phone}
              onChange={(event) => setForm({ ...form, mobile_phone: event.target.value })}
              placeholder="07..."
            />
            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
            <Input
              label="Town"
              value={form.town}
              onChange={(event) => setForm({ ...form, town: event.target.value })}
            />
            <Input
              label="Postal address"
              value={form.postal_address}
              onChange={(event) => setForm({ ...form, postal_address: event.target.value })}
            />
            <Input
              label="Postal code"
              value={form.postal_code}
              onChange={(event) => setForm({ ...form, postal_code: event.target.value })}
            />
          </div>
          <Textarea
            label="Physical address"
            value={form.physical_address}
            onChange={(event) => setForm({ ...form, physical_address: event.target.value })}
            rows={2}
          />
        </div>

        <div className="grid gap-4">
          <Typography variant="h5">ID & tax numbers</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="National ID Number"
              value={form.national_id_number}
              onChange={(event) => setForm({ ...form, national_id_number: event.target.value })}
            />
            <Input
              label="KRA PIN Number"
              value={form.kra_pin_number}
              onChange={(event) => setForm({ ...form, kra_pin_number: event.target.value })}
            />
            <Input
              label="NSSF Number"
              value={form.nssf_number}
              onChange={(event) => setForm({ ...form, nssf_number: event.target.value })}
            />
            <Input
              label="NHIF / SHA Number"
              value={form.nhif_number}
              onChange={(event) => setForm({ ...form, nhif_number: event.target.value })}
            />
          </div>
          <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Button variant="outlined" size="small" onClick={() => uploadAttachment('national_id_attachment_id')}>
              {pendingFiles.national_id_attachment_id ? `Selected: ${pendingFiles.national_id_attachment_id.name}` : 'Upload ID file'}
            </Button>
            <Button variant="outlined" size="small" onClick={() => uploadAttachment('kra_pin_attachment_id')}>
              {pendingFiles.kra_pin_attachment_id ? `Selected: ${pendingFiles.kra_pin_attachment_id.name}` : 'Upload KRA PIN file'}
            </Button>
            <Button variant="outlined" size="small" onClick={() => uploadAttachment('nssf_attachment_id')}>
              {pendingFiles.nssf_attachment_id ? `Selected: ${pendingFiles.nssf_attachment_id.name}` : 'Upload NSSF file'}
            </Button>
            <Button variant="outlined" size="small" onClick={() => uploadAttachment('nhif_attachment_id')}>
              {pendingFiles.nhif_attachment_id ? `Selected: ${pendingFiles.nhif_attachment_id.name}` : 'Upload NHIF file'}
            </Button>
          </div>
        </div>

        <div className="grid gap-4">
          <Typography variant="h5">Bank details</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="Bank name"
              value={form.bank_name}
              onChange={(event) => setForm({ ...form, bank_name: event.target.value })}
            />
            <Input
              label="Branch name"
              value={form.bank_branch_name}
              onChange={(event) => setForm({ ...form, bank_branch_name: event.target.value })}
            />
            <Input
              label="Bank code"
              value={form.bank_code}
              onChange={(event) => setForm({ ...form, bank_code: event.target.value })}
            />
            <Input
              label="Branch code"
              value={form.branch_code}
              onChange={(event) => setForm({ ...form, branch_code: event.target.value })}
            />
            <Input
              label="Account number"
              value={form.bank_account_number}
              onChange={(event) => setForm({ ...form, bank_account_number: event.target.value })}
            />
            <Input
              label="Account holder name"
              value={form.bank_account_holder_name}
              onChange={(event) => setForm({ ...form, bank_account_holder_name: event.target.value })}
            />
          </div>
          <Button variant="outlined" size="small" onClick={() => uploadAttachment('bank_doc_attachment_id')}>
            {pendingFiles.bank_doc_attachment_id ? `Selected: ${pendingFiles.bank_doc_attachment_id.name}` : 'Upload bank doc'}
          </Button>
        </div>

        <div className="grid gap-4">
          <Typography variant="h5">Next of kin & reliefs</Typography>
          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
            <Input
              label="Next of kin name"
              value={form.next_of_kin_name}
              onChange={(event) => setForm({ ...form, next_of_kin_name: event.target.value })}
            />
            <Input
              label="Relationship"
              value={form.next_of_kin_relationship}
              onChange={(event) => setForm({ ...form, next_of_kin_relationship: event.target.value })}
            />
            <Input
              label="Next of kin phone"
              value={form.next_of_kin_phone}
              onChange={(event) => setForm({ ...form, next_of_kin_phone: event.target.value })}
            />
          </div>
          <Textarea
            label="Next of kin address"
            value={form.next_of_kin_address}
            onChange={(event) => setForm({ ...form, next_of_kin_address: event.target.value })}
            rows={2}
          />
          <div className="flex items-center gap-2">
            <Switch
              checked={form.has_mortgage_relief}
              onChange={(event) => setForm({ ...form, has_mortgage_relief: event.target.checked })}
            />
            <span className="text-sm text-slate-700">Has mortgage relief</span>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={form.has_insurance_relief}
              onChange={(event) => setForm({ ...form, has_insurance_relief: event.target.checked })}
            />
            <span className="text-sm text-slate-700">Has insurance reliefs</span>
          </div>
        </div>

        <div className="grid gap-4">
          <Typography variant="h5">Notes</Typography>
          <Textarea
            label="Internal notes"
            value={form.notes}
            onChange={(event) => setForm({ ...form, notes: event.target.value })}
            rows={3}
          />
          <div className="flex gap-2 mt-2">
            <Button variant="outlined" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={submitCreate}
              disabled={saving || !form.first_name.trim() || !form.surname.trim()}
            >
              {saving ? <Spinner size="small" /> : 'Create employee'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
