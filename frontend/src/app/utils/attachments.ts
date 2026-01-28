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
