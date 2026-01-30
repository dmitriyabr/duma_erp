/**
 * Shared API response types. Use these instead of local copies.
 */

export interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
}


export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages?: number
}
