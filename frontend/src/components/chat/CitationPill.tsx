import type { SessionFile } from '../../api/client'
import { citationLabel, type CitationProvenance } from '../../lib/citationProvenance'
import { Badge } from '../ui/badge'

type Props = {
  source: string
  label?: string
  score?: number
  provenance?: CitationProvenance
  sessionFiles?: SessionFile[]
  onOpenVault?: (path: string) => void
}

function resolveProvenance(
  source: string,
  label: string | undefined,
  provenance: CitationProvenance | undefined,
  sessionFiles: SessionFile[] | undefined,
): CitationProvenance | null {
  if (provenance) return provenance
  if (!sessionFiles?.length) return null
  return citationLabel({ source, title: label ?? null }, sessionFiles)
}

export function CitationPill({
  source,
  label,
  score,
  provenance,
  sessionFiles,
  onOpenVault,
}: Props) {
  const kind = source.includes('wiki/') ? 'wiki' : 'raw'
  const text = label || source.split('/').pop() || source
  const scoreText =
    typeof score === 'number' && !Number.isNaN(score) ? ` · ${score.toFixed(2)}` : ''
  const resolved = resolveProvenance(source, label, provenance, sessionFiles)

  return (
    <button
      type="button"
      className="mr-1 inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-foreground hover:bg-secondary/70"
      title={source}
      onClick={() => {
        if (onOpenVault) onOpenVault(source)
      }}
    >
      <span className="text-[10px] uppercase text-muted-foreground">[{kind}]</span>
      {resolved ? (
        <Badge variant={resolved === 'yours' ? 'accent' : 'outline'} className="px-1.5 py-0 text-[10px]">
          {resolved}
        </Badge>
      ) : null}
      <span className="max-w-[12rem] truncate">
        {text}
        {scoreText}
      </span>
    </button>
  )
}
