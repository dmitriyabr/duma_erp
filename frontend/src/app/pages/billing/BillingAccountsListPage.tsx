import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useApi } from '../../hooks/useApi'
import { canManageBillingAccounts } from '../../utils/permissions'
import { formatMoney } from '../../utils/format'
import type { PaginatedResponse } from '../../types/api'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TablePagination, TableRow } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Spinner } from '../../components/ui/Spinner'

interface BillingAccountRow {
  id: number
  account_number: string
  display_name: string
  account_type: string
  primary_guardian_name?: string | null
  primary_guardian_phone?: string | null
  member_count: number
  available_balance: number
  outstanding_debt: number
  balance: number
}

export const BillingAccountsListPage = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = canManageBillingAccounts(user)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(50)
  const [search, setSearch] = useState('')

  const url = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page + 1),
      limit: String(limit),
    })
    if (search.trim()) params.set('search', search.trim())
    return `/billing-accounts?${params.toString()}`
  }, [page, limit, search])

  const { data, loading, error } = useApi<PaginatedResponse<BillingAccountRow>>(url)
  const rows = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div>
      <div className="flex justify-between items-center gap-4 mb-4 flex-wrap">
        <div>
          <Typography variant="h4">Billing accounts</Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            Parent / guardian payment accounts that can pay and auto-allocate across one or more students.
          </Typography>
        </div>
        {canManage && (
          <Button variant="contained" onClick={() => navigate('/students/new')}>
            New admission
          </Button>
        )}
      </div>

      <div className="max-w-[340px] mb-4">
        <Input
          label="Search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(0)
          }}
          placeholder="Account, contact, student"
        />
      </div>

      {error && (
        <Alert severity="error" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Account</TableHeaderCell>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Members</TableHeaderCell>
              <TableHeaderCell>Billing contact</TableHeaderCell>
              <TableHeaderCell align="right">Credit</TableHeaderCell>
              <TableHeaderCell align="right">Debt</TableHeaderCell>
              <TableHeaderCell align="right">Net</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-mono text-xs">{row.account_number}</TableCell>
                <TableCell>{row.display_name}</TableCell>
                <TableCell className="capitalize">{row.account_type}</TableCell>
                <TableCell>{row.member_count}</TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span>{row.primary_guardian_name ?? '—'}</span>
                    <span className="text-xs text-slate-500">{row.primary_guardian_phone ?? '—'}</span>
                  </div>
                </TableCell>
                <TableCell align="right">{formatMoney(row.available_balance)}</TableCell>
                <TableCell align="right">{formatMoney(row.outstanding_debt)}</TableCell>
                <TableCell align="right">{formatMoney(row.balance)}</TableCell>
                <TableCell align="right">
                  <div className="flex gap-2 justify-end">
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => navigate(`/billing/families/${row.id}`)}
                    >
                      View
                    </Button>
                    {canManage && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() =>
                          navigate('/payments/new', {
                            state: {
                              billingAccountId: row.id,
                              billingAccountName: row.display_name,
                            },
                          })
                        }
                      >
                        Pay
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <td colSpan={9} className="px-4 py-8 text-center">
                  <Spinner size="medium" />
                </td>
              </TableRow>
            )}
            {!rows.length && !loading && (
              <TableRow>
                <td colSpan={9} className="px-4 py-8 text-center">
                  <Typography color="secondary">No billing accounts found</Typography>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(nextLimit) => {
            setLimit(nextLimit)
            setPage(0)
          }}
        />
      </div>
    </div>
  )
}
