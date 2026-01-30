import { Alert, Box, Button, Tab, Tabs } from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
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

  const handleTabChange = (_: React.SyntheticEvent, value: string) => {
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
        <InvoicesTab
          studentId={resolvedId}
          onError={handleError}
          onDebtChange={handleBalanceChange}
          initialInvoices={invoicesApi.data?.items ?? null}
          invoicesLoading={invoicesApi.loading}
        />
      </TabPanel>

      <TabPanel active={tab} name="payments">
        <PaymentsTab
          studentId={resolvedId}
          onError={handleError}
          onBalanceChange={handleBalanceChange}
          onAllocationResult={setAllocationResult}
          initialInvoices={invoicesApi.data?.items ?? null}
          invoicesLoading={invoicesApi.loading}
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
