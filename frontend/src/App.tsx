import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { AlertCircle, Fingerprint, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { fetchLlmConfig } from './api/client'
import { Sidebar } from './components/layout/Sidebar'
import { TopBar } from './components/layout/TopBar'
import type { Section } from './components/layout/sections'
import { ThemeProvider } from './components/theme/ThemeProvider'
import { ToastProvider } from './components/toast/ToastProvider'
import { Button } from './components/ui/button'
import { formatTtl, shortSessionId } from './lib/format'
import { ChatTab } from './tabs/ChatTab'
import { KnowledgeSection, type KnowledgeView } from './sections/KnowledgeSection'
import { SessionProvider } from './session/SessionProvider'
import { useSession } from './session/SessionContext'
import { OverviewTab } from './tabs/OverviewTab'
import { SettingsTab } from './tabs/SettingsTab'

const DEMO_CHIP_DISMISS_KEY = 'second-brain.demo-chip-dismissed'

function DemoSessionChip() {
  const { sessionId, expiresAt, error, retrySession, isMintingSession, isLoading, clearSession } =
    useSession()
  const [dismissed, setDismissed] = useState(() => {
    try {
      return window.localStorage.getItem(DEMO_CHIP_DISMISS_KEY) === '1'
    } catch {
      return false
    }
  })

  if (dismissed && !error) return null

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
      <Fingerprint className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span className="font-medium text-foreground">
        Session {isMintingSession ? '…' : shortSessionId(sessionId)}
      </span>
      <span>· TTL {formatTtl(expiresAt)}</span>
      <Button
        variant="ghost"
        size="sm"
        className="h-6 px-2 text-xs"
        disabled={isLoading}
        onClick={() => void clearSession()}
      >
        {isLoading ? '…' : 'New ID'}
      </Button>
      {error ? (
        <button
          type="button"
          className="inline-flex items-center gap-1 font-semibold text-warning-foreground underline"
          onClick={() => void retrySession()}
        >
          <AlertCircle className="h-3.5 w-3.5" />
          Retry
        </button>
      ) : (
        <button
          type="button"
          className="rounded p-0.5 hover:bg-secondary"
          aria-label="Dismiss session chip"
          onClick={() => {
            try {
              window.localStorage.setItem(DEMO_CHIP_DISMISS_KEY, '1')
            } catch {
              /* ignore */
            }
            setDismissed(true)
          }}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

function Shell() {
  const [section, setSection] = useState<Section>('ask')
  const [knowledgeView, setKnowledgeView] = useState<KnowledgeView>('browse')
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem('second-brain.sidebar-collapsed') === '1'
    } catch {
      return false
    }
  })

  const { data: llmConfig } = useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLlmConfig,
    staleTime: Infinity,
  })
  const isDemo = !!llmConfig?.demo_mode

  useEffect(() => {
    try {
      window.localStorage.setItem('second-brain.sidebar-collapsed', sidebarCollapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [sidebarCollapsed])

  const goToVault = useCallback(() => {
    setKnowledgeView('browse')
    setSection('knowledge')
  }, [])

  const askAbout = useCallback((prompt: string) => {
    setPendingPrompt(prompt)
    setSection('ask')
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar
        active={section}
        onSelect={setSection}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed((c) => !c)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar active={section} onSelect={setSection} />
        {section === 'ask' ? (
          <div className="flex min-h-0 flex-1 flex-col gap-2 px-3 py-3 md:px-6">
            {isDemo ? (
              <div className="flex justify-end">
                <DemoSessionChip />
              </div>
            ) : null}
            <div className="min-h-0 flex-1">
              <ChatTab
                onNavigateVault={goToVault}
                onNavigateSettings={() => setSection('settings')}
                pendingPrompt={pendingPrompt}
                onPendingPromptConsumed={() => setPendingPrompt(null)}
              />
            </div>
          </div>
        ) : section === 'help' ? (
          <main className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-6 md:px-8">
              <OverviewTab />
            </div>
          </main>
        ) : (
          <main className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-6 md:px-8">
            {section === 'knowledge' ? (
              <KnowledgeSection
                view={knowledgeView}
                onViewChange={setKnowledgeView}
                onAskAbout={askAbout}
              />
            ) : null}
            {section === 'settings' ? <SettingsTab /> : null}
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
        <ToastProvider>
          <SessionProvider>
            <Shell />
          </SessionProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
