import { FolderOpen, Plug, RefreshCw, Upload } from 'lucide-react'

import { Segmented } from '../components/ui/segmented'
import { IngestScanTab } from '../tabs/IngestScanTab'
import { IngestTab } from '../tabs/IngestTab'
import { VaultTab } from '../tabs/VaultTab'
import { ConnectorsPanel } from './ConnectorsPanel'

export type KnowledgeView = 'browse' | 'ingest' | 'add' | 'connectors'

type Props = {
  view: KnowledgeView
  onViewChange: (v: KnowledgeView) => void
  onAskAbout?: (prompt: string) => void
}

function knowledgeCopy(view: KnowledgeView): { heading: string; subtitle: string } {
  if (view === 'browse') {
    return {
      heading: 'Browse vault',
      subtitle: 'Explore indexed files and ask about what you find.',
    }
  }
  if (view === 'ingest') {
    return {
      heading: 'Ingest vault',
      subtitle: 'Scan the vault folder for new or changed files, including drops from shared mounts.',
    }
  }
  if (view === 'add') {
    return {
      heading: 'Add documents',
      subtitle: 'Ingest files, pasted text, or a URL into the knowledge base.',
    }
  }
  return {
    heading: 'Connectors',
    subtitle: 'Keep knowledge fresh from GitHub, JIRA, Confluence, and Slack.',
  }
}

/**
 * "Knowledge" merges vault browse, vault scan ingest, Add, and Connectors.
 */
export function KnowledgeSection({ view, onViewChange, onAskAbout }: Props) {
  const { heading, subtitle } = knowledgeCopy(view)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">{heading}</h2>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <Segmented<KnowledgeView>
          aria-label="Knowledge view"
          value={view}
          onChange={onViewChange}
          options={[
            { value: 'browse', label: 'Browse', icon: FolderOpen },
            { value: 'ingest', label: 'Ingest', icon: RefreshCw },
            { value: 'add', label: 'Add', icon: Upload },
            { value: 'connectors', label: 'Connectors', icon: Plug },
          ]}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        {view === 'browse' ? <VaultTab onAskAbout={onAskAbout} /> : null}
        {view === 'ingest' ? <IngestScanTab /> : null}
        {view === 'add' ? <IngestTab /> : null}
        {view === 'connectors' ? <ConnectorsPanel onAskAbout={onAskAbout} /> : null}
      </div>
    </div>
  )
}
