import { useCallback, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'

import { Button } from '../components/ui/button'
import { chatsClient } from '../api/chatsClient'
import { fetchLlmConfig } from '../api/client'
import type { LlmConfigModel } from '../api/generated'
import { streamChatPost } from '../lib/streamChat'
import { vaultPathQuery } from '../lib/vaultDeepLink'
import { useChatStore, type RetrievedChunk } from '../state/useChatStore'
import { ChatHeader } from '../components/chat/ChatHeader'
import { Composer } from '../components/chat/Composer'
import { ConversationList } from '../components/chat/ConversationList'
import { MessageStream } from '../components/chat/MessageStream'

function pickDefaultChatProvider(cfg: LlmConfigModel): string {
  const keys = Object.keys(cfg.allowed_models_by_provider)
  const isUsable = (p: string) =>
    (cfg.allowed_models_by_provider[p]?.length ?? 0) > 0 && cfg.provider_key_configured[p] === true
  if (isUsable(cfg.default_provider)) return cfg.default_provider
  const usable = keys.find(isUsable)
  if (usable) return usable
  return keys.includes(cfg.default_provider) ? cfg.default_provider : keys[0] ?? 'ollama'
}

function pickDefaultChatModel(cfg: LlmConfigModel, provider: string): string {
  const models = cfg.allowed_models_by_provider[provider] ?? []
  const def = cfg.default_model_by_provider[provider]
  if (def && models.includes(def)) return def
  return models[0] ?? ''
}

type Props = {
  onNavigateVault?: () => void
}

export function ChatTab({ onNavigateVault }: Props) {
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
  const [_header, setHeader] = useState({ provider: '', model: '', scope: 'vault' })
  const [headerSeeded, setHeaderSeeded] = useState(false)
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null)

  const { data: llmConfig } = useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLlmConfig,
    staleTime: Infinity,
  })

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
    } catch (e) {
      setError((e as Error).message)
    }
  }, [setChats, setError])

  useEffect(() => {
    void refreshList()
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
            if (!seen.has(h.chat_id)) {
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
          }
          setChats(subset as never)
        } catch {
          /* ignore */
        }
      })()
    }, 350)
    return () => clearTimeout(t)
  }, [searchQ, refreshList, setChats])

  async function newChat() {
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
    } catch (e) {
      setError((e as Error).message)
    }
  }

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
        await refreshList()
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setDeletingChatId(null)
      }
    },
    [activeId, chats, refreshList, setActive, setDetail, setError],
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

  async function sendMessage(text: string) {
    if (!activeId || !detail) return
    setLoading(true)
    resetStream()
    setError(null)
    const optimistic = {
      ...detail,
      messages: [
        ...detail.messages,
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
    try {
      await streamChatPost(
        `/chats/${activeId}/messages`,
        {
          message: text,
          provider: detail.provider,
          model: detail.model,
          scope: detail.knowledge_scope,
          system_prompt: detail.system_prompt,
        },
        (ev) => {
          if (ev.event === 'token') appendStream(ev.data.text)
          // Live preview of the retrieved context while the answer streams in;
          // the persisted copy comes back on the re-fetched detail below.
          if (ev.event === 'retrieval') setPendingChunks(ev.data.chunks as RetrievedChunk[])
          if (ev.event === 'error') setError(ev.data.message)
        },
      )
      const d = await chatsClient.get(activeId)
      setDetail(d)
      resetStream()
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-card flex h-full flex-col gap-3 p-4">
      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="hidden md:inline-flex"
          onClick={() => setShowList((s) => !s)}
          aria-label={showList ? 'Hide conversations' : 'Show conversations'}
          title={showList ? 'Hide conversations' : 'Show conversations'}
        >
          {showList ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>
        <div className="min-w-0 flex-1">
          <ChatHeader
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
      <div className="flex min-h-0 flex-1 gap-3">
        {showList ? (
          <div className="hidden w-72 shrink-0 md:block">
            <ConversationList
              chats={chats}
              activeId={activeId}
              onSelect={(id) => setActive(id)}
              onNew={() => void newChat()}
              onDelete={(id) => void handleDeleteChat(id)}
              deletingId={deletingChatId}
              searchQuery={searchQ}
              onSearchChange={setSearchQ}
            />
          </div>
        ) : null}
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border bg-secondary/40 p-3">
            <MessageStream
              messages={detail?.messages || []}
              streaming={streamText || undefined}
              streamingChunks={loading ? pendingChunks : undefined}
              onOpenVault={(path) => {
                window.location.hash = vaultPathQuery(path)
                onNavigateVault?.()
              }}
            />
          </div>
          <Composer onSend={(t) => void sendMessage(t)} disabled={loading || !activeId} />
        </div>
      </div>
    </div>
  )
}
