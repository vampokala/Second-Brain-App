import { formatDistanceToNow } from 'date-fns'

import type { ChatListItem } from '../../api/chatsClient'

type Props = {
  chats: ChatListItem[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  searchQuery: string
  onSearchChange: (q: string) => void
}

export function ConversationList({
  chats,
  activeId,
  onSelect,
  onNew,
  searchQuery,
  onSearchChange,
}: Props) {
  const pinned = chats.filter((c) => c.pinned)
  const rest = chats.filter((c) => !c.pinned)
  return (
    <div className="flex h-full flex-col gap-3">
      <button
        type="button"
        className="w-full rounded-xl bg-blue-600 py-2 text-sm font-semibold text-white"
        onClick={onNew}
      >
        + New chat
      </button>
      <input
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        placeholder="Search messages (server)…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto text-sm">
        {pinned.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-semibold uppercase text-slate-500">Pinned</div>
            <ul className="space-y-1">
              {pinned.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`w-full rounded-lg px-2 py-1.5 text-left hover:bg-slate-100 ${
                      c.id === activeId ? 'bg-blue-50 font-semibold text-blue-900' : ''
                    }`}
                    onClick={() => onSelect(c.id)}
                  >
                    <div className="truncate">{c.title || 'Untitled'}</div>
                    <div className="text-xs text-slate-500">
                      {formatDistanceToNow(new Date(c.updated_at), { addSuffix: true })}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div>
          <div className="mb-1 text-xs font-semibold uppercase text-slate-500">Recent</div>
          <ul className="space-y-1">
            {rest.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={`w-full rounded-lg px-2 py-1.5 text-left hover:bg-slate-100 ${
                    c.id === activeId ? 'bg-blue-50 font-semibold text-blue-900' : ''
                  }`}
                  onClick={() => onSelect(c.id)}
                >
                  <div className="truncate">{c.title || 'Untitled'}</div>
                  <div className="text-xs text-slate-500">
                    {formatDistanceToNow(new Date(c.updated_at), { addSuffix: true })}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
