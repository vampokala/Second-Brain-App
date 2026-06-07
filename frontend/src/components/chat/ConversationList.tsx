import { formatDistanceToNow } from 'date-fns'
import { useState } from 'react'

import type { ChatListItem } from '../../api/chatsClient'

type Props = {
  chats: ChatListItem[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  deletingId?: string | null
  searchQuery: string
  onSearchChange: (q: string) => void
}

export function ConversationList({
  chats,
  activeId,
  onSelect,
  onNew,
  onDelete,
  deletingId,
  searchQuery,
  onSearchChange,
}: Props) {
  const [recentCollapsed, setRecentCollapsed] = useState(false)
  const [menuOpenForId, setMenuOpenForId] = useState<string | null>(null)
  const pinned = chats.filter((c) => c.pinned)
  const rest = chats.filter((c) => !c.pinned)

  const renderChatRow = (c: ChatListItem) => (
    <div
      className={`group relative flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-secondary ${
        c.id === activeId ? 'bg-primary/10 text-primary' : ''
      }`}
    >
      <button
        type="button"
        className={`min-w-0 flex-1 text-left ${c.id === activeId ? 'font-semibold' : ''}`}
        onClick={() => {
          onSelect(c.id)
          setMenuOpenForId(null)
        }}
      >
        <div className="truncate">{c.title || 'Untitled'}</div>
        <div className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(c.updated_at), { addSuffix: true })}
        </div>
      </button>
      <button
        type="button"
        className="rounded px-1.5 py-0.5 text-muted-foreground hover:bg-secondary hover:text-foreground group-hover:opacity-100 md:opacity-0"
        onClick={() => setMenuOpenForId((prev) => (prev === c.id ? null : c.id))}
        aria-label="Chat actions"
      >
        ⋯
      </button>
      {menuOpenForId === c.id ? (
        <div className="absolute right-2 top-8 z-10 rounded-md border border-border bg-card p-1 shadow-lg">
          <button
            type="button"
            className="block w-full rounded px-2 py-1 text-left text-xs text-destructive hover:bg-destructive/10"
            onClick={() => {
              setMenuOpenForId(null)
              onDelete(c.id)
            }}
            disabled={deletingId === c.id}
          >
            {deletingId === c.id ? 'Deleting…' : 'Delete chat'}
          </button>
        </div>
      ) : null}
    </div>
  )

  return (
    <div className="flex h-full flex-col gap-3">
      <button
        type="button"
        className="w-full rounded-xl bg-primary py-2 text-sm font-semibold text-white"
        onClick={onNew}
      >
        + New chat
      </button>
      <input
        className="w-full rounded-lg border border-border px-3 py-2 text-sm"
        placeholder="Search messages (server)…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto text-sm">
        {pinned.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Pinned</div>
            <ul className="space-y-1">
              {pinned.map((c) => (
                <li key={c.id}>
                  {renderChatRow(c)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div>
          <button
            type="button"
            className="mb-1 flex w-full items-center justify-between text-xs font-semibold uppercase text-muted-foreground"
            onClick={() => setRecentCollapsed((v) => !v)}
          >
            <span>Recent</span>
            <span>{recentCollapsed ? 'Show' : 'Hide'}</span>
          </button>
          {!recentCollapsed ? (
            <ul className="space-y-1">
              {rest.map((c) => (
                <li key={c.id}>
                  {renderChatRow(c)}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  )
}
