export type VaultStats = {
  file_count: number
  chunk_count: number
  last_ingest_at?: string | null
  embed_model?: string
  vault_path?: string
  vault_host_path?: string | null
}

export type VaultClearBody = {
  confirm: 'delete'
  clear_vault?: boolean
  clear_memory?: boolean
  clear_chats?: boolean
}

export type VaultClearResponse = {
  cleared: { vault: boolean; memory: boolean; chats: boolean }
  detail: string
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export const vaultClient = {
  clear: (body: VaultClearBody) =>
    json<VaultClearResponse>('/vault/clear', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  stats: () => json<VaultStats>('/vault/stats'),
}
