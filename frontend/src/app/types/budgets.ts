import type { PaginatedResponse } from './api'

export interface BudgetSummary {
  id: number
  budget_number: string
  name: string
  purpose_id: number
  purpose_name: string | null
  period_from: string
  period_to: string
  limit_amount: number | string
  notes: string | null
  status: string
  created_by_id: number
  approved_by_id: number | null
  created_at: string
  updated_at: string
  direct_issue_total: number | string
  transfer_in_total: number | string
  returned_total: number | string
  transfer_out_total: number | string
  reserved_total: number | string
  settled_total: number | string
  committed_total: number | string
  open_on_hands_total: number | string
  available_unreserved_total: number | string
  available_to_issue: number | string
  overdue_advances_count: number
}

export interface BudgetAdvanceSummary {
  id: number
  advance_number: string
  budget_id: number
  budget_number: string
  budget_name: string
  employee_id: number
  employee_name: string
  issue_date: string
  amount_issued: number | string
  payment_method: string
  reference_number: string | null
  proof_text: string | null
  proof_attachment_id: number | null
  notes: string | null
  source_type: string
  settlement_due_date: string
  status: string
  created_by_id: number
  created_at: string
  updated_at: string
  reserved_amount: number | string
  settled_amount: number | string
  returned_amount: number | string
  transferred_out_amount: number | string
  open_balance: number | string
  available_unreserved_amount: number | string
}

export interface BudgetAdvanceReturn {
  id: number
  return_number: string
  advance_id: number
  return_date: string
  amount: number | string
  return_method: string
  reference_number: string | null
  proof_text: string | null
  proof_attachment_id: number | null
  notes: string | null
  created_by_id: number
  created_at: string
}

export interface BudgetAdvanceTransfer {
  id: number
  transfer_number: string
  from_advance_id: number
  from_advance_number: string
  to_budget_id: number
  to_budget_number: string
  to_employee_id: number
  to_employee_name: string | null
  transfer_date: string
  amount: number | string
  transfer_type: string
  reason: string
  created_to_advance_id: number
  created_to_advance_number: string
  created_by_id: number
  created_at: string
}

export interface BudgetClosureStatus {
  budget_id: number
  open_advances_count: number
  overdue_advances_count: number
  unresolved_claims_count: number
  transferable_amount_total: number | string
  can_close: boolean
  blocking_reasons: string[]
}

export interface MyBudgetAvailableBalance {
  budget_id: number
  budget_number: string
  budget_name: string
  available_unreserved_total: number | string
}

export type BudgetListResponse = PaginatedResponse<BudgetSummary>
export type BudgetAdvanceListResponse = PaginatedResponse<BudgetAdvanceSummary>
export type BudgetTransferListResponse = PaginatedResponse<BudgetAdvanceTransfer>
