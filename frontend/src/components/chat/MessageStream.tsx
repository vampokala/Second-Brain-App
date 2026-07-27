import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { BookOpen, Loader2, Pencil, RefreshCw } from 'lucide-react'

import type { SessionFile } from '../../api/client'
import { citationLabel } from '../../lib/citationProvenance'
import { SEED_QUESTIONS } from '../../lib/seedQuestions'
import type { ChatTruthfulness } from '../../lib/streamChat'
import type { RetrievedChunk } from '../../state/useChatStore'
import { CopyButton } from '../ui/copy-button'
import { Button } from '../ui/button'
import { CitationPill } from './CitationPill'
import type { SourceCitation } from './SourcesDrawer'
import { TruthfulnessBadge } from './TruthfulnessBadge'

type Msg = {
  id: string
  role: string
  content: string
  citations: Array<Record<string, unknown>>
  retrieved?: RetrievedChunk[]
  truthfulness?: ChatTruthfulness
}

type Props = {
  messages: Msg[]
  streaming?: string
  streamingChunks?: RetrievedChunk[]
  searching?: boolean
  sessionFiles?: SessionFile[]
  onOpenVault?: (hash: string) => void
  onSeedQuestion?: (q: string) => void
  onOpenSources?: (payload: { citations: SourceCitation[]; chunks: RetrievedChunk[] }) => void
  onRegenerate?: (messageId: string) => void
  onEdit?: (messageId: string, content: string) => void
}

function toCitations(raw: Array<Record<string, unknown>>): SourceCitation[] {
  return raw.map((c) => ({
    chunk_id: c.chunk_id != null ? String(c.chunk_id) : undefined,
    source: c.source != null ? String(c.source) : undefined,
    title: c.title != null ? String(c.title) : undefined,
    score: typeof c.score === 'number' ? c.score : undefined,
    preview: c.preview != null ? String(c.preview) : undefined,
    provenance:
      c.provenance === 'global' || c.provenance === 'yours' ? c.provenance : undefined,
  }))
}

function EmptyState({ onSeedQuestion }: { onSeedQuestion?: (q: string) => void }) {
  return (
    <div className="flex h-full min-h-[12rem] flex-col items-center justify-center gap-4 px-4 text-center">
      <div>
        <p className="text-base font-semibold text-foreground">Ask your knowledge base</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a starter question or type your own below.
        </p>
      </div>
      <div className="flex w-full max-w-lg flex-col gap-2">
        {SEED_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm hover:border-primary/40 hover:bg-primary/5"
            onClick={() => onSeedQuestion?.(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageActions({
  messageId,
  role,
  content,
  citations,
  retrieved,
  onOpenSources,
  onRegenerate,
  onEdit,
}: {
  messageId: string
  role: string
  content: string
  citations: Array<Record<string, unknown>>
  retrieved?: RetrievedChunk[]
  onOpenSources?: Props['onOpenSources']
  onRegenerate?: Props['onRegenerate']
  onEdit?: Props['onEdit']
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(content)

  if (messageId.startsWith('tmp-')) return null

  if (editing && role === 'user') {
    return (
      <div className="mt-2 space-y-2">
        <textarea
          className="w-full rounded-lg border border-border p-2 text-sm"
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              onEdit?.(messageId, draft.trim())
              setEditing(false)
            }}
            disabled={!draft.trim()}
          >
            Save &amp; fork
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1">
      {role === 'assistant' && (citations?.length || retrieved?.length) ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            onOpenSources?.({
              citations: toCitations(citations || []),
              chunks: retrieved || [],
            })
          }
        >
          <BookOpen className="h-3.5 w-3.5" />
          Sources
        </Button>
      ) : null}
      {role === 'assistant' && onRegenerate ? (
        <Button size="sm" variant="ghost" onClick={() => onRegenerate(messageId)}>
          <RefreshCw className="h-3.5 w-3.5" />
          Regenerate
        </Button>
      ) : null}
      {role === 'user' && onEdit ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setDraft(content)
            setEditing(true)
          }}
        >
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </Button>
      ) : null}
    </div>
  )
}

export function MessageStream({
  messages,
  streaming,
  streamingChunks,
  searching,
  sessionFiles,
  onOpenVault,
  onSeedQuestion,
  onOpenSources,
  onRegenerate,
  onEdit,
}: Props) {
  const empty = messages.length === 0 && !streaming && !searching

  if (empty) {
    return <EmptyState onSeedQuestion={onSeedQuestion} />
  }

  return (
    <div className="space-y-4 overflow-y-auto pr-2 text-sm">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`group rounded-xl p-3 ${m.role === 'user' ? 'ml-8 bg-secondary' : 'mr-8 bg-card shadow-sm'}`}
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase text-muted-foreground">{m.role}</span>
            <div className="opacity-0 transition-opacity group-hover:opacity-100">
              <CopyButton text={m.content} label={`Copy ${m.role} message`} />
            </div>
          </div>
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          </div>
          {m.truthfulness ? (
            <div className="mt-2">
              <TruthfulnessBadge truthfulness={m.truthfulness} />
            </div>
          ) : null}
          {m.citations?.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {m.citations.map((c) => {
                const source = String(c.source || '')
                const title = c.title ? String(c.title) : undefined
                const provenance =
                  c.provenance === 'global' || c.provenance === 'yours'
                    ? c.provenance
                    : sessionFiles?.length
                      ? citationLabel({ source, title: title ?? null }, sessionFiles)
                      : undefined
                return (
                  <CitationPill
                    key={String(c.chunk_id)}
                    source={source}
                    label={title}
                    score={typeof c.score === 'number' ? c.score : undefined}
                    provenance={provenance}
                    sessionFiles={sessionFiles}
                    onOpenVault={onOpenVault}
                  />
                )
              })}
            </div>
          ) : null}
          <MessageActions
            messageId={m.id}
            role={m.role}
            content={m.content}
            citations={m.citations}
            retrieved={m.retrieved}
            onOpenSources={onOpenSources}
            onRegenerate={onRegenerate}
            onEdit={onEdit}
          />
        </div>
      ))}
      {searching && !streaming ? (
        <div className="mr-8 flex items-center gap-2 rounded-xl bg-card p-3 text-sm text-muted-foreground shadow-sm">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Searching knowledge…
        </div>
      ) : null}
      {streaming ? (
        <div className="group mr-8 rounded-xl bg-card p-3 shadow-sm">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase text-muted-foreground">assistant</span>
            <div className="opacity-0 transition-opacity group-hover:opacity-100">
              <CopyButton text={streaming} label="Copy assistant message" />
            </div>
          </div>
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown>
          </div>
          {streamingChunks?.length ? (
            <Button
              size="sm"
              variant="ghost"
              className="mt-2"
              onClick={() =>
                onOpenSources?.({
                  citations: [],
                  chunks: streamingChunks,
                })
              }
            >
              <BookOpen className="h-3.5 w-3.5" />
              Sources ({streamingChunks.length})
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
