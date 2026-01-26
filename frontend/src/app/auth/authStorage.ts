export type UserRole = 'SuperAdmin' | 'Admin' | 'User' | 'Accountant'

export interface AuthUser {
  id: number
  email: string
  full_name: string
  role: UserRole
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface StoredAuth {
  user: AuthUser
  tokens: AuthTokens
}

const AUTH_KEY = 'erp_auth'

const readStorage = (storage: Storage): StoredAuth | null => {
  const raw = storage.getItem(AUTH_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as StoredAuth
  } catch {
    storage.removeItem(AUTH_KEY)
    return null
  }
}

export const getStoredAuth = (): StoredAuth | null => {
  return readStorage(localStorage) ?? readStorage(sessionStorage)
}

const getStorageWithAuth = (): Storage | null => {
  if (localStorage.getItem(AUTH_KEY)) {
    return localStorage
  }
  if (sessionStorage.getItem(AUTH_KEY)) {
    return sessionStorage
  }
  return null
}

export const saveAuth = (auth: StoredAuth, remember: boolean) => {
  const storage = remember ? localStorage : sessionStorage
  const otherStorage = remember ? sessionStorage : localStorage
  otherStorage.removeItem(AUTH_KEY)
  storage.setItem(AUTH_KEY, JSON.stringify(auth))
}

export const updateTokens = (tokens: AuthTokens) => {
  const storage = getStorageWithAuth()
  if (!storage) {
    return
  }
  const current = readStorage(storage)
  if (!current) {
    return
  }
  storage.setItem(
    AUTH_KEY,
    JSON.stringify({
      ...current,
      tokens,
    })
  )
}

export const clearAuth = () => {
  localStorage.removeItem(AUTH_KEY)
  sessionStorage.removeItem(AUTH_KEY)
}

export const getAccessToken = () => {
  return getStoredAuth()?.tokens.access_token ?? null
}

export const getRefreshToken = () => {
  return getStoredAuth()?.tokens.refresh_token ?? null
}
