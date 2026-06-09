import { create } from 'zustand'

import type { ChatDetail, ChatListItem, RetrievedChunk } from '../api/chatsClient'

export type { RetrievedChunk }

type State = {
  chats: ChatListItem[]
  activeId: string | null
  detail: ChatDetail | null
  streamText: string
  loading: boolean
  error: string | null
  // Retrieval chunks for the in-flight turn, shown live under the streaming
  // bubble. Once the turn completes the chunks are persisted on the message and
  // come back via the re-fetched detail, so this is only transient.
  pendingChunks: RetrievedChunk[]
  setChats: (c: ChatListItem[]) => void
  setActive: (id: string | null) => void
  setDetail: (d: ChatDetail | null) => void
  appendStream: (t: string) => void
  resetStream: () => void
  setLoading: (b: boolean) => void
  setError: (e: string | null) => void
  setPendingChunks: (c: RetrievedChunk[]) => void
}

export const useChatStore = create<State>((set) => ({
  chats: [],
  activeId: null,
  detail: null,
  streamText: '',
  loading: false,
  error: null,
  pendingChunks: [],
  setChats: (chats) => set({ chats }),
  setActive: (activeId) => set({ activeId }),
  setDetail: (detail) => set({ detail }),
  appendStream: (t) => set((s) => ({ streamText: s.streamText + t })),
  resetStream: () => set({ streamText: '', pendingChunks: [] }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setPendingChunks: (pendingChunks) => set({ pendingChunks }),
}))
