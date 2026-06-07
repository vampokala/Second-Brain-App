import type { AskView } from '../components/layout/sections'
import { ChatTab } from '../tabs/ChatTab'
import { QueryTab } from '../tabs/QueryTab'

type Props = {
  view: AskView
  onNavigateVault?: () => void
}

/**
 * "Ask" merges the old Chat and Query tabs. The Chat / Quick ask toggle lives in
 * the top bar (see TopBar) so the chat pane can use the full viewport height.
 * Chat is the primary full-height surface; Quick ask is a scrollable single-shot
 * form (former Query tab).
 */
export function AskSection({ view, onNavigateVault }: Props) {
  if (view === 'chat') {
    return <ChatTab onNavigateVault={onNavigateVault} />
  }
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl">
        <QueryTab />
      </div>
    </div>
  )
}
