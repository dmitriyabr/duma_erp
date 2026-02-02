import { Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api, unwrapResponse } from '../../services/api'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Checkbox } from '../../components/ui/Checkbox'
import { Card, CardContent } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'

interface SchoolSettingsData {
  id: number
  school_name: string
  school_address: string
  school_phone: string
  school_email: string
  use_paybill: boolean
  mpesa_business_number: string
  use_bank_transfer: boolean
  bank_name: string
  bank_account_name: string
  bank_account_number: string
  bank_branch: string
  bank_swift_code: string
  logo_attachment_id: number | null
  stamp_attachment_id: number | null
}

const emptyForm: SchoolSettingsData = {
  id: 0,
  school_name: '',
  school_address: '',
  school_phone: '',
  school_email: '',
  use_paybill: true,
  mpesa_business_number: '',
  use_bank_transfer: false,
  bank_name: '',
  bank_account_name: '',
  bank_account_number: '',
  bank_branch: '',
  bank_swift_code: '',
  logo_attachment_id: null,
  stamp_attachment_id: null,
}

export const SchoolPage = () => {
  const { data: settingsData, loading, error, refetch } = useApi<SchoolSettingsData>('/school-settings')
  const saveMutation = useApiMutation<unknown>()
  const logoUploadMutation = useApiMutation<{ id: number }>()
  const stampUploadMutation = useApiMutation<{ id: number }>()

  const [form, setForm] = useState<SchoolSettingsData>(emptyForm)
  const [success, setSuccess] = useState(false)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [stampPreview, setStampPreview] = useState<string | null>(null)

  useEffect(() => {
    if (settingsData) {
      setForm(settingsData)
    }
  }, [settingsData])

  useEffect(() => {
    if (!settingsData) return
    if (settingsData.logo_attachment_id) {
      api
        .get(`/attachments/${settingsData.logo_attachment_id}/download`, { responseType: 'blob' })
        .then((res) => setLogoPreview(URL.createObjectURL(res.data as Blob)))
        .catch(() => setLogoPreview(null))
    } else {
      setLogoPreview(null)
    }
  }, [settingsData?.logo_attachment_id])

  useEffect(() => {
    if (!settingsData) return
    if (settingsData.stamp_attachment_id) {
      api
        .get(`/attachments/${settingsData.stamp_attachment_id}/download`, { responseType: 'blob' })
        .then((res) => setStampPreview(URL.createObjectURL(res.data as Blob)))
        .catch(() => setStampPreview(null))
    } else {
      setStampPreview(null)
    }
  }, [settingsData?.stamp_attachment_id])

  const handleChange = (field: keyof SchoolSettingsData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const v = e.target.value
    setForm((prev) => ({ ...prev, [field]: v }))
  }

  const handleCheckbox = (field: 'use_paybill' | 'use_bank_transfer') => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.checked }))
  }

  const displayError = error ?? saveMutation.error ?? logoUploadMutation.error ?? stampUploadMutation.error

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) return
    logoUploadMutation.reset()
    const fd = new FormData()
    fd.append('file', file)
    const id = await logoUploadMutation.execute(() =>
      api.post('/attachments', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => ({
        data: { data: unwrapResponse<{ id: number }>(r) },
      }))
    )
    if (id != null) {
      setForm((prev) => ({ ...prev, logo_attachment_id: id.id }))
      setLogoPreview(URL.createObjectURL(file))
    }
    e.target.value = ''
  }

  const handleStampUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) return
    stampUploadMutation.reset()
    const fd = new FormData()
    fd.append('file', file)
    const id = await stampUploadMutation.execute(() =>
      api.post('/attachments', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => ({
        data: { data: unwrapResponse<{ id: number }>(r) },
      }))
    )
    if (id != null) {
      setForm((prev) => ({ ...prev, stamp_attachment_id: id.id }))
      setStampPreview(URL.createObjectURL(file))
    }
    e.target.value = ''
  }

  const handleSave = async () => {
    setSuccess(false)
    saveMutation.reset()
    const ok = await saveMutation.execute(() =>
      api
        .put('/school-settings', {
          school_name: form.school_name || null,
          school_address: form.school_address || null,
          school_phone: form.school_phone || null,
          school_email: form.school_email || null,
          use_paybill: form.use_paybill,
          mpesa_business_number: form.mpesa_business_number || null,
          use_bank_transfer: form.use_bank_transfer,
          bank_name: form.bank_name || null,
          bank_account_name: form.bank_account_name || null,
          bank_account_number: form.bank_account_number || null,
          bank_branch: form.bank_branch || null,
          bank_swift_code: form.bank_swift_code || null,
          logo_attachment_id: form.logo_attachment_id,
          stamp_attachment_id: form.stamp_attachment_id,
        })
        .then((res) => ({ data: { data: unwrapResponse(res) } }))
    )
    if (ok != null) {
      setSuccess(true)
      refetch()
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[200px]">
        <Spinner size="large" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          School settings
        </Typography>
        <Button variant="contained" onClick={handleSave} disabled={saveMutation.loading}>
          {saveMutation.loading ? <Spinner size="small" /> : 'Save'}
        </Button>
      </div>

      {displayError && (
        <Alert
          severity="error"
          onClose={() => {
            saveMutation.reset()
            logoUploadMutation.reset()
            stampUploadMutation.reset()
          }}
          className="mb-4"
        >
          {displayError}
        </Alert>
      )}
      {success && (
        <Alert severity="success" onClose={() => setSuccess(false)} className="mb-4">
          Settings saved.
        </Alert>
      )}

      <Card>
        <CardContent>
          <Typography variant="h6" className="mb-4">
            School info (for invoices & receipts)
          </Typography>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="School name"
              value={form.school_name}
              onChange={handleChange('school_name')}
            />
            <Input
              label="Phone"
              value={form.school_phone}
              onChange={handleChange('school_phone')}
            />
            <div className="md:col-span-2">
              <Input
                label="Address"
                value={form.school_address}
                onChange={handleChange('school_address')}
              />
            </div>
            <div className="md:col-span-2">
              <Input
                label="Email"
                type="email"
                value={form.school_email}
                onChange={handleChange('school_email')}
              />
            </div>
          </div>

          <div className="border-t border-slate-200 my-6" />

          <Typography variant="h6" className="mb-4">
            M-Pesa
          </Typography>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={form.use_paybill}
                  onChange={handleCheckbox('use_paybill')}
                />
                <Typography variant="body2">Use M-Pesa on invoices</Typography>
              </label>
            </div>
            <div className="md:col-span-2">
              <Input
                label="Paybill"
                value={form.mpesa_business_number}
                onChange={handleChange('mpesa_business_number')}
                placeholder="e.g. 123456"
              />
            </div>
          </div>
          <Typography variant="body2" color="secondary" className="mt-2">
            Account number on invoice will be student admission number.
          </Typography>

          <div className="border-t border-slate-200 my-6" />

          <Typography variant="h6" className="mb-4">
            Bank transfer
          </Typography>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={form.use_bank_transfer}
                  onChange={handleCheckbox('use_bank_transfer')}
                />
                <Typography variant="body2">Use bank transfer on invoices</Typography>
              </label>
            </div>
            <Input
              label="Bank name"
              value={form.bank_name}
              onChange={handleChange('bank_name')}
            />
            <Input
              label="Account name"
              value={form.bank_account_name}
              onChange={handleChange('bank_account_name')}
            />
            <Input
              label="Account number"
              value={form.bank_account_number}
              onChange={handleChange('bank_account_number')}
            />
            <Input
              label="Branch"
              value={form.bank_branch}
              onChange={handleChange('bank_branch')}
            />
            <Input
              label="Swift code"
              value={form.bank_swift_code}
              onChange={handleChange('bank_swift_code')}
            />
          </div>

          <div className="border-t border-slate-200 my-6" />

          <Typography variant="h6" className="mb-4">
            Logo & stamp (for PDF)
          </Typography>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Typography variant="body2" color="secondary" className="mb-2">
                Logo (invoices & receipts)
              </Typography>
              {logoPreview && (
                <img
                  src={logoPreview}
                  alt="Logo"
                  className="max-w-[200px] max-h-[100px] object-contain mb-2 block"
                />
              )}
              <label className="inline-block">
                <input type="file" className="hidden" accept="image/*" onChange={handleLogoUpload} disabled={logoUploadMutation.loading} />
                <Button
                  variant="outlined"
                  type="button"
                  disabled={logoUploadMutation.loading}
                  className="cursor-pointer"
                  onClick={(e) => {
                    e.preventDefault()
                    const input = e.currentTarget.parentElement?.querySelector('input[type="file"]') as HTMLInputElement
                    input?.click()
                  }}
                >
                  <Upload className="w-4 h-4 mr-2" />
                  {logoUploadMutation.loading ? 'Uploading…' : 'Upload logo'}
                </Button>
              </label>
            </div>
            <div>
              <Typography variant="body2" color="secondary" className="mb-2">
                Stamp (receipts)
              </Typography>
              {stampPreview && (
                <img
                  src={stampPreview}
                  alt="Stamp"
                  className="max-w-[120px] max-h-[120px] object-contain mb-2 block"
                />
              )}
              <label className="inline-block">
                <input type="file" className="hidden" accept="image/*" onChange={handleStampUpload} disabled={stampUploadMutation.loading} />
                <Button
                  variant="outlined"
                  type="button"
                  disabled={stampUploadMutation.loading}
                  className="cursor-pointer"
                  onClick={(e) => {
                    e.preventDefault()
                    const input = e.currentTarget.parentElement?.querySelector('input[type="file"]') as HTMLInputElement
                    input?.click()
                  }}
                >
                  <Upload className="w-4 h-4 mr-2" />
                  {stampUploadMutation.loading ? 'Uploading…' : 'Upload stamp'}
                </Button>
              </label>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
