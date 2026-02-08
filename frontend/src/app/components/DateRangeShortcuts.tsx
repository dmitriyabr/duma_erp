import { Button } from './ui/Button'

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
  /** Called after range change; if provided (from, to), use these for the report (avoids stale state). */
  onRun?: (from?: string, to?: string) => void
}

export function DateRangeShortcuts({ dateFrom, dateTo, onRangeChange, onRun }: DateRangeShortcutsProps) {
  const apply = (preset: DateRangePreset) => {
    const { from, to } = getDateRangeForPreset(preset)
    onRangeChange(from, to)
    onRun?.(from, to)
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
    <div className="flex items-center gap-1 flex-wrap">
      <div className="inline-flex rounded-md border border-slate-300 overflow-hidden">
        <Button
          size="small"
          variant={active === 'this_year' ? 'contained' : 'outlined'}
          onClick={() => apply('this_year')}
          className="rounded-none border-0 first:rounded-l-md last:rounded-r-md"
        >
          This year
        </Button>
        <Button
          size="small"
          variant={active === 'this_month' ? 'contained' : 'outlined'}
          onClick={() => apply('this_month')}
          className="rounded-none border-0 first:rounded-l-md last:rounded-r-md"
        >
          This month
        </Button>
        <Button
          size="small"
          variant={active === '30_days' ? 'contained' : 'outlined'}
          onClick={() => apply('30_days')}
          className="rounded-none border-0 first:rounded-l-md last:rounded-r-md"
        >
          30 days
        </Button>
        <Button
          size="small"
          variant={active === '365_days' ? 'contained' : 'outlined'}
          onClick={() => apply('365_days')}
          className="rounded-none border-0 first:rounded-l-md last:rounded-r-md"
        >
          365 days
        </Button>
      </div>
    </div>
  )
}
