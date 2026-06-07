import { BookOpen, Brain, FolderOpen, MessageSquareText, Settings } from 'lucide-react'

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
}

export function Sidebar({ active, onSelect }: Props) {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r bg-card md:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <Brain className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="leading-tight">
          <div className="text-sm font-bold tracking-tight text-foreground">Second Brain</div>
          <div className="text-xs text-muted-foreground">Knowledge assistant</div>
        </div>
      </div>
      <nav className="flex flex-col gap-1 px-3 py-2" aria-label="Primary">
        {NAV.map(({ id, label, icon: Icon, hint }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
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
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
