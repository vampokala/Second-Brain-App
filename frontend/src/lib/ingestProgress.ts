/** Derive a human progress row status from ingest event text. */
export function progressStatusFromText(text: string): 'running' | 'ok' | 'error' {
  const lower = text.toLowerCase()
  if (lower.includes('error') || lower.includes('fail')) return 'error'
  if (
    lower.includes('done') ||
    lower.includes('ok') ||
    lower.includes('complete') ||
    lower.includes('skipped') ||
    lower.includes('cancelled') ||
    lower.includes('ingested')
  ) {
    return 'ok'
  }
  return 'running'
}

export type IngestProgressPayload = {
  phase?: string
  message?: string
  current?: number
  total?: number
  relativePath?: string
  relative_path?: string
  file_path?: string
  event_type?: string
  status?: string
  details?: { error?: string | null; chunk_count?: number; message?: string }
}

/** Normalize App legacy SSE + Lite-shaped progress into one payload. */
export function normalizeIngestProgress(
  raw: Record<string, unknown>,
): IngestProgressPayload {
  const details =
    raw.details && typeof raw.details === 'object'
      ? (raw.details as IngestProgressPayload['details'])
      : undefined
  const path = String(
    raw.relative_path ||
      raw.relativePath ||
      raw.file_path ||
      raw.path ||
      raw.relpath ||
      '',
  )
  const status = String(raw.status || '')
  const err = details?.error ? String(details.error) : ''
  const message = String(
    raw.message || details?.message || (err ? `${status}: ${err}` : status) || '',
  )
  const eventType = String(raw.event_type || '')
  const phaseRaw = String(raw.phase || eventType || 'ingest')
  const phase = phaseRaw === 'ingest' ? 'file' : phaseRaw
  return {
    phase,
    message,
    current: typeof raw.current === 'number' ? raw.current : undefined,
    total: typeof raw.total === 'number' ? raw.total : undefined,
    relative_path: path || undefined,
    relativePath: path || undefined,
    file_path: path || undefined,
    event_type: eventType,
    status,
    details,
  }
}

/** Port of Lite `formatIngestProgressLine`. */
export function formatIngestProgressLine(p: IngestProgressPayload): string {
  const path = p.relativePath || p.relative_path || p.file_path || ''
  const phase = p.phase || 'ingest'
  const message = p.message || ''
  const cur = p.current
  const tot = p.total
  const prefix =
    typeof cur === 'number' && typeof tot === 'number' ? `[${cur}/${tot}] ` : ''
  const mid = path ? `${path} · ` : ''
  return `${prefix}${mid}${phase}: ${message}`.trim()
}

export type ProgressRow = {
  id: string
  label: string
  status: 'running' | 'ok' | 'error'
  detail?: string
}

export function progressRowFromPayload(raw: Record<string, unknown>): ProgressRow | null {
  const p = normalizeIngestProgress(raw)
  const label = p.relative_path || p.phase || 'Ingest'
  if (!p.relative_path && !p.message && !p.status && !p.phase) return null
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    label,
    status: progressStatusFromText(`${p.status || ''} ${p.message || ''}`),
    detail: p.message || p.status || undefined,
  }
}
