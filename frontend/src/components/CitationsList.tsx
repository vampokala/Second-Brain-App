import type { SessionFile } from '../api/client'
import type { CitationModel } from '../api/generated'
import { citationLabel } from '../lib/citationProvenance'

export function CitationsList({
  citations,
  sessionFiles,
}: {
  citations: CitationModel[]
  sessionFiles: SessionFile[]
}) {
  return (
    <section className="app-card p-5">
      <h2 className="mb-3 text-lg font-semibold text-foreground">Citations</h2>
      {citations.length === 0 ? (
        <p className="text-sm text-muted-foreground">No citations returned yet.</p>
      ) : (
        <ul className="space-y-3">
          {citations.map((citation) => {
            const label = citationLabel(citation, sessionFiles)
            return (
              <li key={`${citation.raw_id}-${citation.chunk_id}`} className="rounded-xl bg-muted p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-foreground px-2 py-1 text-xs font-semibold text-white">
                    [{label === 'yours' ? 'yours' : 'global'}]
                  </span>
                  <span className="font-medium text-foreground">
                    {citation.title || citation.source || citation.chunk_id}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {citation.verification} · score {citation.verification_score.toFixed(2)}
                </p>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
