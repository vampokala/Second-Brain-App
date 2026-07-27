import { ExternalLink, X } from 'lucide-react'

import type { SessionFile } from '../../api/client'
import type { CitationProvenance } from '../../lib/citationProvenance'
import type { RetrievedChunk } from '../../state/useChatStore'
import { Button } from '../ui/button'
import { CitationPill } from './CitationPill'

export type SourceCitation = {
  chunk_id?: string
  source?: string
  title?: string
  score?: number
  preview?: string
  provenance?: CitationProvenance
}

type Props = {
  open: boolean
  onClose: () => void
  citations: SourceCitation[]
  chunks: RetrievedChunk[]
  sessionFiles?: SessionFile[]
  onOpenVault?: (path: string) => void
}

function scoreLabel(score: number | undefined): string | null {
  if (typeof score !== 'number' || Number.isNaN(score)) return null
  return score.toFixed(3)
}

export function SourcesDrawer({ open, onClose, citations, chunks, sessionFiles, onOpenVault }: Props) {
  if (!open) return null

  const hasCitations = citations.length > 0
  const hasChunks = chunks.length > 0

  return (
    <aside
      className="flex w-full shrink-0 flex-col border-t border-border bg-card md:w-80 md:border-l md:border-t-0"
      aria-label="Sources"
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <h3 className="text-sm font-semibold text-foreground">Sources</h3>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close sources">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-3 text-sm">
        {!hasCitations && !hasChunks ? (
          <p className="text-muted-foreground">No sources for this answer yet.</p>
        ) : null}

        {hasCitations ? (
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Citations
            </h4>
            <ul className="space-y-3">
              {citations.map((c, i) => {
                const source = String(c.source || '')
                const score = scoreLabel(c.score)
                return (
                  <li key={String(c.chunk_id || i)} className="rounded-lg border border-border p-2">
                    <div className="flex flex-wrap items-center gap-1">
                      <CitationPill
                        source={source}
                        label={c.title ? String(c.title) : undefined}
                        score={c.score}
                        provenance={c.provenance}
                        sessionFiles={sessionFiles}
                        onOpenVault={onOpenVault}
                      />
                      {score ? (
                        <span className="text-xs text-muted-foreground">score {score}</span>
                      ) : null}
                    </div>
                    {c.preview ? (
                      <p className="mt-2 line-clamp-4 text-xs text-muted-foreground">{c.preview}</p>
                    ) : null}
                    {source && onOpenVault ? (
                      <button
                        type="button"
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary"
                        onClick={() => onOpenVault(source)}
                      >
                        <ExternalLink className="h-3 w-3" />
                        Open in vault
                      </button>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </section>
        ) : null}

        {hasChunks ? (
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Retrieved chunks
            </h4>
            <ul className="space-y-2">
              {chunks.map((c) => (
                <li key={c.id} className="rounded-lg bg-muted/60 p-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="truncate font-medium" title={c.source || c.id}>
                      {c.source || c.id}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      score {c.score.toFixed(3)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{c.preview}</p>
                  {c.source && onOpenVault ? (
                    <button
                      type="button"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary"
                      onClick={() => onOpenVault(c.source)}
                    >
                      <ExternalLink className="h-3 w-3" />
                      Open in vault
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </aside>
  )
}
