import { api } from '../services/api'

/**
 * Download a report as Excel (XLSX). Uses the same endpoint with format=xlsx.
 * @param path - API path e.g. '/reports/aged-receivables'
 * @param params - Same query params as the report (date_from, date_to, etc.)
 * @param filename - Suggested filename e.g. 'aged-receivables.xlsx'
 */
export function downloadReportExcel(
  path: string,
  params: Record<string, unknown>,
  filename: string
): void {
  api
    .get(path, {
      params: { ...params, format: 'xlsx' },
      responseType: 'blob',
    })
    .then((res) => {
      const blob = res.data as Blob
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    })
    .catch((err) => {
      console.error('Excel download failed', err)
      // Optionally show a snackbar - for now just log
    })
}
