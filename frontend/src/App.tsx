import * as Tabs from '@radix-ui/react-tabs'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AlertCircle, BookOpen, Database, FileText, Fingerprint } from 'lucide-react'
import { useMemo } from 'react'
import { QueryTab } from './tabs/QueryTab'
import { OverviewTab } from './tabs/OverviewTab'
import { DocumentsTab } from './tabs/DocumentsTab'
import { SessionProvider } from './session/SessionProvider'
import { useSession } from './session/SessionContext'
import { formatTtl, shortSessionId } from './lib/format'

function Shell() {
  const { sessionId, expiresAt, error, retrySession, isMintingSession, isLoading, clearSession } =
    useSession()

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 md:px-8">
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="app-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Doc Ingestion</p>
              <h1 className="mt-1 text-3xl font-bold text-slate-950">Document Q&A Assistant</h1>
              <p className="mt-2 max-w-3xl text-slate-600">
                Ask citation-aware questions against the global demo corpus, your private uploads, or both.
              </p>
            </div>
            <div className="flex min-w-[12rem] flex-col gap-2 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
              <div>
                <div>Session {isMintingSession ? 'creating…' : shortSessionId(sessionId)}</div>
                <div className="text-slate-500">TTL {formatTtl(expiresAt)}</div>
              </div>
              <button
                type="button"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow hover:bg-blue-700 disabled:pointer-events-none disabled:opacity-50"
                disabled={isLoading}
                aria-busy={isLoading}
                onClick={() => void clearSession()}
              >
                <Fingerprint className="h-4 w-4 shrink-0" aria-hidden="true" />
                {isLoading ? 'Creating…' : sessionId ? 'New session ID' : 'Generate session ID'}
              </button>
              <p className="text-xs leading-snug text-slate-500">
                Fresh ID for uploads in this browser. Replaces any current demo session (including uploads on
                the server).
              </p>
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
            Your uploads stay in this browser session, expire after inactivity, and are not added to the
            shared corpus.
          </div>
          {error ? (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <span className="inline-flex items-center gap-2">
                <AlertCircle className="h-4 w-4" aria-hidden="true" />
                {error.message}
              </span>
              <button type="button" className="font-semibold underline" onClick={() => void retrySession()}>
                Retry session
              </button>
            </div>
          ) : null}
        </header>

        <Tabs.Root defaultValue="overview" className="space-y-5">
          <Tabs.List className="app-card inline-flex gap-2 p-2" aria-label="Main sections">
            <Tabs.Trigger
              value="overview"
              className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-slate-700 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
            >
              <BookOpen className="h-4 w-4" aria-hidden="true" />
              Overview
            </Tabs.Trigger>
            <Tabs.Trigger
              value="query"
              className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-slate-700 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
            >
              <Database className="h-4 w-4" aria-hidden="true" />
              Query
            </Tabs.Trigger>
            <Tabs.Trigger
              value="documents"
              className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-slate-700 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
            >
              <FileText className="h-4 w-4" aria-hidden="true" />
              My documents
            </Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="overview">
            <OverviewTab />
          </Tabs.Content>
          <Tabs.Content value="query">
            <QueryTab />
          </Tabs.Content>
          <Tabs.Content value="documents">
            <DocumentsTab />
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </main>
  )
}

function App() {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: false,
          },
        },
      }),
    [],
  )

  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <Shell />
      </SessionProvider>
    </QueryClientProvider>
  )
}

export default App
