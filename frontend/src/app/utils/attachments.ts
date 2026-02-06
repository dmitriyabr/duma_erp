import { api } from '../services/api'

/**
 * Opens attachment file in a new tab (image/PDF). Uses auth from api.
 */
export async function openAttachmentInNewTab(attachmentId: number): Promise<void> {
  const response = await api.get(`/attachments/${attachmentId}/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data as Blob)
  window.open(url, '_blank', 'noopener,noreferrer')
  // Revoke after a delay so the new tab can load the blob
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export async function downloadAttachment(attachmentId: number): Promise<void> {
  const response = await api.get(`/attachments/${attachmentId}/download`, {
    responseType: 'blob',
  })

  const disposition = response.headers['content-disposition']
  const match = disposition?.match(/filename="?([^";]+)"?/)
  const filename = match?.[1] ?? `attachment-${attachmentId}`

  const blob = response.data as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
