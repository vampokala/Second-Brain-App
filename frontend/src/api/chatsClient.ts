import type { ChatTruthfulness } from '../lib/streamChat'

const base = ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export type RetrievedChunk = {
  id: string
  score: number
  source: string
  preview: string
}

export type ChatListItem = {
  id: string
  title: string | null
  updated_at: string
  model: string
  provider: string
  pinned: boolean
}

export type GroundingMode = 'corpus_only' | 'allow_general'

export type SendMessageBody = {
  message: string
  provider?: string
  model?: string
  scope?: string
  system_prompt?: string | null
  grounding_mode?: GroundingMode
  include_web_search?: boolean
}

export type PersonasResponse = {
  personas: { id: string; label: string }[]
  grades: { id: string; label: string }[]
}

export type SaveToWikiResponse = {
  path: string
  ingested: boolean
  chunk_count: number
}

export type UpdateMemoryResponse = {
  content: string
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
    retrieved?: RetrievedChunk[]
    /** Client-side attach from SSE `final`; not always persisted by GET /chats. */
    truthfulness?: ChatTruthfulness
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
  pin: (id: string, pinned: boolean) =>
    json<ChatDetail>(`/chats/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ pinned }),
    }),
  regeneratePath: (chatId: string, messageId: string) =>
    `/chats/${chatId}/messages/${messageId}/regenerate`,
  editPath: (chatId: string, messageId: string) => `/chats/${chatId}/messages/${messageId}/edit`,
  listPersonas: () => json<PersonasResponse>('/settings/personas'),
  saveToWiki: (chatId: string, messageId: string, body?: Record<string, unknown>) =>
    json<SaveToWikiResponse>(`/chats/${chatId}/messages/${messageId}/save-to-wiki`, {
      method: 'POST',
      body: JSON.stringify(body ?? {}),
    }),
  updateMemory: (chatId: string) =>
    json<UpdateMemoryResponse>(`/chats/${chatId}/memory/update`, {
      method: 'POST',
      body: '{}',
    }),
}
