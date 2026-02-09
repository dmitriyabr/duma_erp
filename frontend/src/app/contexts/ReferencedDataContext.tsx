import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from 'react'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../auth/AuthContext'

export interface GradeRef {
  id: number
  code: string
  name: string
  display_order: number
  is_active: boolean
}

export interface TransportZoneRef {
  id: number
  zone_name: string
  zone_code: string
  is_active: boolean
}

interface ReferencedDataState {
  grades: GradeRef[]
  transportZones: TransportZoneRef[]
  loading: boolean
  error: string | null
}

interface ReferencedDataContextValue extends ReferencedDataState {
  refetchGrades: () => Promise<void>
  refetchTransportZones: () => Promise<void>
  refetchAll: () => Promise<void>
}

const ReferencedDataContext = createContext<ReferencedDataContextValue | undefined>(undefined)

const gradesUrl = '/students/grades'
const gradesParams = { params: { include_inactive: true } }
const zonesUrl = '/terms/transport-zones'
const zonesParams = { params: { include_inactive: true } }

export function ReferencedDataProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const role = user?.role

  // Avoid global 403 redirect loop for roles that don't have access to these endpoints.
  // (api.ts redirects to /access-denied on any 403)
  const canReadReferencedData = role !== 'User'

  const gradesApi = useApi<GradeRef[]>(canReadReferencedData ? gradesUrl : null, gradesParams, [canReadReferencedData])
  const zonesApi = useApi<TransportZoneRef[]>(canReadReferencedData ? zonesUrl : null, zonesParams, [canReadReferencedData])

  const grades = gradesApi.data ?? []
  const transportZones = zonesApi.data ?? []
  const loading = gradesApi.loading || zonesApi.loading
  const error = gradesApi.error ?? zonesApi.error ?? null

  const refetchGrades = useCallback(() => {
    if (!canReadReferencedData) return Promise.resolve()
    return gradesApi.refetch()
  }, [canReadReferencedData, gradesApi.refetch])
  const refetchTransportZones = useCallback(() => {
    if (!canReadReferencedData) return Promise.resolve()
    return zonesApi.refetch()
  }, [canReadReferencedData, zonesApi.refetch])
  const refetchAll = useCallback(async () => {
    if (!canReadReferencedData) return
    await Promise.all([gradesApi.refetch(), zonesApi.refetch()])
  }, [canReadReferencedData, gradesApi.refetch, zonesApi.refetch])

  const value = useMemo<ReferencedDataContextValue>(
    () => ({
      grades,
      transportZones,
      loading,
      error,
      refetchGrades,
      refetchTransportZones,
      refetchAll,
    }),
    [grades, transportZones, loading, error, refetchGrades, refetchTransportZones, refetchAll]
  )

  return (
    <ReferencedDataContext.Provider value={value}>
      {children}
    </ReferencedDataContext.Provider>
  )
}

export function useReferencedData() {
  const ctx = useContext(ReferencedDataContext)
  if (ctx === undefined) {
    throw new Error('useReferencedData must be used within ReferencedDataProvider')
  }
  return ctx
}

/** Optional hook: returns undefined if outside provider (e.g. on login page). */
export function useReferencedDataOptional(): ReferencedDataContextValue | undefined {
  return useContext(ReferencedDataContext)
}
