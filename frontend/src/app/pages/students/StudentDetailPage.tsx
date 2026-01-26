import { Alert, Box, Button, Tab, Tabs } from '@mui/material'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../services/api'
import { InvoicesTab } from './components/InvoicesTab'
import { ItemsToIssueTab } from './components/ItemsToIssueTab'
import { OverviewTab } from './components/OverviewTab'
import { PaymentsTab } from './components/PaymentsTab'
import { StatementTab } from './components/StatementTab'
import { StudentHeader } from './components/StudentHeader'
import type {
  ApiResponse,
  GradeOption,
  InvoiceSummary,
  PaginatedResponse,
  StudentBalance,
  StudentResponse,
  TransportZoneOption,
} from './types'
import { parseNumber } from './types'

const TabPanel = ({
  active,
  name,
  children,
}: {
  active: string
  name: string
  children: React.ReactNode
}) => {
  if (active !== name) {
    return null
  }
  return <Box sx={{ mt: 2 }}>{children}</Box>
}

export const StudentDetailPage = () => {
  const { studentId } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const resolvedId = Number(studentId)

  const [student, setStudent] = useState<StudentResponse | null>(null)
  const [balance, setBalance] = useState<StudentBalance | null>(null)
  const [debt, setDebt] = useState(0)
  const [_loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState('overview')
  const [grades, setGrades] = useState<GradeOption[]>([])
  const [transportZones, setTransportZones] = useState<TransportZoneOption[]>([])
  const [allocationResult, setAllocationResult] = useState<string | null>(null)

  const loadStudent = useCallback(async () => {
    if (!resolvedId) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<StudentResponse>>(`/students/${resolvedId}`)
      setStudent(response.data.data)
    } catch {
      setError('Failed to load student.')
    } finally {
      setLoading(false)
    }
  }, [resolvedId])

  const loadReferenceData = async () => {
    try {
      const [gradeResponse, zoneResponse] = await Promise.all([
        api.get<ApiResponse<GradeOption[]>>('/students/grades', { params: { include_inactive: true } }),
        api.get<ApiResponse<TransportZoneOption[]>>('/terms/transport-zones', {
          params: { include_inactive: true },
        }),
      ])
      setGrades(gradeResponse.data.data)
      setTransportZones(zoneResponse.data.data)
    } catch {
      setError('Failed to load reference data.')
    }
  }

  const loadBalance = useCallback(async () => {
    if (!resolvedId) return
    try {
      const response = await api.get<ApiResponse<StudentBalance>>(
        `/payments/students/${resolvedId}/balance`
      )
      setBalance(response.data.data)
    } catch {
      setError('Failed to load balance.')
    }
  }, [resolvedId])

  const refreshDebt = useMemo(() => {
    return async () => {
      if (!resolvedId) return
      try {
        const response = await api.get<ApiResponse<PaginatedResponse<InvoiceSummary>>>('/invoices', {
          params: { student_id: resolvedId, limit: 200, page: 1 },
        })
        const totalDue = response.data.data.items.reduce((sum, invoice) => {
          const status = invoice.status?.toLowerCase()
          if (status === 'paid' || status === 'cancelled' || status === 'void') {
            return sum
          }
          return sum + parseNumber(invoice.amount_due)
        }, 0)
        setDebt(totalDue)
      } catch {
        setDebt(0)
      }
    }
  }, [resolvedId])

  const handleBalanceChange = useCallback(() => {
    loadBalance()
    refreshDebt()
  }, [loadBalance, refreshDebt])

  useEffect(() => {
    loadStudent()
    loadBalance()
    refreshDebt()
    loadReferenceData()
  }, [resolvedId, loadStudent, loadBalance, refreshDebt])

  useEffect(() => {
    const nextTab = searchParams.get('tab') ?? 'overview'
    if (nextTab !== tab) {
      setTab(nextTab)
    }
  }, [searchParams, tab])

  const handleTabChange = (_: React.SyntheticEvent, value: string) => {
    setTab(value)
    if (value === 'overview') {
      setSearchParams({})
    } else {
      setSearchParams({ tab: value })
    }
  }

  const handleError = (message: string) => {
    setError(message)
  }

  if (!resolvedId) {
    return (
      <Box>
        <Alert severity="error">Invalid student ID.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Button onClick={() => navigate('/students')} sx={{ mb: 2 }}>
        Back to students
      </Button>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      {student ? (
        <StudentHeader
          student={student}
          balance={balance}
          debt={debt}
          grades={grades}
          transportZones={transportZones}
          onStudentUpdate={loadStudent}
          onError={handleError}
        />
      ) : null}

      {allocationResult ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          {allocationResult}
        </Alert>
      ) : null}

      <Tabs value={tab} onChange={handleTabChange}>
        <Tab label="Overview" value="overview" />
        <Tab label="Invoices" value="invoices" />
        <Tab label="Payments" value="payments" />
        <Tab label="Items to Issue" value="items" />
        <Tab label="Statement" value="statement" />
      </Tabs>

      <TabPanel active={tab} name="overview">
        {student ? (
          <OverviewTab student={student} studentId={resolvedId} onError={handleError} />
        ) : null}
      </TabPanel>

      <TabPanel active={tab} name="invoices">
        <InvoicesTab studentId={resolvedId} onError={handleError} onDebtChange={handleBalanceChange} />
      </TabPanel>

      <TabPanel active={tab} name="payments">
        <PaymentsTab
          studentId={resolvedId}
          onError={handleError}
          onBalanceChange={handleBalanceChange}
          onAllocationResult={setAllocationResult}
        />
      </TabPanel>

      <TabPanel active={tab} name="items">
        <ItemsToIssueTab studentId={resolvedId} onError={handleError} />
      </TabPanel>

      <TabPanel active={tab} name="statement">
        <StatementTab studentId={resolvedId} onError={handleError} />
      </TabPanel>
    </Box>
  )
}
