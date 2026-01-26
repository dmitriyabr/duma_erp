import {
  Alert,
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

interface GradeRow {
  id: number
  code: string
  name: string
  display_order: number
}

interface ZoneRow {
  id: number
  zone_name: string
  zone_code: string
}

interface PriceSettingRow {
  grade: string
  school_fee_amount: number
}

interface TransportPricingRow {
  zone_id: number
  zone_name: string
  zone_code: string
  transport_fee_amount: number
}

interface TermDetail {
  id: number
  year: number
  term_number: number
  display_name: string
  status: 'Draft' | 'Active' | 'Closed'
  start_date?: string | null
  end_date?: string | null
  price_settings: PriceSettingRow[]
  transport_pricings: TransportPricingRow[]
}

interface PriceSettingDraft {
  grade: string
  school_fee_amount: number
}

interface TransportPricingDraft {
  zone_id: number
  zone_name: string
  zone_code: string
  transport_fee_amount: number
}

const getDefaultTermDates = () => {
  const start = new Date()
  const end = new Date()
  end.setMonth(end.getMonth() + 3)
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

export const TermFormPage = () => {
  const { termId } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(termId)
  const resolvedId = termId ? Number(termId) : null
  const currentYear = new Date().getFullYear()
  const defaultDates = getDefaultTermDates()

  const [year, setYear] = useState<number | ''>(currentYear)
  const [termNumber, setTermNumber] = useState<number | ''>('')
  const [startDate, setStartDate] = useState(defaultDates.start)
  const [endDate, setEndDate] = useState(defaultDates.end)

  const [grades, setGrades] = useState<GradeRow[]>([])
  const [zones, setZones] = useState<ZoneRow[]>([])
  const [priceSettings, setPriceSettings] = useState<PriceSettingDraft[]>([])
  const [transportPricing, setTransportPricing] = useState<TransportPricingDraft[]>([])
  const [existingPricing, setExistingPricing] = useState<{
    price_settings: PriceSettingRow[]
    transport_pricings: TransportPricingRow[]
  }>({ price_settings: [], transport_pricings: [] })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [initialized, setInitialized] = useState(false)

  const loadReferenceData = useCallback(async () => {
    try {
      const [gradesResponse, zonesResponse] = await Promise.all([
        api.get<ApiResponse<GradeRow[]>>('/students/grades', { params: { include_inactive: true } }),
        api.get<ApiResponse<ZoneRow[]>>('/terms/transport-zones', {
          params: { include_inactive: true },
        }),
      ])
      const sortedGrades = [...gradesResponse.data.data].sort(
        (a, b) => a.display_order - b.display_order
      )
      setGrades(sortedGrades)
      setZones(zonesResponse.data.data)
    } catch {
      setError('Failed to load pricing references.')
    }
  }, [])

  const loadTerm = useCallback(async () => {
    if (!resolvedId) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<TermDetail>>(`/terms/${resolvedId}`)
      const term = response.data.data
      setInitialized(false)
      setYear(term.year)
      setTermNumber(term.term_number)
      setStartDate(term.start_date ?? defaultDates.start)
      setEndDate(term.end_date ?? defaultDates.end)
      setExistingPricing({
        price_settings: term.price_settings,
        transport_pricings: term.transport_pricings,
      })
    } catch {
      setError('Failed to load term.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  const loadDefaultsFromActive = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<TermDetail | null>>('/terms/active')
      if (response.data.data) {
        setInitialized(false)
        setExistingPricing({
          price_settings: response.data.data.price_settings,
          transport_pricings: response.data.data.transport_pricings,
        })
      }
    } catch {
      setExistingPricing({ price_settings: [], transport_pricings: [] })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadReferenceData()
  }, [loadReferenceData])

  useEffect(() => {
    if (isEdit) {
      loadTerm()
    } else {
      loadDefaultsFromActive()
    }
  }, [isEdit, loadDefaultsFromActive, loadTerm])

  useEffect(() => {
    if (initialized || !grades.length || !zones.length) {
      return
    }
    const gradeMap = new Map(
      existingPricing.price_settings.map((entry) => [entry.grade, Number(entry.school_fee_amount)])
    )
    const zoneMap = new Map(
      existingPricing.transport_pricings.map((entry) => [
        entry.zone_id,
        Number(entry.transport_fee_amount),
      ])
    )
    setPriceSettings(
      grades.map((grade) => ({
        grade: grade.code,
        school_fee_amount: gradeMap.get(grade.code) ?? 0,
      }))
    )
    setTransportPricing(
      zones.map((zone) => ({
        zone_id: zone.id,
        zone_name: zone.zone_name,
        zone_code: zone.zone_code,
        transport_fee_amount: zoneMap.get(zone.id) ?? 0,
      }))
    )
    setInitialized(true)
  }, [grades, zones, existingPricing, initialized])

  const gradeNameMap = useMemo(() => {
    return new Map(grades.map((grade) => [grade.code, grade.name]))
  }, [grades])

  const updatePriceSetting = (grade: string, value: string) => {
    const nextValue = Number(value)
    setPriceSettings((prev) =>
      prev.map((entry) =>
        entry.grade === grade
          ? {
              ...entry,
              school_fee_amount: Number.isNaN(nextValue) ? 0 : nextValue,
            }
          : entry
      )
    )
  }

  const updateTransportPricing = (zoneId: number, value: string) => {
    const nextValue = Number(value)
    setTransportPricing((prev) =>
      prev.map((entry) =>
        entry.zone_id === zoneId
          ? {
              ...entry,
              transport_fee_amount: Number.isNaN(nextValue) ? 0 : nextValue,
            }
          : entry
      )
    )
  }

  const handleSubmit = async () => {
    if (!year || !termNumber) {
      setError('Enter year and term number.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      let termId = resolvedId
      if (isEdit && termId) {
        await api.put(`/terms/${termId}`, {
          start_date: startDate || null,
          end_date: endDate || null,
        })
      } else {
        const response = await api.post<ApiResponse<{ id: number }>>('/terms', {
          year: Number(year),
          term_number: Number(termNumber),
          start_date: startDate || null,
          end_date: endDate || null,
        })
        termId = response.data.data.id
      }

      if (!termId) {
        setError('Term id not returned.')
        setLoading(false)
        return
      }

      await Promise.all([
        api.put(`/terms/${termId}/price-settings`, {
          price_settings: priceSettings.map((entry) => ({
            grade: entry.grade,
            school_fee_amount: entry.school_fee_amount || 0,
          })),
        }),
        api.put(`/terms/${termId}/transport-pricing`, {
          transport_pricings: transportPricing.map((entry) => ({
            zone_id: entry.zone_id,
            transport_fee_amount: entry.transport_fee_amount || 0,
          })),
        }),
      ])

      navigate(`/billing/terms/${termId}`)
    } catch {
      setError('Failed to save term.')
    } finally {
      setLoading(false)
    }
  }

  const displayName = useMemo(() => {
    if (!year || !termNumber) {
      return ''
    }
    return `${year}-T${termNumber}`
  }, [year, termNumber])

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        {isEdit ? 'Edit term' : 'New term'}
      </Typography>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gap: 2, maxWidth: 520 }}>
        <TextField
          label="Year"
          type="number"
          value={year}
          onChange={(event) =>
            setYear(event.target.value === '' ? '' : Number(event.target.value))
          }
          disabled={isEdit}
        />
        <TextField
          label="Term number"
          type="number"
          value={termNumber}
          onChange={(event) =>
            setTermNumber(event.target.value === '' ? '' : Number(event.target.value))
          }
          disabled={isEdit}
        />
        <TextField label="Display name" value={displayName} disabled />
        <TextField
          label="Start date"
          type="date"
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          label="End date"
          type="date"
          value={endDate}
          onChange={(event) => setEndDate(event.target.value)}
          InputLabelProps={{ shrink: true }}
        />
      </Box>

      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          School fees by grade
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Grade</TableCell>
              <TableCell>Amount (KES)</TableCell>
              <TableCell align="right">Preview</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {priceSettings.map((entry) => (
              <TableRow key={entry.grade}>
                <TableCell>{gradeNameMap.get(entry.grade) ?? entry.grade}</TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    type="number"
                    value={entry.school_fee_amount === 0 ? '' : entry.school_fee_amount}
                    onChange={(event) => updatePriceSetting(entry.grade, event.target.value)}
                    onFocus={(event) => event.currentTarget.select()}
                    onWheel={(event) => event.currentTarget.blur()}
                    inputProps={{ min: 0, step: 0.01 }}
                  />
                </TableCell>
                <TableCell align="right">
                  {formatMoney(entry.school_fee_amount || 0)}
                </TableCell>
              </TableRow>
            ))}
            {!priceSettings.length ? (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  No grades found
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Box>

      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Transport fees by zone
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Zone</TableCell>
              <TableCell>Code</TableCell>
              <TableCell>Amount (KES)</TableCell>
              <TableCell align="right">Preview</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {transportPricing.map((entry) => (
              <TableRow key={entry.zone_id}>
                <TableCell>{entry.zone_name}</TableCell>
                <TableCell>{entry.zone_code}</TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    type="number"
                    value={entry.transport_fee_amount === 0 ? '' : entry.transport_fee_amount}
                    onChange={(event) => updateTransportPricing(entry.zone_id, event.target.value)}
                    onFocus={(event) => event.currentTarget.select()}
                    onWheel={(event) => event.currentTarget.blur()}
                    inputProps={{ min: 0, step: 0.01 }}
                  />
                </TableCell>
                <TableCell align="right">
                  {formatMoney(entry.transport_fee_amount || 0)}
                </TableCell>
              </TableRow>
            ))}
            {!transportPricing.length ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  No transport zones found
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
        <Button onClick={() => navigate('/billing/terms')}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={loading}>
          Save term
        </Button>
      </Box>
    </Box>
  )
}
