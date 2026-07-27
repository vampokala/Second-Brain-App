const base = ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export type MemoryResponse = {
  content: string
  path: string
}

export const memoryClient = {
  getMemory: () => json<MemoryResponse>('/memory'),
}
