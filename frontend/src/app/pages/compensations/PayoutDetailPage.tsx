import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { useApi } from '../../hooks/useApi'
import { openAttachmentInNewTab } from '../../utils/attachments'
import type { ApiResponse } from '../../types/api'
import { formatDate, formatMoney } from '../../utils/format'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'

interface PayoutAllocation {
  id: number
  claim_id: number
  allocated_amount: number
}

interface PayoutResponse {
  id: number
  payout_number: string
  employee_id: number
  payout_date: string
  amount: number
  payment_method: string
  reference_number: string | null
  proof_text: string | null
  proof_attachment_id: number | null
  allocations: PayoutAllocation[]
}

interface ClaimRow {
  id: number
  claim_number: string
}

export const PayoutDetailPage = () => {
  const { payoutId } = useParams()
  const resolvedId = payoutId ? Number(payoutId) : null
  const { data: payout, loading, error } = useApi<PayoutResponse>(
    resolvedId ? `/compensations/payouts/${resolvedId}` : null
  )
  const [claims, setClaims] = useState<Map<number, ClaimRow>>(new Map())

  useEffect(() => {
    if (!payout) return
    // Load claims data for display
    const loadClaims = async () => {
      const claimIds = payout.allocations.map((a) => a.claim_id)
      const claimsMap = new Map<number, ClaimRow>()
      for (const claimId of claimIds) {
        try {
          const claimResponse = await api.get<ApiResponse<ClaimRow>>(
            `/compensations/claims/${claimId}`
          )
          claimsMap.set(claimId, {
            id: claimResponse.data.data.id,
            claim_number: claimResponse.data.data.claim_number,
          })
        } catch {
          // Ignore
        }
      }
      setClaims(claimsMap)
    }
    loadClaims()
  }, [payout])

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="large" />
      </div>
    )
  }

  if (!payout) {
    return (
      <div>
        {error && <Alert severity="error">{error}</Alert>}
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4 flex-wrap gap-4">
        <div>
          <Typography variant="h4">
            {payout.payout_number}
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            {formatDate(payout.payout_date)} · {formatMoney(payout.amount)}
          </Typography>
        </div>
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Payment method
          </Typography>
          <Typography>{payout.payment_method}</Typography>
        </div>
        {payout.reference_number && (
          <div>
            <Typography variant="subtitle2" color="secondary" className="mb-1">
              Reference number
            </Typography>
            <Typography>{payout.reference_number}</Typography>
          </div>
        )}
      </div>

      {payout.proof_text && (
        <div className="mb-6">
          <Typography variant="subtitle2" color="secondary" className="mb-1">
            Proof / Reference
          </Typography>
          <Typography className="whitespace-pre-wrap">{payout.proof_text}</Typography>
        </div>
      )}

      {payout.proof_attachment_id && (
        <div className="mb-6">
          <Button
            variant="outlined"
            onClick={() => openAttachmentInNewTab(payout.proof_attachment_id!)}
          >
            View confirmation file
          </Button>
        </div>
      )}

      <Typography variant="h6" className="mb-4">
        Allocations
      </Typography>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Claim Number</TableHeaderCell>
              <TableHeaderCell align="right">Allocated Amount</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payout.allocations.map((allocation) => {
              const claim = claims.get(allocation.claim_id)
              return (
                <TableRow key={allocation.id}>
                  <TableCell>{claim?.claim_number ?? `Claim #${allocation.claim_id}`}</TableCell>
                  <TableCell align="right">{formatMoney(allocation.allocated_amount)}</TableCell>
                </TableRow>
              )
            })}
            {!payout.allocations.length && (
              <TableRow>
                <td colSpan={2} className="px-4 py-8 text-center">
                  <Typography color="secondary">No allocations</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
