import { useEffect, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiError,
  createSession,
  deleteSession,
  getSession,
  type SessionSummary,
} from '../api/client'
import { SessionContext } from './SessionContext'
import { type SessionContextValue, useSessionStore } from './useSession'

function isStaleSessionError(error: unknown) {
  return error instanceof ApiError && [400, 404, 422].includes(error.status)
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const { sessionId, expiresAt, setSession, clearLocalSession } = useSessionStore()

  const createMutation = useMutation({
    mutationFn: createSession,
    onSuccess: (session) => {
      setSession(session.session_id, session.expires_at)
      queryClient.setQueryData(['session', session.session_id], {
        ...session,
        files: [],
        total_bytes: 0,
        max_files: 3,
        max_session_bytes: 8 * 1024 * 1024,
      } satisfies SessionSummary)
    },
  })

  const mutateCreateSession = createMutation.mutate

  const sessionQuery = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId as string),
    enabled: Boolean(sessionId),
    retry: false,
    staleTime: 60_000,
    gcTime: 30 * 60_000,
  })

  useEffect(() => {
    if (sessionId || createMutation.isPending || createMutation.isError) {
      return
    }
    mutateCreateSession()
  }, [sessionId, createMutation.isPending, createMutation.isError, mutateCreateSession])

  useEffect(() => {
    if (isStaleSessionError(sessionQuery.error)) {
      clearLocalSession()
      mutateCreateSession()
    }
  }, [clearLocalSession, mutateCreateSession, sessionQuery.error])

  useEffect(() => {
    if (sessionQuery.data) {
      setSession(sessionQuery.data.session_id, sessionQuery.data.expires_at)
    }
  }, [sessionQuery.data, setSession])

  const isMintingSession = Boolean(!sessionId && createMutation.isPending)
  const awaitsSessionEnvelope =
    Boolean(sessionId) && sessionQuery.data == null && (sessionQuery.isPending || sessionQuery.isFetching)

  const value = useMemo<SessionContextValue>(
    () => ({
      sessionId,
      expiresAt,
      summary: sessionQuery.data,
      isMintingSession,
      awaitsSessionEnvelope,
      isLoading: isMintingSession || awaitsSessionEnvelope,
      error: (sessionQuery.error as Error | null) ?? (createMutation.error as Error | null),
      hasUploads: Boolean(sessionQuery.data?.files.length),
      refreshSession: () => sessionQuery.refetch(),
      retrySession: async () => {
        clearLocalSession()
        await createMutation.mutateAsync()
      },
      clearSession: async () => {
        if (!sessionId) {
          clearLocalSession()
          await createMutation.mutateAsync()
          return
        }
        const next = await deleteSession(sessionId)
        setSession(next.session_id, null)
        queryClient.removeQueries({ queryKey: ['query'] })
        queryClient.removeQueries({ queryKey: ['session'] })
        await queryClient.invalidateQueries({ queryKey: ['session', next.session_id] })
      },
    }),
    [
      clearLocalSession,
      createMutation,
      awaitsSessionEnvelope,
      expiresAt,
      isMintingSession,
      queryClient,
      sessionId,
      sessionQuery,
      setSession,
    ],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
