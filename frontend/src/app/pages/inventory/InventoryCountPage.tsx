import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useRef, useState } from 'react'
import axios from 'axios'
import { api } from '../../services/api'
import { useApi, useApiMutation } from '../../hooks/useApi'

interface ItemOption {
  id: number
  name: string
  sku_code: string
}

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface CountLine {
  id: string
  item_id: number | null
  actual_quantity: number
}

const emptyLine = (): CountLine => ({
  id: `${Date.now()}-${Math.random()}`,
  item_id: null,
  actual_quantity: 0,
})

type BulkMode = 'overwrite' | 'update'

interface BulkUploadResult {
  rows_processed: number
  items_created: number
  errors: Array<{ row: number; message: string }>
}

export const InventoryCountPage = () => {
  const [lines, setLines] = useState<CountLine[]>([emptyLine()])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [bulkMode, setBulkMode] = useState<BulkMode>('update')
  const [bulkResult, setBulkResult] = useState<BulkUploadResult | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: items } = useApi<ItemOption[]>('/items', {
    params: { include_inactive: true, item_type: 'product' },
  })

  const { execute: submitCountMutation, loading } = useApiMutation<void>()
  const { execute: uploadBulkMutation, loading: bulkLoading } = useApiMutation<BulkUploadResult>()

  const updateLine = (lineId: string, updates: Partial<CountLine>) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? { ...line, ...updates } : line)))
  }

  const removeLine = (lineId: string) => {
    setLines((prev) => prev.filter((line) => line.id !== lineId))
  }

  const submitCount = async () => {
    setError(null)
    setSuccess(null)

    const validLines = lines.filter((line) => line.item_id !== null)
    if (!validLines.length) {
      setError('Add at least one item.')
      return
    }

    const result = await submitCountMutation(() =>
      api.post('/inventory/inventory-count', {
        items: validLines.map((line) => ({
          item_id: line.item_id,
          actual_quantity: line.actual_quantity,
        })),
      })
    )

    if (result !== null) {
      setSuccess('Inventory count submitted.')
      setLines([emptyLine()])
    }
  }

  const downloadCurrentStock = async () => {
    setError(null)
    try {
      const response = await api.get('/inventory/bulk-upload/export', {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'stock_export.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        return
      }
      setError('Failed to download stock export.')
    }
  }

  const submitBulkUpload = async () => {
    const file = fileInputRef.current?.files?.[0]
    if (!file) {
      setError('Select a CSV file.')
      return
    }

    setError(null)
    setBulkResult(null)
    setSuccess(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', bulkMode)

    try {
      const result = await uploadBulkMutation(() =>
        api.post<ApiResponse<BulkUploadResult>>('/inventory/bulk-upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      )

      if (result) {
        setBulkResult(result)
        setSuccess(
          `Processed ${result.rows_processed} rows, created ${result.items_created} new items.`
        )
        setSelectedFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
      }
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        return
      }
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null
      setError(msg ?? 'Failed to upload CSV.')
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Inventory count
      </Typography>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}
      {success ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Item</TableCell>
            <TableCell>Actual quantity</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lines.map((line) => (
            <TableRow key={line.id}>
              <TableCell>
                <FormControl size="small" sx={{ minWidth: 240 }}>
                  <InputLabel>Item</InputLabel>
                  <Select
                    value={line.item_id ? String(line.item_id) : ''}
                    label="Item"
                    onChange={(event) =>
                      updateLine(line.id, {
                        item_id: event.target.value ? Number(event.target.value) : null,
                      })
                    }
                    displayEmpty
                  >
                    <MenuItem value="">Select item</MenuItem>
                    {(items || []).map((item) => (
                      <MenuItem key={item.id} value={String(item.id)}>
                        {item.name} ({item.sku_code})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </TableCell>
              <TableCell>
                <TextField
                  size="small"
                  type="number"
                  value={line.actual_quantity}
                  onChange={(event) =>
                    updateLine(line.id, { actual_quantity: Number(event.target.value) || 0 })
                  }
                />
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => removeLine(line.id)}>
                  Remove
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
        <Button onClick={() => setLines((prev) => [...prev, emptyLine()])}>Add item</Button>
        <Button variant="contained" onClick={submitCount} disabled={loading}>
          Apply count
        </Button>
      </Box>

      <Typography variant="h5" sx={{ fontWeight: 600, mt: 4, mb: 2 }}>
        Bulk upload from CSV
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Download current stock, edit quantities (and add rows for new items), then upload. Overwrite
        zeros all stock first; Update only changes rows that appear in the file.
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', mb: 2 }}>
        <Button variant="outlined" onClick={downloadCurrentStock}>
          Download current stock
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: 'none' }}
          onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
        />
        <Button
          variant="outlined"
          onClick={() => fileInputRef.current?.click()}
          disabled={bulkLoading}
        >
          {selectedFile ? selectedFile.name : 'Select CSV'}
        </Button>
        <FormControl component="fieldset">
          <RadioGroup
            row
            value={bulkMode}
            onChange={(e) => setBulkMode(e.target.value as BulkMode)}
          >
            <FormControlLabel value="update" control={<Radio />} label="Update only" />
            <FormControlLabel value="overwrite" control={<Radio />} label="Overwrite warehouse" />
          </RadioGroup>
        </FormControl>
        <Button
          variant="contained"
          onClick={submitBulkUpload}
          disabled={bulkLoading || !selectedFile}
        >
          {bulkLoading ? 'Uploading…' : 'Upload'}
        </Button>
      </Box>
      {bulkResult && bulkResult.errors.length > 0 ? (
        <Alert severity="warning" sx={{ mt: 1 }}>
          {bulkResult.errors.length} row(s) had errors: {bulkResult.errors.slice(0, 3).map((e) => `Row ${e.row}: ${e.message}`).join('; ')}
          {bulkResult.errors.length > 3 ? ` … and ${bulkResult.errors.length - 3} more` : ''}
        </Alert>
      ) : null}
    </Box>
  )
}
