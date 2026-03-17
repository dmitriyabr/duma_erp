/**
 * Shared API response types. Use these instead of local copies.
 */

export interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
}

export interface ApiErrorDetail {
  field?: string | null
  message: string
}

export interface ApiErrorResponse {
  success: false
  data: null
  message: string
  errors?: ApiErrorDetail[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages?: number
}
