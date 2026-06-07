import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { AlertCircle, Fingerprint } from 'lucide-react'
import { useMemo, useState } from 'react'

import { fetchLlmConfig } from './api/client'
import { Sidebar } from './components/layout/Sidebar'
import { TopBar } from './components/layout/TopBar'
import type { AskView, Section } from './components/layout/sections'
import { ThemeProvider } from './components/theme/ThemeProvider'
import { Button } from './components/ui/button'
import { formatTtl, shortSessionId } from './lib/format'
import { AskSection } from './sections/AskSection'
import { KnowledgeSection, type KnowledgeView } from './sections/KnowledgeSection'
import { SessionProvider } from './session/SessionProvider'
import { useSession } from './session/SessionContext'
import { OverviewTab } from './tabs/OverviewTab'
import { SettingsTab } from './tabs/SettingsTab'

function DemoSessionBanner() {
  const { sessionId, expiresAt, error, retrySession, isMintingSession, isLoading, clearSession } =
    useSession()
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">
            Session {isMintingSession ? 'creating…' : shortSessionId(sessionId)}
          </span>
          <span className="ml-2">TTL {formatTtl(expiresAt)}</span>
          <p className="mt-1 text-xs">
            Uploads stay in this browser session, expire after inactivity, and are not added to the
            shared corpus.
          </p>
        </div>
        <Button variant="outline" size="sm" disabled={isLoading} onClick={() => void clearSession()}>
          <Fingerprint className="h-4 w-4" />
          {isLoading ? 'Creating…' : sessionId ? 'New session ID' : 'Generate session ID'}
        </Button>
      </div>
      {error ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning-foreground">
          <span className="inline-flex items-center gap-2">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            {error.message}
          </span>
          <button type="button" className="font-semibold underline" onClick={() => void retrySession()}>
            Retry session
          </button>
        </div>
      ) : null}
    </div>
  )
}

function Shell() {
  const [section, setSection] = useState<Section>('ask')
  const [askView, setAskView] = useState<AskView>('chat')
  const [knowledgeView, setKnowledgeView] = useState<KnowledgeView>('browse')

  const { data: llmConfig } = useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLlmConfig,
    staleTime: Infinity,
  })
  const isDemo = !!llmConfig?.demo_mode

  const goToVault = () => {
    setKnowledgeView('browse')
    setSection('knowledge')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar active={section} onSelect={setSection} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          active={section}
          onSelect={setSection}
          askView={askView}
          onAskViewChange={setAskView}
        />
        {section === 'ask' ? (
          // App-style full-height pane: only the message list scrolls.
          <div className="flex min-h-0 flex-1 flex-col gap-4 px-4 py-4 md:px-8">
            {isDemo ? <DemoSessionBanner /> : null}
            <div className="min-h-0 flex-1">
              <AskSection view={askView} onNavigateVault={goToVault} />
            </div>
          </div>
        ) : (
          <main className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6 md:px-8">
              {isDemo ? <DemoSessionBanner /> : null}
              {section === 'knowledge' ? (
                <KnowledgeSection view={knowledgeView} onViewChange={setKnowledgeView} />
              ) : null}
              {section === 'settings' ? <SettingsTab /> : null}
              {section === 'help' ? <OverviewTab /> : null}
            </div>
          </main>
        )}
      </div>
    </div>
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
      <ThemeProvider>
        <SessionProvider>
          <Shell />
        </SessionProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
