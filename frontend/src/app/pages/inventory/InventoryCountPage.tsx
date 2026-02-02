import { useRef, useState } from 'react'
import axios from 'axios'
import { Trash2 } from 'lucide-react'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Radio, RadioGroup } from '../../components/ui/Radio'
import { Spinner } from '../../components/ui/Spinner'

interface ItemOption {
  id: number
  name: string
  sku_code: string
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
    <div>
      <Typography variant="h4" className="mb-4">
        Inventory count
      </Typography>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" className="mb-4">
          {success}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-4">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Item</TableHeaderCell>
              <TableHeaderCell>Actual quantity</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>
                  <Select
                    value={line.item_id ? String(line.item_id) : ''}
                    onChange={(e) =>
                      updateLine(line.id, {
                        item_id: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                    className="min-w-[240px]"
                  >
                    <option value="">Select item</option>
                    {(items || []).map((item) => (
                      <option key={item.id} value={String(item.id)}>
                        {item.name} ({item.sku_code})
                      </option>
                    ))}
                  </Select>
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    value={line.actual_quantity}
                    onChange={(e) =>
                      updateLine(line.id, { actual_quantity: Number(e.target.value) || 0 })
                    }
                    className="w-32"
                  />
                </TableCell>
                <TableCell align="right">
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => removeLine(line.id)}
                    className="min-w-0"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex gap-2 mb-6">
        <Button variant="outlined" onClick={() => setLines((prev) => [...prev, emptyLine()])}>
          Add item
        </Button>
        <Button variant="contained" onClick={submitCount} disabled={loading}>
          {loading ? <Spinner size="small" /> : 'Apply count'}
        </Button>
      </div>

      <Typography variant="h5" className="mt-8 mb-4">
        Bulk upload from CSV
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-4">
        Download current stock, edit quantities (and add rows for new items), then upload. Overwrite
        zeros all stock first; Update only changes rows that appear in the file.
      </Typography>
      <div className="flex flex-wrap gap-4 items-center mb-4">
        <Button variant="outlined" onClick={downloadCurrentStock}>
          Download current stock
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
        />
        <Button
          variant="outlined"
          onClick={() => fileInputRef.current?.click()}
          disabled={bulkLoading}
        >
          {selectedFile ? selectedFile.name : 'Select CSV'}
        </Button>
        <div className="flex gap-4">
          <RadioGroup value={bulkMode} onChange={(value) => setBulkMode(value as BulkMode)}>
            <Radio value="update" label="Update only" />
            <Radio value="overwrite" label="Overwrite warehouse" />
          </RadioGroup>
        </div>
        <Button
          variant="contained"
          onClick={submitBulkUpload}
          disabled={bulkLoading || !selectedFile}
        >
          {bulkLoading ? <Spinner size="small" /> : 'Upload'}
        </Button>
      </div>
      {bulkResult && bulkResult.errors.length > 0 && (
        <Alert severity="warning" className="mt-2">
          {bulkResult.errors.length} row(s) had errors:{' '}
          {bulkResult.errors.slice(0, 3).map((e) => `Row ${e.row}: ${e.message}`).join('; ')}
          {bulkResult.errors.length > 3 ? ` … and ${bulkResult.errors.length - 3} more` : ''}
        </Alert>
      )}
    </div>
  )
}
