import type { SessionFile } from '../api/client'
import type { CitationModel } from '../api/generated'

export type CitationProvenance = 'global' | 'yours'

export function citationLabel(
  citation: Pick<CitationModel, 'source' | 'title'>,
  sessionFiles: SessionFile[],
): CitationProvenance {
  const searchable = `${citation.source ?? ''} ${citation.title ?? ''}`.toLowerCase()
  return sessionFiles.some((file) => searchable.includes(file.name.toLowerCase())) ? 'yours' : 'global'
}
