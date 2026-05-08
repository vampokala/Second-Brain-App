import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { CitationPill } from './CitationPill'

type Msg = {
  id: string
  role: string
  content: string
  citations: Array<Record<string, unknown>>
}

type Props = {
  messages: Msg[]
  streaming?: string
  onOpenVault?: (hash: string) => void
}

export function MessageStream({ messages, streaming, onOpenVault }: Props) {
  return (
    <div className="space-y-4 overflow-y-auto pr-2 text-sm">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`rounded-xl p-3 ${m.role === 'user' ? 'ml-8 bg-slate-100' : 'mr-8 bg-white shadow-sm'}`}
        >
          <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{m.role}</div>
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          </div>
          {m.citations?.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {m.citations.map((c) => (
                <CitationPill
                  key={String(c.chunk_id)}
                  source={String(c.source || '')}
                  label={c.title ? String(c.title) : undefined}
                  onOpenVault={onOpenVault}
                />
              ))}
            </div>
          ) : null}
        </div>
      ))}
      {streaming ? (
        <div className="mr-8 rounded-xl bg-white p-3 shadow-sm">
          <div className="mb-1 text-xs font-semibold uppercase text-slate-500">assistant</div>
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown>
          </div>
        </div>
      ) : null}
    </div>
  )
}
