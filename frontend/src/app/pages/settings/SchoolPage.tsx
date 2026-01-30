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
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../services/api'

interface ApiResponse<T> {
  success: boolean
  data: T
}

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
  const [form, setForm] = useState<SchoolSettingsData>(emptyForm)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [stampPreview, setStampPreview] = useState<string | null>(null)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [uploadingStamp, setUploadingStamp] = useState(false)

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<SchoolSettingsData>>('/school-settings')
      const data = response.data.data
      setForm(data)
      if (data.logo_attachment_id) {
        try {
          const blobRes = await api.get(`/attachments/${data.logo_attachment_id}/download`, {
            responseType: 'blob',
          })
          setLogoPreview(URL.createObjectURL(blobRes.data as Blob))
        } catch {
          setLogoPreview(null)
        }
      } else {
        setLogoPreview(null)
      }
      if (data.stamp_attachment_id) {
        try {
          const blobRes = await api.get(`/attachments/${data.stamp_attachment_id}/download`, {
            responseType: 'blob',
          })
          setStampPreview(URL.createObjectURL(blobRes.data as Blob))
        } catch {
          setStampPreview(null)
        }
      } else {
        setStampPreview(null)
      }
    } catch {
      setError('Failed to load school settings.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

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

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Please upload an image (PNG, JPEG, etc.).')
      return
    }
    setUploadingLogo(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post<ApiResponse<{ id: number }>>('/attachments', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const id = res.data.data.id
      setForm((prev) => ({ ...prev, logo_attachment_id: id }))
      setLogoPreview(URL.createObjectURL(file))
    } catch {
      setError('Failed to upload logo.')
    } finally {
      setUploadingLogo(false)
      e.target.value = ''
    }
  }

  const handleStampUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Please upload an image (PNG, JPEG, etc.).')
      return
    }
    setUploadingStamp(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post<ApiResponse<{ id: number }>>('/attachments', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const id = res.data.data.id
      setForm((prev) => ({ ...prev, stamp_attachment_id: id }))
      setStampPreview(URL.createObjectURL(file))
    } catch {
      setError('Failed to upload stamp.')
    } finally {
      setUploadingStamp(false)
      e.target.value = ''
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccess(false)
    try {
      await api.put('/school-settings', {
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
      setSuccess(true)
    } catch {
      setError('Failed to save school settings.')
    } finally {
      setSaving(false)
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
        <Button variant="contained" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
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
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="School name"
                value={form.school_name}
                onChange={handleChange('school_name')}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Phone"
                value={form.school_phone}
                onChange={handleChange('school_phone')}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Address"
                value={form.school_address}
                onChange={handleChange('school_address')}
              />
            </Grid>
            <Grid item xs={12} md={6}>
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
            <Grid item xs={12}>
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
            <Grid item xs={12} md={6}>
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
            <Grid item xs={12}>
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
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Bank name"
                value={form.bank_name}
                onChange={handleChange('bank_name')}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Account name"
                value={form.bank_account_name}
                onChange={handleChange('bank_account_name')}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Account number"
                value={form.bank_account_number}
                onChange={handleChange('bank_account_number')}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Branch"
                value={form.bank_branch}
                onChange={handleChange('bank_branch')}
              />
            </Grid>
            <Grid item xs={12} md={6}>
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
            <Grid item xs={12} md={6}>
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
                disabled={uploadingLogo}
              >
                {uploadingLogo ? 'Uploading…' : 'Upload logo'}
                <input type="file" hidden accept="image/*" onChange={handleLogoUpload} />
              </Button>
            </Grid>
            <Grid item xs={12} md={6}>
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
                disabled={uploadingStamp}
              >
                {uploadingStamp ? 'Uploading…' : 'Upload stamp'}
                <input type="file" hidden accept="image/*" onChange={handleStampUpload} />
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    </Box>
  )
}
