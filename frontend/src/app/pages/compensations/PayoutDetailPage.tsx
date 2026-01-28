import {
  Alert,
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../../services/api'
import { openAttachmentInNewTab } from '../../utils/attachments'
import { formatDate, formatMoney } from '../../utils/format'

interface ApiResponse<T> {
  success: boolean
  data: T
}

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
  const [payout, setPayout] = useState<PayoutResponse | null>(null)
  const [claims, setClaims] = useState<Map<number, ClaimRow>>(new Map())
  const [_loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPayout = useCallback(async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<PayoutResponse>>(
        `/compensations/payouts/${resolvedId}`
      )
      const payoutData = response.data.data
      setPayout(payoutData)

      // Загружаем данные claims для отображения
      const claimIds = payoutData.allocations.map((a) => a.claim_id)
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
    } catch {
      setError('Failed to load payout.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  useEffect(() => {
    loadPayout()
  }, [loadPayout])

  if (!payout) {
    return (
      <Box>
        {error ? <Alert severity="error">{error}</Alert> : null}
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {payout.payout_number}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {formatDate(payout.payout_date)} · {formatMoney(payout.amount)}
          </Typography>
        </Box>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Amount
          </Typography>
          <Typography variant="h6">{formatMoney(payout.amount)}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Payment method
          </Typography>
          <Typography>{payout.payment_method}</Typography>
        </Box>
        <Box>
          <Typography variant="subtitle2" color="text.secondary">
            Reference number
          </Typography>
          <Typography>{payout.reference_number ?? '—'}</Typography>
        </Box>
      </Box>

      {payout.proof_text ? (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Proof
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{payout.proof_text}</Typography>
        </Box>
      ) : null}
      {payout.proof_attachment_id ? (
        <Box sx={{ mb: 3 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={() => openAttachmentInNewTab(payout.proof_attachment_id!)}
          >
            View confirmation file
          </Button>
        </Box>
      ) : null}

      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Allocations
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Claim Number</TableCell>
              <TableCell align="right">Allocated Amount</TableCell>
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
            {!payout.allocations.length ? (
              <TableRow>
                <TableCell colSpan={2} align="center">
                  No allocations
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Box>
    </Box>
  )
}
