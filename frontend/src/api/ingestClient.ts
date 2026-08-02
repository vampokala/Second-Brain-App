const base = ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export type IngestCapabilities = {
  supported_extensions: string[]
  vision_enabled: boolean
  max_upload_bytes?: number
  default_provider?: string
  default_model?: string
}

export type IngestItemResult = {
  path: string
  status: 'queued' | 'processing' | 'ingested' | 'failed' | 'skipped' | 'cancelled'
  chunk_count: number
  error?: string | null
}

export type IngestScanSummary = {
  total: number
  ingested: number
  skipped: number
  failed: number
  cancelled: number
}

export type IngestScanFile = {
  path: string
  change: 'new' | 'changed'
  size: number
  mtime_ms: number
}

export type IngestScanPreviewSummary = {
  total_scanned: number
  new: number
  changed: number
  unchanged: number
}

export type IngestScanPreviewResponse = {
  files: IngestScanFile[]
  summary: IngestScanPreviewSummary
}

export type IngestScanStartResponse = {
  status: 'started'
  detail?: string
  selected?: number
}

export const ingestClient = {
  capabilities: () => json<IngestCapabilities>('/ingest/capabilities'),
  cancel: () => json<{ status: string }>('/ingest/cancel', { method: 'POST', body: '{}' }),
  scanPreview: () =>
    json<IngestScanPreviewResponse>('/ingest/scan', { method: 'POST', body: '{}' }),
  ingestPaths: (paths: string[]) =>
    json<IngestScanStartResponse>('/ingest/paths', {
      method: 'POST',
      body: JSON.stringify({ paths }),
    }),
}
