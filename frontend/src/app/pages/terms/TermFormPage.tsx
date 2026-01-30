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
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { api } from '../../services/api'
import { formatMoney } from '../../utils/format'

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

const defaultDates = getDefaultTermDates()

export const TermFormPage = () => {
  const { termId } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(termId)
  const resolvedId = termId ? Number(termId) : null
  const currentYear = new Date().getFullYear()

  const [year, setYear] = useState<number | ''>(currentYear)
  const [termNumber, setTermNumber] = useState<number | ''>('')
  const [startDate, setStartDate] = useState(defaultDates.start)
  const [endDate, setEndDate] = useState(defaultDates.end)
  const [priceSettings, setPriceSettings] = useState<PriceSettingDraft[]>([])
  const [transportPricing, setTransportPricing] = useState<TransportPricingDraft[]>([])
  const [initialized, setInitialized] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const gradesApi = useApi<GradeRow[]>('/students/grades', { params: { include_inactive: true } })
  const zonesApi = useApi<ZoneRow[]>('/terms/transport-zones', {
    params: { include_inactive: true },
  })
  const termApi = useApi<TermDetail | null>(
    isEdit && resolvedId != null ? `/terms/${resolvedId}` : isEdit ? null : '/terms/active'
  )
  const submitMutation = useApiMutation<{ id: number }>()

  const grades = useMemo(
    () => [...(gradesApi.data ?? [])].sort((a, b) => a.display_order - b.display_order),
    [gradesApi.data]
  )
  const zones = zonesApi.data ?? []
  const existingPricing = useMemo(
    () =>
      termApi.data
        ? {
            price_settings: termApi.data.price_settings,
            transport_pricings: termApi.data.transport_pricings,
          }
        : { price_settings: [] as PriceSettingRow[], transport_pricings: [] as TransportPricingRow[] },
    [termApi.data]
  )
  const error = gradesApi.error ?? zonesApi.error ?? termApi.error ?? submitMutation.error
  const displayError = validationError ?? error
  const loading = submitMutation.loading

  useEffect(() => {
    const term = termApi.data
    if (!term) return
    setYear(term.year)
    setTermNumber(term.term_number)
    setStartDate(term.start_date ?? defaultDates.start)
    setEndDate(term.end_date ?? defaultDates.end)
    setInitialized(false)
  }, [termApi.data])

  useEffect(() => {
    if (initialized || !grades.length || !zones.length) return
    const gradeMap = new Map(
      existingPricing.price_settings.map((e) => [e.grade, Number(e.school_fee_amount)])
    )
    const zoneMap = new Map(
      existingPricing.transport_pricings.map((e) => [e.zone_id, Number(e.transport_fee_amount)])
    )
    setPriceSettings(
      grades.map((g) => ({ grade: g.code, school_fee_amount: gradeMap.get(g.code) ?? 0 }))
    )
    setTransportPricing(
      zones.map((z) => ({
        zone_id: z.id,
        zone_name: z.zone_name,
        zone_code: z.zone_code,
        transport_fee_amount: zoneMap.get(z.id) ?? 0,
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
      setValidationError('Enter year and term number.')
      return
    }
    setValidationError(null)
    submitMutation.reset()
    let termId: number | null = resolvedId
    const result = await submitMutation.execute(async () => {
      if (isEdit && termId) {
        await api.put(`/terms/${termId}`, {
          start_date: startDate || null,
          end_date: endDate || null,
        })
      } else {
        const r = await api.post<{ data: { id: number } }>('/terms', {
          year: Number(year),
          term_number: Number(termNumber),
          start_date: startDate || null,
          end_date: endDate || null,
        })
        termId = r.data.data.id
      }
      if (!termId) throw new Error('Term id not returned')
      await Promise.all([
        api.put(`/terms/${termId}/price-settings`, {
          price_settings: priceSettings.map((e) => ({
            grade: e.grade,
            school_fee_amount: e.school_fee_amount || 0,
          })),
        }),
        api.put(`/terms/${termId}/transport-pricing`, {
          transport_pricings: transportPricing.map((e) => ({
            zone_id: e.zone_id,
            transport_fee_amount: e.transport_fee_amount || 0,
          })),
        }),
      ])
      return { data: { data: { id: termId } } }
    })
    if (result != null) navigate(`/billing/terms/${result.id}`)
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

      {displayError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {displayError}
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
