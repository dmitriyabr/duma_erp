import axios, { AxiosError } from 'axios'
import type { AxiosResponse } from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'
import {
  clearAuth,
  getAccessToken,
  getRefreshToken,
  updateTokens,
} from '../auth/authStorage'
import type { ApiResponse } from '../types/api'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** Minutes before expiry to refresh token proactively */
const REFRESH_BEFORE_EXPIRY_MIN = 2

export const api = axios.create({ baseURL })

/**
 * Unwrap API response: get response.data.data. Use in mutation callbacks instead of
 * (r.data as { data: T }).data. For void/empty responses returns true.
 */
export function unwrapResponse<T>(response: AxiosResponse<ApiResponse<T>>): T {
  const body = response.data
  return body?.data !== undefined ? body.data : (true as unknown as T)
}

function getTokenExpiration(token: string): number | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))
    ) as { exp?: number }
    return payload.exp ?? null
  } catch {
    return null
  }
}

function isTokenExpiringSoon(token: string): boolean {
  const exp = getTokenExpiration(token)
  if (!exp) return true
  const marginMs = REFRESH_BEFORE_EXPIRY_MIN * 60 * 1000
  return exp * 1000 <= Date.now() + marginMs
}

let refreshPromise: Promise<string | null> | null = null

/**
 * Refresh access token using refresh_token. Shared by request (proactive) and response (401) interceptors.
 * Returns new access_token or null (and redirects to login on failure).
 */
async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  const refresh = getRefreshToken()
  if (!refresh) {
    clearAuth()
    window.location.assign('/login')
    return null
  }
  refreshPromise = (async () => {
    try {
      const response = await axios.post<ApiResponse<{ access_token: string; refresh_token: string; token_type: string }>>(
        `${baseURL}/auth/refresh`,
        { refresh_token: refresh }
      )
      const data = response.data?.data
      if (!data) return null
      const newTokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        token_type: data.token_type ?? 'bearer',
      }
      updateTokens(newTokens)
      return newTokens.access_token
    } catch {
      clearAuth()
      window.location.assign('/login')
      return null
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

/** Get valid access token, refreshing proactively if expiring within REFRESH_BEFORE_EXPIRY_MIN. */
async function ensureValidAccessToken(): Promise<string | null> {
  const token = getAccessToken()
  if (!token) return null
  if (!isTokenExpiringSoon(token)) return token
  return refreshAccessToken()
}

api.interceptors.request.use(async (config) => {
  const token = await ensureValidAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status
    const originalRequest = error.config as (InternalAxiosRequestConfig & {
      _retry?: boolean
    })

    if (status === 401 && originalRequest) {
      if (originalRequest._retry) {
        return Promise.reject(error)
      }
      const token = await refreshAccessToken()
      if (!token) {
        return Promise.reject(error)
      }
      originalRequest._retry = true
      originalRequest.headers.Authorization = `Bearer ${token}`
      return api(originalRequest)
    }

    if (status === 403) {
      window.location.assign('/access-denied')
    }

    return Promise.reject(error)
  }
)
