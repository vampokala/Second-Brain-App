import { FolderOpen, Plug, Upload } from 'lucide-react'

import { Segmented } from '../components/ui/segmented'
import { IngestTab } from '../tabs/IngestTab'
import { VaultTab } from '../tabs/VaultTab'
import { ConnectorsPanel } from './ConnectorsPanel'

export type KnowledgeView = 'browse' | 'add' | 'connectors'

type Props = {
  view: KnowledgeView
  onViewChange: (v: KnowledgeView) => void
}

/**
 * "Knowledge" merges the old Vault (browse), Ingest (add) and the new
 * Connectors panel into one place to inspect and grow the corpus.
 */
export function KnowledgeSection({ view, onViewChange }: Props) {
  const heading =
    view === 'browse' ? 'Browse vault' : view === 'add' ? 'Add documents' : 'Connectors'
  const subtitle =
    view === 'browse'
      ? 'Explore indexed files and inspect their content.'
      : view === 'add'
        ? 'Ingest files, pasted text, or a URL into the knowledge base.'
        : 'Keep knowledge fresh from GitHub, JIRA, Confluence, and Slack.'

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
            { value: 'add', label: 'Add', icon: Upload },
            { value: 'connectors', label: 'Connectors', icon: Plug },
          ]}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        {view === 'browse' ? <VaultTab /> : null}
        {view === 'add' ? <IngestTab /> : null}
        {view === 'connectors' ? <ConnectorsPanel /> : null}
      </div>
    </div>
  )
}
