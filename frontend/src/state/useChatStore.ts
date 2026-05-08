import { create } from 'zustand'

import type { ChatDetail, ChatListItem } from '../api/chatsClient'

type State = {
  chats: ChatListItem[]
  activeId: string | null
  detail: ChatDetail | null
  streamText: string
  loading: boolean
  error: string | null
  setChats: (c: ChatListItem[]) => void
  setActive: (id: string | null) => void
  setDetail: (d: ChatDetail | null) => void
  appendStream: (t: string) => void
  resetStream: () => void
  setLoading: (b: boolean) => void
  setError: (e: string | null) => void
}

export const useChatStore = create<State>((set) => ({
  chats: [],
  activeId: null,
  detail: null,
  streamText: '',
  loading: false,
  error: null,
  setChats: (chats) => set({ chats }),
  setActive: (activeId) => set({ activeId }),
  setDetail: (detail) => set({ detail }),
  appendStream: (t) => set((s) => ({ streamText: s.streamText + t })),
  resetStream: () => set({ streamText: '' }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}))
