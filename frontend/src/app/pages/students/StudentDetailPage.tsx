import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { INVOICE_LIST_LIMIT } from '../../constants/pagination'
import { useReferencedData } from '../../contexts/ReferencedDataContext'
import { useApi } from '../../hooks/useApi'
import { InvoicesTab } from './components/InvoicesTab'
import { ItemsToIssueTab } from './components/ItemsToIssueTab'
import { OverviewTab } from './components/OverviewTab'
import { PaymentsTab } from './components/PaymentsTab'
import { StatementTab } from './components/StatementTab'
import { StudentHeader } from './components/StudentHeader'
import type {
  InvoiceSummary,
  PaginatedResponse,
  StudentBalance,
  StudentResponse,
} from './types'
import { parseNumber } from './types'
import { Alert } from '../../components/ui/Alert'
import { Tabs, TabsList, Tab, TabPanel } from '../../components/ui/Tabs'

export const StudentDetailPage = () => {
  const { studentId } = useParams()
  // const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const resolvedId = Number(studentId)

  const { data: student, error: studentError, refetch: refetchStudent } = useApi<StudentResponse>(
    resolvedId ? `/students/${resolvedId}` : null
  )
  const { data: balance, refetch: refetchBalance } = useApi<StudentBalance>(
    resolvedId ? `/payments/students/${resolvedId}/balance` : null
  )
  const { grades, transportZones } = useReferencedData()

  const invoicesApi = useApi<PaginatedResponse<InvoiceSummary>>(
    resolvedId ? '/invoices' : null,
    {
      params: { student_id: resolvedId, limit: INVOICE_LIST_LIMIT, page: 1 },
    },
    [resolvedId]
  )

  const debt = balance != null ? parseNumber(balance.outstanding_debt) : 0

  const [error, setError] = useState<string | null>(null)
  const tabParam = searchParams.get('tab') ?? 'overview'
  const tab = ['overview', 'invoices', 'payments', 'items', 'statement'].includes(tabParam)
    ? tabParam
    : 'overview'
  const [allocationResult, setAllocationResult] = useState<string | null>(null)

  const loadStudent = useCallback(async () => {
    refetchStudent()
  }, [refetchStudent])

  const loadBalance = useCallback(async () => {
    refetchBalance()
  }, [refetchBalance])

  useEffect(() => {
    if (studentError) {
      setError('Failed to load student.')
    }
  }, [studentError])

  const handleBalanceChange = useCallback(() => {
    loadBalance()
    invoicesApi.refetch()
  }, [loadBalance, invoicesApi.refetch])

  useEffect(() => {
    loadStudent()
    loadBalance()
  }, [resolvedId, loadStudent, loadBalance])

  const handleTabChange = (value: string) => {
    if (value === 'overview') {
      setSearchParams({})
    } else {
      setSearchParams({ tab: value })
    }
  }

  const handleError = (message: string) => {
    setError(message)
  }

  const handleDebtChange = () => {
    handleBalanceChange()
  }

  const handleAllocationResult = (message: string) => {
    setAllocationResult(message)
    setTimeout(() => setAllocationResult(null), 5000)
  }

  if (!student) {
    return (
      <div>
        {error && <Alert severity="error">{error}</Alert>}
      </div>
    )
  }

  return (
    <div>
      {error && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {allocationResult && (
        <Alert severity="success" className="mb-4" onClose={() => setAllocationResult(null)}>
          {allocationResult}
        </Alert>
      )}

      <StudentHeader
        student={student}
        balance={balance}
        debt={debt}
        grades={grades}
        transportZones={transportZones}
        onStudentUpdate={loadStudent}
        onError={handleError}
      />

      <Tabs value={tab} onChange={handleTabChange} className="mt-6">
        <TabsList>
          <Tab value="overview">Overview</Tab>
          <Tab value="invoices">Invoices</Tab>
          <Tab value="payments">Payments</Tab>
          <Tab value="items">Items to issue</Tab>
          <Tab value="statement">Statement</Tab>
        </TabsList>

        <TabPanel value="overview">
          <OverviewTab student={student} studentId={resolvedId} onError={handleError} />
        </TabPanel>

        <TabPanel value="invoices">
          <InvoicesTab
            studentId={resolvedId}
            onError={handleError}
            onDebtChange={handleDebtChange}
            initialInvoices={invoicesApi.data?.items ?? null}
            invoicesLoading={invoicesApi.loading}
          />
        </TabPanel>

        <TabPanel value="payments">
          <PaymentsTab
            studentId={resolvedId}
            onError={handleError}
            onBalanceChange={handleBalanceChange}
            onAllocationResult={handleAllocationResult}
            initialInvoices={invoicesApi.data?.items ?? null}
            invoicesLoading={invoicesApi.loading}
          />
        </TabPanel>

        <TabPanel value="items">
          <ItemsToIssueTab studentId={resolvedId} onError={handleError} />
        </TabPanel>

        <TabPanel value="statement">
          <StatementTab studentId={resolvedId} onError={handleError} />
        </TabPanel>
      </Tabs>
    </div>
  )
}
