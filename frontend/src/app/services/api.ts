import axios, { AxiosError } from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'
import {
  clearAuth,
  getAccessToken,
  getRefreshToken,
  updateTokens,
} from '../auth/authStorage'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api = axios.create({ baseURL })

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let pendingRequests: Array<(token: string | null) => void> = []

const resolvePending = (token: string | null) => {
  pendingRequests.forEach((callback) => callback(token))
  pendingRequests = []
}

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
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push((token) => {
            if (!token) {
              reject(error)
              return
            }
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(api(originalRequest))
          })
        })
      }

      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        clearAuth()
        window.location.assign('/login')
        return Promise.reject(error)
      }

      isRefreshing = true
      try {
        const response = await axios.post(`${baseURL}/auth/refresh`, {
          refresh_token: refreshToken,
        })
        const data = response.data?.data
        const newTokens = {
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          token_type: data.token_type,
        }
        updateTokens(newTokens)
        isRefreshing = false
        resolvePending(newTokens.access_token)
        originalRequest._retry = true
        originalRequest.headers.Authorization = `Bearer ${newTokens.access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        isRefreshing = false
        resolvePending(null)
        clearAuth()
        window.location.assign('/login')
        return Promise.reject(refreshError)
      }
    }

    if (status === 403) {
      window.location.assign('/access-denied')
    }

    return Promise.reject(error)
  }
)
