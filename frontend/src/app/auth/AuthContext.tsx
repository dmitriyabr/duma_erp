import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import axios from 'axios'
import { clearAuth, getStoredAuth, saveAuth } from './authStorage'
import type { AuthTokens, AuthUser } from './authStorage'

interface LoginPayload {
  email: string
  password: string
  remember: boolean
}

interface AuthContextValue {
  user: AuthUser | null
  isLoading: boolean
  login: (payload: LoginPayload) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const getApiBaseUrl = () => {
  return import.meta.env.VITE_API_BASE_URL || '/api/v1'
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const stored = getStoredAuth()
    if (stored?.user) {
      setUser(stored.user)
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async ({ email, password, remember }: LoginPayload) => {
    const baseUrl = getApiBaseUrl()
    const response = await axios.post(`${baseUrl}/auth/login`, {
      email,
      password,
    })
    const data = response.data?.data
    const tokens: AuthTokens = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: data.token_type,
    }
    const nextUser: AuthUser = data.user
    saveAuth({ user: nextUser, tokens }, remember)
    setUser(nextUser)
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setUser(null)
    window.location.assign('/login')
  }, [])

  const value = useMemo(
    () => ({
      user,
      isLoading,
      login,
      logout,
    }),
    [user, isLoading, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
