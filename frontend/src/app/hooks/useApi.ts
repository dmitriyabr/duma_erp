import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'

interface UseApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

interface UseApiResult<T> extends UseApiState<T> {
  refetch: () => Promise<void>
  reset: () => void
}

/**
 * Universal API hook that properly handles 401 errors and token refresh.
 *
 * 401 errors are handled by axios interceptor (token refresh + retry),
 * so they are NOT treated as errors in the component - loading continues
 * until the retry succeeds or fails with a different error.
 *
 * Request is keyed by url + JSON.stringify(options). Pass stable options
 * (e.g. via useMemo) so that the same params do not trigger extra refetches.
 *
 * @example
 * const { data, loading, error, refetch } = useApi<MyData[]>('/api/endpoint')
 */
export function useApi<T>(
  url: string | null,
  options?: Record<string, unknown>,
  deps: unknown[] = []
): UseApiResult<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  })

  const fetchData = useCallback(async () => {
    if (!url) {
      setState({ data: null, loading: false, error: null })
      return
    }

    setState((prev) => ({ ...prev, loading: true, error: null }))

    try {
      const { api } = await import('../services/api')
      const response = await api.get<{ success: boolean; data: T }>(url, options)
      setState({ data: response.data.data, loading: false, error: null })
    } catch (err) {
      // 401 errors are handled by interceptor (token refresh + retry)
      // If we're here with 401, it means refresh failed → user will be redirected to login
      // So we can safely ignore 401 and not show error to user
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        // Token refresh is in progress or failed - don't show error
        setState((prev) => ({ ...prev, loading: false }))
        return
      }

      const message = axios.isAxiosError(err)
        ? err.response?.data?.message || err.message
        : 'An unexpected error occurred'

      setState({ data: null, loading: false, error: message })
    }
  }, [url, JSON.stringify(options)])

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null })
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData, ...deps])

  return {
    ...state,
    refetch: fetchData,
    reset,
  }
}

/**
 * Hook for manual API calls (mutations - POST, PUT, DELETE).
 * Does not auto-fetch on mount.
 *
 * @example
 * const { execute, loading, error } = useApiMutation<Result>()
 * const handleSubmit = async () => {
 *   const result = await execute(() => api.post('/endpoint', data))
 *   if (result) { ... }
 * }
 */
export function useApiMutation<T>() {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  })

  const execute = useCallback(
    async (apiCall: () => Promise<{ data: { data: T } }>): Promise<T | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }))

      try {
        const response = await apiCall()
        setState({ data: response.data.data, loading: false, error: null })
        return response.data.data
      } catch (err) {
        // Same 401 handling as useApi
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          setState((prev) => ({ ...prev, loading: false }))
          return null
        }

        const message = axios.isAxiosError(err)
          ? err.response?.data?.message || err.message
          : 'An unexpected error occurred'

        setState({ data: null, loading: false, error: message })
        return null
      }
    },
    []
  )

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null })
  }, [])

  return {
    ...state,
    execute,
    reset,
  }
}
