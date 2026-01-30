import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  Divider,
  FormControlLabel,
  Grid,
  Typography,
  TextField,
} from '@mui/material'
import CloudUploadIcon from '@mui/icons-material/CloudUpload'
import { useEffect, useState } from 'react'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api, unwrapResponse } from '../../services/api'

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
    _e: React.ChangeEvent<HTMLInputElement>,
    checked: boolean
  ) => {
    setForm((prev) => ({ ...prev, [field]: checked }))
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
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          School settings
        </Typography>
        <Button variant="contained" onClick={handleSave} disabled={saveMutation.loading}>
          {saveMutation.loading ? 'Saving…' : 'Save'}
        </Button>
      </Box>

      {displayError && (
        <Alert
          severity="error"
          onClose={() => {
            saveMutation.reset()
            logoUploadMutation.reset()
            stampUploadMutation.reset()
          }}
          sx={{ mb: 2 }}
        >
          {displayError}
        </Alert>
      )}
      {success && (
        <Alert severity="success" onClose={() => setSuccess(false)} sx={{ mb: 2 }}>
          Settings saved.
        </Alert>
      )}

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            School info (for invoices & receipts)
          </Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="School name"
                value={form.school_name}
                onChange={handleChange('school_name')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Phone"
                value={form.school_phone}
                onChange={handleChange('school_phone')}
              />
            </Grid>
            <Grid size={12}>
              <TextField
                fullWidth
                label="Address"
                value={form.school_address}
                onChange={handleChange('school_address')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={form.school_email}
                onChange={handleChange('school_email')}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            M-Pesa
          </Typography>
          <Grid container spacing={2}>
            <Grid size={12}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.use_paybill}
                    onChange={handleCheckbox('use_paybill')}
                  />
                }
                label="Use M-Pesa on invoices"
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Paybill"
                value={form.mpesa_business_number}
                onChange={handleChange('mpesa_business_number')}
                placeholder="e.g. 123456"
              />
            </Grid>
          </Grid>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Account number on invoice will be student admission number.
          </Typography>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            Bank transfer
          </Typography>
          <Grid container spacing={2}>
            <Grid size={12}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.use_bank_transfer}
                    onChange={handleCheckbox('use_bank_transfer')}
                  />
                }
                label="Use bank transfer on invoices"
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Bank name"
                value={form.bank_name}
                onChange={handleChange('bank_name')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Account name"
                value={form.bank_account_name}
                onChange={handleChange('bank_account_name')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Account number"
                value={form.bank_account_number}
                onChange={handleChange('bank_account_number')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Branch"
                value={form.bank_branch}
                onChange={handleChange('bank_branch')}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Swift code"
                value={form.bank_swift_code}
                onChange={handleChange('bank_swift_code')}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            Logo & stamp (for PDF)
          </Typography>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Logo (invoices & receipts)
              </Typography>
              {logoPreview && (
                <Box
                  component="img"
                  src={logoPreview}
                  alt="Logo"
                  sx={{ maxWidth: 200, maxHeight: 100, objectFit: 'contain', mb: 1, display: 'block' }}
                />
              )}
              <Button
                variant="outlined"
                component="label"
                startIcon={<CloudUploadIcon />}
                disabled={logoUploadMutation.loading}
              >
                {logoUploadMutation.loading ? 'Uploading…' : 'Upload logo'}
                <input type="file" hidden accept="image/*" onChange={handleLogoUpload} />
              </Button>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Stamp (receipts)
              </Typography>
              {stampPreview && (
                <Box
                  component="img"
                  src={stampPreview}
                  alt="Stamp"
                  sx={{ maxWidth: 120, maxHeight: 120, objectFit: 'contain', mb: 1, display: 'block' }}
                />
              )}
              <Button
                variant="outlined"
                component="label"
                startIcon={<CloudUploadIcon />}
                disabled={stampUploadMutation.loading}
              >
                {stampUploadMutation.loading ? 'Uploading…' : 'Upload stamp'}
                <input type="file" hidden accept="image/*" onChange={handleStampUpload} />
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    </Box>
  )
}
