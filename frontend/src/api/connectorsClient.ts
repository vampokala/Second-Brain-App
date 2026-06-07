export type ConnectorType = 'github' | 'jira' | 'confluence' | 'slack'

export type Connector = {
  id: string
  connector_type: ConnectorType
  resource_id: string
  config: Record<string, unknown>
  enabled: boolean
  sync_interval_min: number | null
  cursor: Record<string, unknown> | null
  last_sync_at: string | null
  next_sync_at: string | null
  last_status: string | null
  last_error: string | null
  item_count: number
}

export type ConnectorUpsert = {
  connector_type: ConnectorType
  resource_id: string
  config: Record<string, unknown>
  enabled?: boolean
  sync_interval_min?: number | null
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Request failed (${res.status})`)
  }
  return (await res.json()) as T
}

export const connectorsClient = {
  list: () => fetch('/connectors').then((r) => asJson<Connector[]>(r)),
  upsert: (body: ConnectorUpsert) =>
    fetch('/connectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => asJson<Connector>(r)),
  remove: (id: string) =>
    fetch(`/connectors/${id}`, { method: 'DELETE' }).then((r) => asJson<{ status: string }>(r)),
  test: (id: string) =>
    fetch(`/connectors/${id}/test`, { method: 'POST' }).then((r) =>
      asJson<{ ok: boolean; message: string }>(r),
    ),
  sync: (id: string) =>
    fetch(`/connectors/${id}/sync`, { method: 'POST' }).then((r) =>
      asJson<{ status: string; detail: string | null }>(r),
    ),
}
