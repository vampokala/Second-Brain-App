import { useCallback, useEffect, useState } from 'react'

import { chatsClient } from '../api/chatsClient'
import { streamChatPost } from '../lib/streamChat'
import { vaultPathQuery } from '../lib/vaultDeepLink'
import { useChatStore } from '../state/useChatStore'
import { ChatHeader } from '../components/chat/ChatHeader'
import { Composer } from '../components/chat/Composer'
import { ConversationList } from '../components/chat/ConversationList'
import { MessageStream } from '../components/chat/MessageStream'

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
    setChats,
    setActive,
    setDetail,
    appendStream,
    resetStream,
    setLoading,
    setError,
  } = useChatStore()
  const [searchQ, setSearchQ] = useState('')
  const [_header, setHeader] = useState({ provider: 'ollama', model: 'qwen2.5:7b', scope: 'vault' })

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
    try {
      const d = await chatsClient.create({
        knowledge_scope: _header.scope,
        provider: _header.provider,
        model: _header.model,
      })
      setActive(d.id)
      setDetail(d)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    }
  }

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
    <div className="app-card flex min-h-[28rem] flex-col gap-4 p-5">
      <h2 className="text-lg font-bold text-slate-900">Chat</h2>
      {error ? <div className="rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{error}</div> : null}
      <ChatHeader
        provider={detail?.provider || _header.provider}
        model={detail?.model || _header.model}
        scope={detail?.knowledge_scope || _header.scope}
        onProviderModelChange={(p, m) => setHeader((h) => ({ ...h, provider: p, model: m }))}
        onScopeToggle={(s) => setHeader((h) => ({ ...h, scope: s }))}
      />
      <div className="grid min-h-[22rem] flex-1 grid-cols-1 gap-4 md:grid-cols-12">
        <div className="md:col-span-4">
          <ConversationList
            chats={chats}
            activeId={activeId}
            onSelect={(id) => setActive(id)}
            onNew={() => void newChat()}
            searchQuery={searchQ}
            onSearchChange={setSearchQ}
          />
        </div>
        <div className="flex flex-col gap-3 md:col-span-8">
          <div className="min-h-[12rem] flex-1 rounded-xl border border-slate-100 bg-slate-50 p-3">
            <MessageStream
              messages={detail?.messages || []}
              streaming={streamText || undefined}
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
