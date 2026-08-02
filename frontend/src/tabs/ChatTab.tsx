import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { PanelLeftClose, PanelLeftOpen, X } from 'lucide-react'

import { Button } from '../components/ui/button'
import { chatsClient, type GroundingMode } from '../api/chatsClient'
import { fetchLlmConfig } from '../api/client'
import type { LlmConfigModel } from '../api/generated'
import { streamChatPost, type ChatMetaEvent, type ChatTruthfulness } from '../lib/streamChat'
import { personaChipLabel } from '../lib/personas'
import { vaultPathQuery } from '../lib/vaultDeepLink'
import { useToast } from '../components/toast/ToastProvider'
import { useSession } from '../session/SessionContext'
import { useChatStore, type RetrievedChunk } from '../state/useChatStore'
import { ChatHeader } from '../components/chat/ChatHeader'
import { Composer } from '../components/chat/Composer'
import { ConversationList } from '../components/chat/ConversationList'
import { MessageStream } from '../components/chat/MessageStream'
import {
  SourcesDrawer,
  type SourceCitation,
} from '../components/chat/SourcesDrawer'

function pickDefaultChatProvider(cfg: LlmConfigModel): string {
  const keys = Object.keys(cfg.allowed_models_by_provider)
  const isUsable = (p: string) => {
    if (cfg.provider_key_configured[p] !== true) return false
    if (p === 'gateway') {
      return Boolean(cfg.default_model_by_provider[p] || cfg.allowed_models_by_provider[p]?.length)
    }
    return (cfg.allowed_models_by_provider[p]?.length ?? 0) > 0
  }
  if (isUsable(cfg.default_provider)) return cfg.default_provider
  const usable = keys.find(isUsable)
  if (usable) return usable
  return keys.includes(cfg.default_provider) ? cfg.default_provider : keys[0] ?? 'ollama'
}

function pickDefaultChatModel(cfg: LlmConfigModel, provider: string): string {
  const models = cfg.allowed_models_by_provider[provider] ?? []
  const def = cfg.default_model_by_provider[provider]
  if (def && (models.includes(def) || provider === 'gateway')) return def
  return models[0] ?? def ?? ''
}

type Props = {
  onNavigateVault?: () => void
  onNavigateSettings?: () => void
  pendingPrompt?: string | null
  onPendingPromptConsumed?: () => void
}

type AppSettings = {
  chat_persona?: string
  student_grade?: string
  web_search_enabled?: boolean
  brave_search_api_key?: string
}

