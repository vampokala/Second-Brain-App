/** Subscribe to ingest SSE (`/events/ingest`). */

import { resolveApiBaseUrl } from '../api/client'

export function ingestEventsSource(
  onMessage: (payload: Record<string, unknown>) => void,
): { close: () => void } {
  const root = resolveApiBaseUrl()
  const url = root ? `${root}/events/ingest` : '/events/ingest'
  const es = new EventSource(url)
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as Record<string, unknown>
      onMessage(data)
    } catch {
      /* ignore */
    }
  }
  return { close: () => es.close() }
}
