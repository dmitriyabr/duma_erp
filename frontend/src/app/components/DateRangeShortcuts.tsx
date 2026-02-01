import { Box, ButtonGroup, Button } from '@mui/material'

export type DateRangePreset = 'this_year' | 'this_month' | '30_days' | '365_days'

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function getDateRangeForPreset(preset: DateRangePreset): { from: string; to: string } {
  const today = new Date()
  const to = toISODate(today)
  let from: string
  switch (preset) {
    case 'this_year':
      from = toISODate(new Date(today.getFullYear(), 0, 1))
      break
    case 'this_month':
      from = toISODate(new Date(today.getFullYear(), today.getMonth(), 1))
      break
    case '30_days': {
      const d = new Date(today)
      d.setDate(d.getDate() - 30)
      from = toISODate(d)
      break
    }
    case '365_days': {
      const d = new Date(today)
      d.setDate(d.getDate() - 365)
      from = toISODate(d)
      break
    }
    default:
      from = to
  }
  return { from, to }
}

interface DateRangeShortcutsProps {
  dateFrom: string
  dateTo: string
  onRangeChange: (from: string, to: string) => void
  onRun?: () => void
}

export function DateRangeShortcuts({ dateFrom, dateTo, onRangeChange, onRun }: DateRangeShortcutsProps) {
  const apply = (preset: DateRangePreset) => {
    const { from, to } = getDateRangeForPreset(preset)
    onRangeChange(from, to)
    onRun?.()
  }

  const currentPreset = (): DateRangePreset | null => {
    const { from: yFrom, to: yTo } = getDateRangeForPreset('this_year')
    if (dateFrom === yFrom && dateTo === yTo) return 'this_year'
    const { from: mFrom, to: mTo } = getDateRangeForPreset('this_month')
    if (dateFrom === mFrom && dateTo === mTo) return 'this_month'
    const { from: d30From, to: d30To } = getDateRangeForPreset('30_days')
    if (dateFrom === d30From && dateTo === d30To) return '30_days'
    const { from: d365From, to: d365To } = getDateRangeForPreset('365_days')
    if (dateFrom === d365From && dateTo === d365To) return '365_days'
    return null
  }

  const active = currentPreset()

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <ButtonGroup size="small" variant="outlined">
        <Button onClick={() => apply('this_year')} color={active === 'this_year' ? 'primary' : 'inherit'}>
          This year
        </Button>
        <Button onClick={() => apply('this_month')} color={active === 'this_month' ? 'primary' : 'inherit'}>
          This month
        </Button>
        <Button onClick={() => apply('30_days')} color={active === '30_days' ? 'primary' : 'inherit'}>
          30 days
        </Button>
        <Button onClick={() => apply('365_days')} color={active === '365_days' ? 'primary' : 'inherit'}>
          365 days
        </Button>
      </ButtonGroup>
    </Box>
  )
}
