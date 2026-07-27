import { BookOpen, Brain, FolderOpen, MessageSquareText, PanelLeftClose, Settings } from 'lucide-react'

import { cn } from '../../lib/utils'
import type { Section } from './sections'

const NAV: { id: Section; label: string; icon: typeof MessageSquareText; hint: string }[] = [
  { id: 'ask', label: 'Ask', icon: MessageSquareText, hint: 'Chat & quick answers' },
  { id: 'knowledge', label: 'Knowledge', icon: FolderOpen, hint: 'Browse & add sources' },
  { id: 'settings', label: 'Settings', icon: Settings, hint: 'Providers & keys' },
  { id: 'help', label: 'Help', icon: BookOpen, hint: 'How it works' },
]

type Props = {
  active: Section
  onSelect: (s: Section) => void
  collapsed?: boolean
  onToggleCollapsed?: () => void
}

export function Sidebar({ active, onSelect, collapsed = false, onToggleCollapsed }: Props) {
  return (
    <aside
      className={cn(
        'hidden shrink-0 flex-col border-r bg-card transition-all duration-200 md:flex',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      <div className={cn('flex items-center gap-2.5 px-5 py-5', collapsed && 'flex-col')}>
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <Brain className="h-5 w-5" aria-hidden="true" />
        </span>
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-sm font-bold tracking-tight text-foreground">Second Brain</div>
            <div className="text-xs text-muted-foreground">Knowledge assistant</div>
          </div>
        )}
      </div>
      <nav className={cn('flex flex-col gap-1 px-3 py-2', collapsed && 'items-center')} aria-label="Primary">
        {NAV.map(({ id, label, icon: Icon, hint }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              title={label}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors',
                collapsed && 'justify-center px-2',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {!collapsed && (
                <span className="flex flex-col">
                  <span>{label}</span>
                  <span
                    className={cn(
                      'text-xs font-normal',
                      isActive ? 'text-primary/70' : 'text-muted-foreground/70',
                    )}
                  >
                    {hint}
                  </span>
                </span>
              )}
            </button>
          )
        })}
      </nav>
      <div className={cn('mt-auto flex px-3 py-2', collapsed && 'justify-center')}>
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
        >
          <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </aside>
  )
}
