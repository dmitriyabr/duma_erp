import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { api, unwrapResponse } from '../../services/api'

interface InvoiceReference { id: number }

interface Props {
  invoice: InvoiceReference
  transportZoneId?: number | null
  onRecalculate: () => void
}

/** Rare correction actions are available only when the server finds a price difference. */
export function TransportInvoiceActions({ invoice, transportZoneId, onRecalculate }: Props) {
  const menu = useRef<HTMLDetailsElement>(null)
  const [availableFor, setAvailableFor] = useState<{
    invoice: InvoiceReference
    zoneId: number | null | undefined
  } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    api.post(`/invoices/${invoice.id}/recalculate-transport/preview`, undefined, {
      signal: controller.signal,
    }).then(response => {
      if (!controller.signal.aborted) {
        const { changed } = unwrapResponse<{ changed: boolean }>(response)
        setAvailableFor(changed ? { invoice, zoneId: transportZoneId } : null)
      }
    }).catch(() => {
      if (!controller.signal.aborted) setAvailableFor(null)
    })
    return () => controller.abort()
  }, [invoice, transportZoneId])

  useEffect(() => {
    const closeOutside = (event: MouseEvent) => {
      if (menu.current && !menu.current.contains(event.target as Node)) menu.current.open = false
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && menu.current?.open) {
        menu.current.open = false
        menu.current.querySelector('summary')?.focus()
      }
    }
    document.addEventListener('mousedown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [])

  // Hide stale availability immediately while another invoice/zone is being checked.
  if (availableFor?.invoice !== invoice || availableFor.zoneId !== transportZoneId) return null

  return <details ref={menu} className="relative">
    <summary className="flex cursor-pointer list-none items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
      Actions <ChevronDown className="h-4 w-4" />
    </summary>
    <div className="absolute bottom-full right-0 z-10 mb-2 min-w-52 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
      <button type="button" className="w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100" onClick={() => {
        if (menu.current) menu.current.open = false
        onRecalculate()
      }}>
        Recalculate transport
      </button>
    </div>
  </details>
}
