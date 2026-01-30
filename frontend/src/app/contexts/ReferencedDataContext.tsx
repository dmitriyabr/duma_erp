import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from 'react'
import { useApi } from '../hooks/useApi'

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
  const gradesApi = useApi<GradeRef[]>(gradesUrl, gradesParams, [])
  const zonesApi = useApi<TransportZoneRef[]>(zonesUrl, zonesParams, [])

  const grades = gradesApi.data ?? []
  const transportZones = zonesApi.data ?? []
  const loading = gradesApi.loading || zonesApi.loading
  const error = gradesApi.error ?? zonesApi.error ?? null

  const refetchGrades = useCallback(() => gradesApi.refetch(), [gradesApi.refetch])
  const refetchTransportZones = useCallback(() => zonesApi.refetch(), [zonesApi.refetch])
  const refetchAll = useCallback(async () => {
    await Promise.all([gradesApi.refetch(), zonesApi.refetch()])
  }, [gradesApi.refetch, zonesApi.refetch])

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
