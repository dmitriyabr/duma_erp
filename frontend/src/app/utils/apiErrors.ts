import axios from 'axios'
import type { ApiErrorDetail, ApiErrorResponse } from '../types/api'

export interface ParsedApiError {
  message: string
  errors: ApiErrorDetail[]
}

function normalizeErrorDetail(detail: unknown): ApiErrorDetail | null {
  if (!detail || typeof detail !== 'object') return null
  const value = detail as { field?: unknown; message?: unknown }
  if (typeof value.message !== 'string' || !value.message.trim()) return null
  return {
    field: typeof value.field === 'string' ? value.field : null,
    message: value.message,
  }
}

export function parseApiError(error: unknown): ParsedApiError {
  if (!axios.isAxiosError(error)) {
    return {
      message: 'An unexpected error occurred',
      errors: [],
    }
  }

  const errorData = error.response?.data as Partial<ApiErrorResponse> | undefined
  const detailData = error.response?.data as { detail?: unknown } | undefined
  const details = Array.isArray(errorData?.errors)
    ? errorData.errors
        .map(normalizeErrorDetail)
        .filter((detail): detail is ApiErrorDetail => detail !== null)
    : []
  const detailMessage =
    typeof detailData?.detail === 'string'
      ? detailData.detail
      : null
  const message =
    (typeof errorData?.message === 'string' && errorData.message.trim()) ||
    detailMessage ||
    error.message ||
    'An unexpected error occurred'

  return {
    message,
    errors: details,
  }
}