export function ChatTab({
  onNavigateVault,
  onNavigateSettings,
  pendingPrompt,
  onPendingPromptConsumed,
}: Props) {
  const { toast } = useToast()
  const { summary: sessionSummary } = useSession()
  const {
    chats,
    activeId,
    detail,
    streamText,
    loading,
    error,
    pendingChunks,
    setChats,
    setActive,
    setDetail,
    appendStream,
    resetStream,
    setLoading,
    setError,
    setPendingChunks,
  } = useChatStore()
  const [searchQ, setSearchQ] = useState('')
  const [showList, setShowList] = useState(true)
  const [mobileListOpen, setMobileListOpen] = useState(false)
  const [_header, setHeader] = useState({ provider: '', model: '', scope: 'vault' })
  const [headerSeeded, setHeaderSeeded] = useState(false)
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null)
  const [bootstrapped, setBootstrapped] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [sourcesCitations, setSourcesCitations] = useState<SourceCitation[]>([])
  const [sourcesChunks, setSourcesChunks] = useState<RetrievedChunk[]>([])
  const [groundingMode, setGroundingMode] = useState<GroundingMode>('corpus_only')
  const [includeWebSearch, setIncludeWebSearch] = useState(false)
  const [lastMeta, setLastMeta] = useState<ChatMetaEvent | null>(null)
  const [lastTruthfulness, setLastTruthfulness] = useState<ChatTruthfulness | null>(null)
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null)
  const creatingRef = useRef(false)
  const pendingSendRef = useRef<string | null>(null)

  const { data: llmConfig } = useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLlmConfig,
    staleTime: Infinity,
  })

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch('/settings')
        if (!res.ok) return
        const payload = (await res.json()) as { values: Record<string, unknown> }
        const values = payload.values
        setAppSettings({
          chat_persona: typeof values.chat_persona === 'string' ? values.chat_persona : undefined,
          student_grade: typeof values.student_grade === 'string' ? values.student_grade : undefined,
          web_search_enabled: values.web_search_enabled === true,
          brave_search_api_key:
            typeof values.brave_search_api_key === 'string' ? values.brave_search_api_key : undefined,
        })
        if (values.web_search_enabled === true) {
          setIncludeWebSearch(true)
        }
      } catch {
        /* settings optional until backend ready */
      }
    })()
  }, [])

  const webSearchAvailable = useMemo(() => {
    if (appSettings?.web_search_enabled === false) return false
    const masked = appSettings?.brave_search_api_key?.trim()
    return !!masked && masked !== '***'
  }, [appSettings])

  const personaLabel = useMemo(
    () =>
      personaChipLabel({
        chatPersona: appSettings?.chat_persona,
        studentGrade: appSettings?.student_grade,
      }),
    [appSettings],
  )

  const sessionFiles = sessionSummary?.files ?? []

  const displayMessages = useMemo(() => {
    const msgs = detail?.messages ?? []
    if (!lastTruthfulness || msgs.length === 0) return msgs
    const lastAssistantIdx = [...msgs].reverse().findIndex((m) => m.role === 'assistant')
    if (lastAssistantIdx < 0) return msgs
    const idx = msgs.length - 1 - lastAssistantIdx
    const last = msgs[idx]
    if (last.truthfulness) return msgs
    const next = [...msgs]
    next[idx] = { ...last, truthfulness: lastTruthfulness }
    return next
  }, [detail?.messages, lastTruthfulness])

  useEffect(() => {
    if (headerSeeded || !llmConfig) return
    const provider = pickDefaultChatProvider(llmConfig)
    const model = pickDefaultChatModel(llmConfig, provider)
    setHeader((h) => ({ ...h, provider, model }))
    setHeaderSeeded(true)
  }, [llmConfig, headerSeeded])

  const refreshList = useCallback(async () => {
    try {
      const list = await chatsClient.list()
      setChats(list)
      setError(null)
      return list
    } catch (e) {
      setError((e as Error).message)
      return null
    }
  }, [setChats, setError])

  const newChat = useCallback(async () => {
    if (creatingRef.current) return null
    creatingRef.current = true
    const provider = _header.provider || 'ollama'
    const model = _header.model || 'qwen2.5:7b'
    try {
      const d = await chatsClient.create({
        knowledge_scope: _header.scope,
        provider,
        model,
      })
      setActive(d.id)
      setDetail(d)
      await refreshList()
      return d
    } catch (e) {
      setError((e as Error).message)
      toast({ title: 'Could not create chat', description: (e as Error).message, tone: 'error' })
      return null
    } finally {
      creatingRef.current = false
    }
  }, [_header, refreshList, setActive, setDetail, setError, toast])

  useEffect(() => {
    void (async () => {
      const list = await refreshList()
      if (bootstrapped || !list) return
      setBootstrapped(true)
      if (activeId) return
      if (list.length > 0) {
        setActive(list[0].id)
        return
      }
      await newChat()
    })()
    // Bootstrap once after first list load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshList])

  useEffect(() => {
    if (!activeId) return
    void (async () => {
      try {
        const d = await chatsClient.get(activeId)
        setDetail(d)
        setHeader({ provider: d.provider, model: d.model, scope: d.knowledge_scope })
      } catch (e) {
        setError((e as Error).message)
      }
    })()
  }, [activeId, setDetail, setError])

  useEffect(() => {
    const t = setTimeout(() => {
      if (!searchQ.trim()) {
        void refreshList()
        return
      }
      void (async () => {
        try {
          const hits = await chatsClient.search(searchQ)
          const seen = new Set<string>()
          const subset = []
          for (const h of hits) {
            if (seen.has(h.chat_id)) continue
            seen.add(h.chat_id)
            subset.push({
              id: h.chat_id,
              title: h.preview.slice(0, 48),
              updated_at: new Date().toISOString(),
              model: '',
              provider: '',
              pinned: false,
            })
          }
          setChats(subset as never)
        } catch (e) {
          setError((e as Error).message)
        }
      })()
    }, 350)
    return () => clearTimeout(t)
  }, [searchQ, refreshList, setChats, setError])

  const handleDeleteChat = useCallback(
    async (id: string) => {
      const target = chats.find((c) => c.id === id)
      const label = target?.title?.trim() || 'Untitled'
      const confirmed = window.confirm(`Delete chat "${label}"? This cannot be undone.`)
      if (!confirmed) return
      setDeletingChatId(id)
      setError(null)
      try {
        await chatsClient.remove(id)
        if (activeId === id) {
          setActive(null)
          setDetail(null)
        }
        const list = await refreshList()
        if (activeId === id) {
          if (list && list.length > 0) setActive(list[0].id)
          else await newChat()
        }
        toast({ title: 'Chat deleted', tone: 'success' })
      } catch (e) {
        setError((e as Error).message)
        toast({ title: 'Delete failed', description: (e as Error).message, tone: 'error' })
      } finally {
        setDeletingChatId(null)
      }
    },
    [activeId, chats, newChat, refreshList, setActive, setDetail, setError, toast],
  )

  const handlePinChat = useCallback(
    async (id: string, pinned: boolean) => {
      try {
        await chatsClient.pin(id, pinned)
        await refreshList()
        toast({ title: pinned ? 'Chat pinned' : 'Chat unpinned', tone: 'success' })
      } catch (e) {
        toast({ title: 'Pin failed', description: (e as Error).message, tone: 'error' })
      }
    },
    [refreshList, toast],
  )

  const handleProviderModelChange = useCallback(
    async (p: string, m: string) => {
      setHeader((h) => ({ ...h, provider: p, model: m }))
      if (!activeId || !detail) return
      const previous = detail
      setDetail({ ...detail, provider: p, model: m })
      try {
        const updated = await chatsClient.patch(activeId, { provider: p, model: m })
        setDetail(updated)
        await refreshList()
      } catch (e) {
        setDetail(previous)
        setError((e as Error).message)
      }
    },
    [activeId, detail, setDetail, refreshList, setError],
  )

  const handleScopeToggle = useCallback(
    async (s: string) => {
      setHeader((h) => ({ ...h, scope: s }))
      if (!activeId || !detail) return
      const previous = detail
      setDetail({ ...detail, knowledge_scope: s })
      try {
        const updated = await chatsClient.patch(activeId, { knowledge_scope: s })
        setDetail(updated)
        await refreshList()
      } catch (e) {
        setDetail(previous)
        setError((e as Error).message)
      }
    },
    [activeId, detail, setDetail, refreshList, setError],
  )

  const runStream = useCallback(
    async (path: string, body: object | null) => {
      if (!activeId) return
      setLoading(true)
      resetStream()
      setError(null)
      setSourcesOpen(false)
      setLastTruthfulness(null)
      try {
        await streamChatPost(path, body, (ev) => {
          if (ev.event === 'token') appendStream(ev.data.text)
          if (ev.event === 'retrieval') {
            setPendingChunks(ev.data.chunks as RetrievedChunk[])
            setSourcesChunks(ev.data.chunks as RetrievedChunk[])
            setSourcesOpen(true)
          }
          if (ev.event === 'meta') setLastMeta(ev.data)
          if (ev.event === 'final' && ev.data.truthfulness) {
            setLastTruthfulness(ev.data.truthfulness)
          }
          if (ev.event === 'error') setError(ev.data.message)
        })
        const d = await chatsClient.get(activeId)
        setDetail(d)
        resetStream()
        await refreshList()
      } catch (e) {
        setError((e as Error).message)
        toast({ title: 'Chat failed', description: (e as Error).message, tone: 'error' })
      } finally {
        setLoading(false)
      }
    },
    [
      activeId,
      appendStream,
      refreshList,
      resetStream,
      setDetail,
      setError,
      setLoading,
      setPendingChunks,
      toast,
    ],
  )

  const sendMessage = useCallback(
    async (
      text: string,
      chatId?: string,
      opts?: { groundingMode: GroundingMode; includeWebSearch: boolean },
    ) => {
      const id = chatId || activeId
      if (!id) return
      const grounding = opts?.groundingMode ?? groundingMode
      const webSearch = opts?.includeWebSearch ?? includeWebSearch
      let current = detail
      if (!current || current.id !== id) {
        current = await chatsClient.get(id)
        setDetail(current)
        setActive(id)
      }
      const optimistic = {
        ...current,
        messages: [
          ...current.messages,
          {
            id: `tmp-${Date.now()}`,
            role: 'user',
            content: text,
            parent_id: null,
            created_at: new Date().toISOString(),
            citations: [],
          },
        ],
      }
      setDetail(optimistic)
      await runStream(`/chats/${id}/messages`, {
        message: text,
        provider: current.provider,
        model: current.model,
        scope: current.knowledge_scope,
        system_prompt: current.system_prompt,
        grounding_mode: grounding,
        include_web_search: webSearch,
      })
    },
    [activeId, detail, groundingMode, includeWebSearch, runStream, setActive, setDetail],
  )

  useEffect(() => {
    if (!pendingPrompt?.trim() || !bootstrapped) return
    const text = pendingPrompt.trim()
    onPendingPromptConsumed?.()
    void (async () => {
      let id = activeId
      if (!id) {
        const created = await newChat()
        id = created?.id ?? null
      }
      if (!id) return
      await sendMessage(text, id)
    })()
  }, [pendingPrompt, bootstrapped, activeId, newChat, onPendingPromptConsumed, sendMessage])

  useEffect(() => {
    const pending = pendingSendRef.current
    if (!pending || !activeId || !detail || detail.id !== activeId || loading) return
    pendingSendRef.current = null
    void sendMessage(pending, activeId)
  }, [activeId, detail, loading, sendMessage])

  const handleSeedQuestion = useCallback(
    (q: string) => {
      if (activeId && detail) {
        void sendMessage(q)
        return
      }
      pendingSendRef.current = q
      void newChat()
    },
    [activeId, detail, newChat, sendMessage],
  )

  const handleRegenerate = useCallback(
    (messageId: string) => {
      if (!activeId) return
      void runStream(chatsClient.regeneratePath(activeId, messageId), null)
    },
    [activeId, runStream],
  )

  const handleEdit = useCallback(
    (messageId: string, content: string) => {
      if (!activeId || !content.trim()) return
      void runStream(chatsClient.editPath(activeId, messageId), { content })
    },
    [activeId, runStream],
  )

  const lastAssistantMessageId = useMemo(() => {
    const msgs = detail?.messages ?? []
    for (let i = msgs.length - 1; i >= 0; i -= 1) {
      if (msgs[i].role === 'assistant' && !msgs[i].id.startsWith('tmp-')) {
        return msgs[i].id
      }
    }
    return null
  }, [detail?.messages])

  const handleSaveToWiki = useCallback(async () => {
    if (!activeId || !lastAssistantMessageId) {
      toast({ title: 'Nothing to save', description: 'Send a message first.', tone: 'error' })
      return
    }
    try {
      const result = await chatsClient.saveToWiki(activeId, lastAssistantMessageId)
      toast({
        title: 'Saved to wiki',
        description: `wiki/${result.path}${result.ingested ? ` (${result.chunk_count} chunks)` : ''}`,
        tone: 'success',
      })
    } catch (e) {
      toast({ title: 'Save failed', description: (e as Error).message, tone: 'error' })
    }
  }, [activeId, lastAssistantMessageId, toast])

  const handleUpdateMemory = useCallback(async () => {
    if (!activeId) return
    try {
      await chatsClient.updateMemory(activeId)
      toast({ title: 'Rolling memory updated', tone: 'success' })
    } catch (e) {
      toast({ title: 'Memory update failed', description: (e as Error).message, tone: 'error' })
    }
  }, [activeId, toast])

  const openVault = useCallback(
    (path: string) => {
      window.location.hash = vaultPathQuery(path)
      onNavigateVault?.()
    },
    [onNavigateVault],
  )

  const conversationList = (
    <ConversationList
      chats={chats}
      activeId={activeId}
      onSelect={(id) => {
        setActive(id)
        setMobileListOpen(false)
      }}
      onNew={() => {
        void newChat()
        setMobileListOpen(false)
      }}
      onDelete={(id) => void handleDeleteChat(id)}
      onPin={(id, pinned) => void handlePinChat(id, pinned)}
      deletingId={deletingChatId}
      searchQuery={searchQ}
      onSearchChange={setSearchQ}
    />
  )

  return (
    <div className="flex h-full flex-col gap-2">
      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <div className="flex items-center gap-2 px-1">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setMobileListOpen(true)}
          aria-label="Open conversations"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="hidden md:inline-flex"
          onClick={() => setShowList((s) => !s)}
          aria-label={showList ? 'Hide conversations' : 'Show conversations'}
        >
          {showList ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>
        <div className="min-w-0 flex-1">
          <ChatHeader
            title={detail?.title}
            provider={detail?.provider || _header.provider}
            model={detail?.model || _header.model}
            scope={detail?.knowledge_scope || _header.scope}
            allowedModelsByProvider={llmConfig?.allowed_models_by_provider}
            defaultModelByProvider={llmConfig?.default_model_by_provider}
            providerKeyConfigured={llmConfig?.provider_key_configured}
            onProviderModelChange={handleProviderModelChange}
            onScopeToggle={handleScopeToggle}
          />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-xl border border-border bg-background">
        {showList ? (
          <div className="hidden w-60 shrink-0 border-r border-border p-3 md:block lg:w-72">
            {conversationList}
          </div>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <MessageStream
              messages={displayMessages}
              sessionFiles={sessionFiles}
              streaming={streamText || undefined}
              streamingChunks={loading ? pendingChunks : undefined}
              searching={loading && !streamText}
              onOpenVault={openVault}
              onSeedQuestion={handleSeedQuestion}
              onOpenSources={({ citations, chunks }) => {
                setSourcesCitations(citations)
                setSourcesChunks(chunks)
                setSourcesOpen(true)
              }}
              onRegenerate={handleRegenerate}
              onEdit={handleEdit}
            />
          </div>
          <div className="border-t border-border p-3">
            <Composer
              onSend={(t, opts) => void sendMessage(t, undefined, opts)}
              personaLabel={personaLabel}
              onOpenPersonaSettings={onNavigateSettings}
              groundingMode={groundingMode}
              onGroundingModeChange={setGroundingMode}
              includeWebSearch={includeWebSearch}
              onIncludeWebSearchChange={setIncludeWebSearch}
              webSearchAvailable={webSearchAvailable}
              onSaveToWiki={lastAssistantMessageId ? handleSaveToWiki : undefined}
              onUpdateMemory={handleUpdateMemory}
              disabled={loading || !activeId}
              lastMeta={lastMeta}
            />
          </div>
        </div>

        {sourcesOpen ? (
          <SourcesDrawer
            open={sourcesOpen}
            onClose={() => setSourcesOpen(false)}
            citations={sourcesCitations}
            chunks={sourcesChunks}
            sessionFiles={sessionFiles}
            onOpenVault={openVault}
          />
        ) : null}
      </div>

      {mobileListOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="Close conversations"
            onClick={() => setMobileListOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col bg-card p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold">Conversations</p>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMobileListOpen(false)}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="min-h-0 flex-1">{conversationList}</div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
