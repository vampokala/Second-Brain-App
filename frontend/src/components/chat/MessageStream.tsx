import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { RetrievedChunk } from '../../state/useChatStore'
import { CitationPill } from './CitationPill'

type Msg = {
  id: string
  role: string
  content: string
  citations: Array<Record<string, unknown>>
  retrieved?: RetrievedChunk[]
}

type Props = {
  messages: Msg[]
  streaming?: string
  streamingChunks?: RetrievedChunk[]
  onOpenVault?: (hash: string) => void
}

function RetrievedChunksPanel({ chunks }: { chunks: RetrievedChunk[] }) {
  if (!chunks.length) return null
  return (
    <details className="mt-3 rounded-lg border border-border bg-muted/50 p-2 text-xs">
      <summary className="cursor-pointer select-none font-medium text-muted-foreground">
        Retrieved chunks ({chunks.length})
      </summary>
      <ul className="mt-2 space-y-2">
        {chunks.map((c) => (
          <li key={c.id} className="rounded-md bg-card p-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="truncate font-medium text-foreground" title={c.source || c.id}>
                {c.source || c.id}
              </span>
              <span className="shrink-0 text-muted-foreground">score {c.score.toFixed(3)}</span>
            </div>
            <p className="mt-1 text-muted-foreground">{c.preview}</p>
          </li>
        ))}
      </ul>
    </details>
  )
}

export function MessageStream({ messages, streaming, streamingChunks, onOpenVault }: Props) {
  return (
    <div className="space-y-4 overflow-y-auto pr-2 text-sm">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`rounded-xl p-3 ${m.role === 'user' ? 'ml-8 bg-secondary' : 'mr-8 bg-card shadow-sm'}`}
        >
          <div className="mb-1 text-xs font-semibold uppercase text-muted-foreground">{m.role}</div>
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
          {m.role === 'assistant' && m.retrieved?.length ? (
            <RetrievedChunksPanel chunks={m.retrieved} />
          ) : null}
        </div>
      ))}
      {streaming ? (
        <div className="mr-8 rounded-xl bg-card p-3 shadow-sm">
          <div className="mb-1 text-xs font-semibold uppercase text-muted-foreground">assistant</div>
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown>
          </div>
          {streamingChunks?.length ? <RetrievedChunksPanel chunks={streamingChunks} /> : null}
        </div>
      ) : null}
    </div>
  )
}
