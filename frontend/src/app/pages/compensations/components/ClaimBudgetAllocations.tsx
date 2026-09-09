import { Typography } from '../../../components/ui/Typography'
import { formatMoney } from '../../../utils/format'

export interface ClaimBudgetAllocation {
  id: number
  advance_id: number
  advance_number: string
  allocated_amount: number
  allocation_status: string
  released_reason: string | null
}

function AllocationList({ allocations }: { allocations: ClaimBudgetAllocation[] }) {
  return (
    <div className="space-y-2">
      {allocations.map((allocation) => (
        <div key={allocation.id} className="rounded-lg border border-slate-200 p-3">
          <Typography variant="body2" className="font-medium">
            {allocation.advance_number} · {formatMoney(allocation.allocated_amount)}
          </Typography>
          <Typography variant="caption" color="secondary">
            {allocation.allocation_status}
            {allocation.released_reason ? ` · ${allocation.released_reason}` : ''}
          </Typography>
        </div>
      ))}
    </div>
  )
}

export function ClaimBudgetAllocations({ allocations }: { allocations: ClaimBudgetAllocation[] }) {
  if (!allocations.length) return null

  const current = allocations.filter((allocation) => allocation.allocation_status !== 'released')
  const history = allocations
    .filter((allocation) => allocation.allocation_status === 'released')
    .sort((a, b) => b.id - a.id)

  return (
    <div className="mb-6">
      <Typography variant="subtitle2" color="secondary" className="mb-2">
        Budget allocations
      </Typography>
      {current.length ? (
        <AllocationList allocations={current} />
      ) : (
        <Typography variant="body2" color="secondary">No active allocations</Typography>
      )}
      {history.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-slate-500">
            Released allocations history ({history.length})
          </summary>
          <div className="mt-2">
            <AllocationList allocations={history} />
          </div>
        </details>
      )}
    </div>
  )
}
