import { useState } from 'react'
import { api } from '../../services/api'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Typography } from '../../components/ui/Typography'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'

function getDefaultDateRange(): { start: string; end: string } {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

type ExportType = 'student-payments' | 'procurement-payments' | 'student-balance-changes'
type ExportTypeExtended = ExportType | 'bank-transfers' | 'bank-statement-files'

export const AccountantExportPage = () => {
  const [datesPayments, setDatesPayments] = useState(getDefaultDateRange)
  const [datesProcurement, setDatesProcurement] = useState(getDefaultDateRange)
  const [datesBalanceChanges, setDatesBalanceChanges] = useState(getDefaultDateRange)
  const [datesBankTransfers, setDatesBankTransfers] = useState(getDefaultDateRange)
  const [datesBankFiles, setDatesBankFiles] = useState(getDefaultDateRange)
  const [loadingType, setLoadingType] = useState<ExportTypeExtended | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async (
    type: ExportTypeExtended,
    startDate: string,
    endDate: string,
  ) => {
    if (!startDate || !endDate) {
      setError('Please set start date and end date.')
      return
    }
    setError(null)
    setLoadingType(type)
    try {
      const url = `/accountant/export/${type}?start_date=${startDate}&end_date=${endDate}&format=csv`
      const response = await api.get(url, { responseType: 'blob' })
      const rawBlob = response.data as Blob
      const rawText = await rawBlob.text()
      // Backend may generate absolute URLs using a localhost base. Rewrite them to the current origin
      // so links in exported CSV are usable on production.
      const rewrittenText = rawText.replace(
        /https?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?/g,
        window.location.origin
      )
      const blob = new Blob([rewrittenText], { type: 'text/csv;charset=utf-8' })
      const disposition = response.headers['content-disposition']
      const filenameMatch = disposition?.match(/filename="?([^";]+)"?/)
      const filename = filenameMatch?.[1] ?? `export_${type}_${startDate}_${endDate}.csv`
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (err: unknown) {
      const message = err && typeof err === 'object' && 'message' in err
        ? String((err as { message: string }).message)
        : 'Export failed'
      setError(message)
    } finally {
      setLoadingType((cur) => (cur === type ? null : cur))
    }
  }

  const renderExportLabel = (type: ExportTypeExtended) => {
    const isLoading = loadingType === type
    return isLoading ? (
      <span className="inline-flex items-center gap-2">
        <Spinner size="small" />
        Download CSV
      </span>
    ) : (
      'Download CSV'
    )
  }

  const isBusy = loadingType !== null

  return (
    <div>
      <Typography variant="h4" className="mb-4">
        Data Export
      </Typography>
      <Typography variant="body2" color="secondary" className="mb-6">
        Export data for accounting (QuickBooks, Xero, Excel). Select date range and download CSV.
      </Typography>

      {error && (
        <Alert severity="error" className="mb-4" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <div className="max-w-2xl flex flex-col gap-6">
        <div>
          <Typography variant="subtitle1" className="mb-2">
            Student Payments (Receipts)
          </Typography>
          <div className="flex gap-4 items-center flex-wrap mb-2">
            <div className="min-w-[180px]">
              <Input
                label="Start date"
                type="date"
                value={datesPayments.start}
                onChange={(e) => setDatesPayments((p) => ({ ...p, start: e.target.value }))}
              />
            </div>
            <div className="min-w-[180px]">
              <Input
                label="End date"
                type="date"
                value={datesPayments.end}
                onChange={(e) => setDatesPayments((p) => ({ ...p, end: e.target.value }))}
              />
            </div>
            <Button
              variant="outlined"
              onClick={() =>
                handleExport('student-payments', datesPayments.start, datesPayments.end)
              }
              disabled={isBusy}
            >
              {renderExportLabel('student-payments')}
            </Button>
          </div>
        </div>

        <div>
          <Typography variant="subtitle1" className="mb-2">
            Procurement Payments
          </Typography>
          <div className="flex gap-4 items-center flex-wrap mb-2">
            <div className="min-w-[180px]">
              <Input
                label="Start date"
                type="date"
                value={datesProcurement.start}
                onChange={(e) => setDatesProcurement((p) => ({ ...p, start: e.target.value }))}
              />
            </div>
            <div className="min-w-[180px]">
              <Input
                label="End date"
                type="date"
                value={datesProcurement.end}
                onChange={(e) => setDatesProcurement((p) => ({ ...p, end: e.target.value }))}
              />
            </div>
            <Button
              variant="outlined"
              onClick={() =>
                handleExport('procurement-payments', datesProcurement.start, datesProcurement.end)
              }
              disabled={isBusy}
            >
              {renderExportLabel('procurement-payments')}
            </Button>
          </div>
        </div>

        <div>
          <Typography variant="subtitle1" className="mb-2">
            Student Balance Changes
          </Typography>
          <div className="flex gap-4 items-center flex-wrap mb-2">
            <div className="min-w-[180px]">
              <Input
                label="Start date"
                type="date"
                value={datesBalanceChanges.start}
                onChange={(e) => setDatesBalanceChanges((p) => ({ ...p, start: e.target.value }))}
              />
            </div>
            <div className="min-w-[180px]">
              <Input
                label="End date"
                type="date"
                value={datesBalanceChanges.end}
                onChange={(e) => setDatesBalanceChanges((p) => ({ ...p, end: e.target.value }))}
              />
            </div>
            <Button
              variant="outlined"
              onClick={() =>
                handleExport('student-balance-changes', datesBalanceChanges.start, datesBalanceChanges.end)
              }
              disabled={isBusy}
            >
              {renderExportLabel('student-balance-changes')}
            </Button>
          </div>
          <Typography variant="caption" color="secondary" className="block">
            Columns: Date, Student ID, Student Name, Type, Reference, Amount (+ in / − out)
          </Typography>
        </div>

        <div>
          <Typography variant="subtitle1" className="mb-2">
            Bank Transfers (Outgoing)
          </Typography>
          <div className="flex gap-4 items-center flex-wrap mb-2">
            <div className="min-w-[180px]">
              <Input
                label="Start date"
                type="date"
                value={datesBankTransfers.start}
                onChange={(e) => setDatesBankTransfers((p) => ({ ...p, start: e.target.value }))}
              />
            </div>
            <div className="min-w-[180px]">
              <Input
                label="End date"
                type="date"
                value={datesBankTransfers.end}
                onChange={(e) => setDatesBankTransfers((p) => ({ ...p, end: e.target.value }))}
              />
            </div>
            <Button
              variant="outlined"
              onClick={() =>
                handleExport('bank-transfers', datesBankTransfers.start, datesBankTransfers.end)
              }
              disabled={isBusy}
            >
              {renderExportLabel('bank-transfers')}
            </Button>
          </div>
          <Typography variant="caption" color="secondary" className="block">
            Columns: Value Date, Description, Reference, Type, Amount, Matched document#, Proof link
          </Typography>
        </div>

        <div>
          <Typography variant="subtitle1" className="mb-2">
            Bank Statement Files
          </Typography>
          <div className="flex gap-4 items-center flex-wrap mb-2">
            <div className="min-w-[180px]">
              <Input
                label="Start date"
                type="date"
                value={datesBankFiles.start}
                onChange={(e) => setDatesBankFiles((p) => ({ ...p, start: e.target.value }))}
              />
            </div>
            <div className="min-w-[180px]">
              <Input
                label="End date"
                type="date"
                value={datesBankFiles.end}
                onChange={(e) => setDatesBankFiles((p) => ({ ...p, end: e.target.value }))}
              />
            </div>
            <Button
              variant="outlined"
              onClick={() =>
                handleExport('bank-statement-files', datesBankFiles.start, datesBankFiles.end)
              }
              disabled={isBusy}
            >
              {renderExportLabel('bank-statement-files')}
            </Button>
          </div>
          <Typography variant="caption" color="secondary" className="block">
            Columns: Import ID, File name, Range from/to, Download link
          </Typography>
        </div>
      </div>
    </div>
  )
}
