import {
  Alert,
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { api } from '../../services/api'

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

export const InventoryCountPage = () => {
  const [items, setItems] = useState<ItemOption[]>([])
  const [lines, setLines] = useState<CountLine[]>([emptyLine()])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const fetchItems = async () => {
    try {
      const response = await api.get<ApiResponse<ItemOption[]>>('/items', {
        params: { include_inactive: true, item_type: 'product' },
      })
      setItems(response.data.data)
    } catch {
      setItems([])
    }
  }

  useEffect(() => {
    fetchItems()
  }, [])

  const updateLine = (lineId: string, updates: Partial<CountLine>) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? { ...line, ...updates } : line)))
  }

  const removeLine = (lineId: string) => {
    setLines((prev) => prev.filter((line) => line.id !== lineId))
  }

  const submitCount = async () => {
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const validLines = lines.filter((line) => line.item_id !== null)
      if (!validLines.length) {
        setError('Add at least one item.')
        setLoading(false)
        return
      }
      await api.post('/inventory/inventory-count', {
        items: validLines.map((line) => ({
          item_id: line.item_id,
          actual_quantity: line.actual_quantity,
        })),
      })
      setSuccess('Inventory count submitted.')
      setLines([emptyLine()])
    } catch {
      setError('Failed to submit inventory count.')
    } finally {
      setLoading(false)
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
                    {items.map((item) => (
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
    </Box>
  )
}
