const base = ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export type ChatListItem = {
  id: string
  title: string | null
  updated_at: string
  model: string
  provider: string
  pinned: boolean
}

export type ChatDetail = {
  id: string
  title: string | null
  pinned: boolean
  system_prompt: string | null
  provider: string
  model: string
  knowledge_scope: string
  messages: Array<{
    id: string
    role: string
    content: string
    parent_id: string | null
    created_at: string
    citations: Array<Record<string, unknown>>
  }>
}

export const chatsClient = {
  list: () => json<ChatListItem[]>('/chats'),
  get: (id: string) => json<ChatDetail>(`/chats/${id}`),
  create: (body: {
    title?: string | null
    system_prompt?: string | null
    provider?: string
    model?: string
    knowledge_scope?: string
  }) =>
    json<ChatDetail>('/chats', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  patch: (id: string, body: Record<string, unknown>) =>
    json<ChatDetail>(`/chats/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  remove: (id: string) => json<{ status: string }>(`/chats/${id}`, { method: 'DELETE' }),
  search: (q: string) =>
    json<Array<{ message_id: string; chat_id: string; role: string; preview: string; rank: number }>>(
      `/chats/search?q=${encodeURIComponent(q)}`,
    ),
}
