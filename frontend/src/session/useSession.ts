import { create } from 'zustand'
import type { SessionSummary } from '../api/client'

export const SESSION_STORAGE_KEY = 'doc-ingestion.demo.session'

interface SessionState {
  sessionId: string | null
  expiresAt: number | null
  setSession: (sessionId: string, expiresAt: number | null) => void
  clearLocalSession: () => void
}

function readStoredSession(): Pick<SessionState, 'sessionId' | 'expiresAt'> {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) {
      return { sessionId: null, expiresAt: null }
    }
    const parsed = JSON.parse(raw) as { sessionId?: string; expiresAt?: number }
    return { sessionId: parsed.sessionId ?? null, expiresAt: parsed.expiresAt ?? null }
  } catch {
    return { sessionId: null, expiresAt: null }
  }
}

export const useSessionStore = create<SessionState>((set) => ({
  ...readStoredSession(),
  setSession: (sessionId, expiresAt) => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ sessionId, expiresAt }))
    set({ sessionId, expiresAt })
  },
  clearLocalSession: () => {
    localStorage.removeItem(SESSION_STORAGE_KEY)
    set({ sessionId: null, expiresAt: null })
  },
}))

export interface SessionContextValue {
  sessionId: string | null
  expiresAt: number | null
  summary: SessionSummary | undefined
  /** True only while POST /sessions is in-flight (nothing in localStorage yet). */
  isMintingSession: boolean
  /**
   * True while we lack session summary yet (new session bootstrap or hydrating from storage).
   * Prefer this or isMintingSession over isLoading when you care about UX flicker.
   */
  awaitsSessionEnvelope: boolean
  isLoading: boolean
  error: Error | null
  hasUploads: boolean
  refreshSession: () => Promise<unknown>
  clearSession: () => Promise<void>
  retrySession: () => Promise<void>
}
