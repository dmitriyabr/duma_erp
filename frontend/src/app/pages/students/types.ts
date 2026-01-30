export type Gender = 'male' | 'female'
export type StudentStatus = 'active' | 'inactive'
export type DiscountValueType = 'fixed' | 'percentage'

export interface StudentResponse {
  id: number
  student_number: string
  first_name: string
  last_name: string
  full_name: string
  date_of_birth?: string | null
  gender: Gender
  grade_id: number
  grade_name?: string | null
  transport_zone_id?: number | null
  transport_zone_name?: string | null
  guardian_name: string
  guardian_phone: string
  guardian_email?: string | null
  status: StudentStatus
  enrollment_date?: string | null
  notes?: string | null
}

export interface StudentBalance {
  student_id: number
  total_payments: number
  total_allocated: number
  available_balance: number
  outstanding_debt: number
  balance: number // net: available_balance − outstanding_debt (computed on backend)
}

export interface InvoiceSummary {
  id: number
  invoice_number: string
  invoice_type: string
  status: string
  total: number
  paid_total: number
  amount_due: number
  issue_date?: string | null
  due_date?: string | null
}

export interface InvoiceLine {
  id: number
  description: string
  quantity: number
  unit_price: number
  line_total: number
  discount_amount: number
  net_amount: number
  paid_amount: number
  remaining_amount: number
}

export interface InvoiceDetail extends InvoiceSummary {
  notes?: string | null
  lines: InvoiceLine[]
}

export interface PaymentResponse {
  id: number
  payment_number: string
  receipt_number?: string | null
  amount: number
  payment_method: string
  payment_date: string
  reference?: string | null
  confirmation_attachment_id?: number | null
  status: string
  notes?: string | null
  created_at: string
}

export interface ReservationItem {
  id: number
  item_id: number
  item_name?: string | null
  item_sku?: string | null
  quantity_required: number
  quantity_reserved: number
  quantity_issued: number
}

export interface ReservationResponse {
  id: number
  invoice_id?: number | null
  invoice_line_id?: number | null
  status: string
  created_at: string
  items: ReservationItem[]
}

export interface StudentDiscountResponse {
  id: number
  applies_to: string
  value_type: string
  value: number
  reason_text?: string | null
  reason_name?: string | null
  is_active: boolean
}

export interface StatementEntry {
  date: string
  description: string
  reference?: string | null
  credit?: number | null
  debit?: number | null
  balance: number
}

export interface StatementResponse {
  opening_balance: number
  closing_balance: number
  total_credits: number
  total_debits: number
  entries: StatementEntry[]
}

export interface ItemOption {
  id: number
  name: string
  sku_code: string
  price: number
}

export interface KitOption {
  id: number
  name: string
  price: number
}

export interface GradeOption {
  id: number
  name: string
}

export interface TransportZoneOption {
  id: number
  zone_name: string
}

export type { ApiResponse, PaginatedResponse } from '../../types/api'

export const parseNumber = (value: unknown): number => {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? 0 : parsed
  }
  return 0
}

export const getDefaultDueDate = (): string => {
  const date = new Date()
  date.setMonth(date.getMonth() + 1)
  return date.toISOString().slice(0, 10)
}

export const getMonthToDateRange = (): { date_from: string; date_to: string } => {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  return {
    date_from: start.toISOString().slice(0, 10),
    date_to: now.toISOString().slice(0, 10),
  }
}
