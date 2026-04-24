import { useEffect, useMemo } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { useApi } from '../../hooks/useApi'
import type { PaginatedResponse } from '../../types/api'
import type { BudgetSummary, MyBudgetAvailableBalance } from '../../types/budgets'
import { formatMoney } from '../../utils/format'
import { Alert } from '../ui/Alert'
import { Select } from '../ui/Select'
import { Typography } from '../ui/Typography'

type FundingSource = 'personal_funds' | 'budget'

interface BudgetFundingSectionProps {
  fundingSource: FundingSource
  onFundingSourceChange: (value: FundingSource) => void
  budgetId: number | ''
  onBudgetIdChange: (value: number | '') => void
  employeeId?: number | ''
  purposeId?: number | ''
  effectiveDate?: string
  disabled?: boolean
  showFundingSource?: boolean
  requireExplicitEmployee?: boolean
  title?: string
}

export const BudgetFundingSection = ({
  fundingSource,
  onFundingSourceChange,
  budgetId,
  onBudgetIdChange,
  employeeId,
  purposeId,
  effectiveDate,
  disabled = false,
  showFundingSource = true,
  requireExplicitEmployee = false,
  title,
}: BudgetFundingSectionProps) => {
  const { user } = useAuth()
  const currentUserRole = user?.role
  const selectedEmployeeId =
    typeof employeeId === 'number'
      ? employeeId
      : requireExplicitEmployee
        ? null
        : (user?.id ?? null)

  const budgetsUrl = useMemo(() => {
    if (fundingSource !== 'budget') return null
    if (!selectedEmployeeId) return null

    if (currentUserRole === 'User') {
      return '/budgets/my/budgets'
    }

    const params = new URLSearchParams()
    params.set('page', '1')
    params.set('limit', '100')
    params.set('employee_id', String(selectedEmployeeId))
    return `/budgets?${params.toString()}`
  }, [fundingSource, selectedEmployeeId, currentUserRole])

  const { data: rawBudgetsData, loading: budgetsLoading, error: budgetsError } = useApi<
    PaginatedResponse<BudgetSummary> | BudgetSummary[]
  >(budgetsUrl, undefined, [budgetsUrl])

  const rawBudgets = useMemo(() => {
    if (!rawBudgetsData) return []
    return Array.isArray(rawBudgetsData) ? rawBudgetsData : rawBudgetsData.items
  }, [rawBudgetsData])

  const budgets = useMemo(
    () =>
      rawBudgets.filter((budget) => {
        if (!['active', 'closing'].includes(budget.status)) return false
        if (typeof purposeId === 'number' && budget.purpose_id !== purposeId) return false
        if (effectiveDate && (budget.period_from > effectiveDate || budget.period_to < effectiveDate)) return false
        return true
      }),
    [rawBudgets, purposeId, effectiveDate]
  )

  useEffect(() => {
    if (fundingSource !== 'budget') return
    if (!budgetId) return
    if (budgets.some((budget) => budget.id === budgetId)) return
    onBudgetIdChange('')
  }, [fundingSource, budgetId, budgets, onBudgetIdChange])

  const balanceUrl = useMemo(() => {
    if (fundingSource !== 'budget' || !budgetId || !selectedEmployeeId) return null
    const params = new URLSearchParams()
    if (currentUserRole === 'SuperAdmin' || currentUserRole === 'Admin') {
      params.set('employee_id', String(selectedEmployeeId))
    }
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return `/budgets/${budgetId}/my-available-balance${suffix}`
  }, [fundingSource, budgetId, selectedEmployeeId, currentUserRole])

  const { data: balance, loading: balanceLoading, error: balanceError } = useApi<MyBudgetAvailableBalance>(
    balanceUrl,
    undefined,
    [balanceUrl]
  )

  const selectedBudget = useMemo(
    () => budgets.find((budget) => budget.id === budgetId) ?? null,
    [budgets, budgetId]
  )

  return (
    <div className="md:col-span-2 space-y-3">
      {title ? (
        <div>
          <Typography variant="subtitle2">{title}</Typography>
        </div>
      ) : null}

      {showFundingSource ? (
        <Select
          label="Funding source"
          value={fundingSource}
          onChange={(e) => onFundingSourceChange(e.target.value as FundingSource)}
          disabled={disabled}
        >
          <option value="personal_funds">Personal funds (reimbursement)</option>
          <option value="budget">Budget advance</option>
        </Select>
      ) : null}

      {fundingSource === 'budget' ? (
        <>
          {!selectedEmployeeId ? (
            <Alert severity="warning">Select employee first to load available budgets.</Alert>
          ) : (
            <Select
              label="Budget"
              value={budgetId}
              onChange={(e) => onBudgetIdChange(e.target.value ? Number(e.target.value) : '')}
              disabled={disabled || budgetsLoading}
              helperText={
                budgetsLoading
                  ? 'Loading budgets...'
                  : budgets.length
                    ? undefined
                    : 'No available budgets match the selected employee, purpose, and date.'
              }
            >
              <option value="">Select budget</option>
              {budgets.map((budget) => (
                <option key={budget.id} value={budget.id}>
                  {budget.budget_number} · {budget.name}
                </option>
              ))}
            </Select>
          )}

          {budgetsError ? (
            <Alert severity="warning">{budgetsError}</Alert>
          ) : null}

          {selectedBudget ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <Typography variant="body2">
                Period: {selectedBudget.period_from} - {selectedBudget.period_to}
              </Typography>
              <Typography variant="body2">
                Purpose: {selectedBudget.purpose_name ?? '—'}
              </Typography>
              <Typography variant="body2">
                Employee available balance:{' '}
                {balanceLoading ? 'Loading…' : balance ? formatMoney(balance.available_unreserved_total) : '—'}
              </Typography>
              {balanceError ? (
                <Typography variant="caption" color="secondary" className="mt-1 block">
                  {balanceError}
                </Typography>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
