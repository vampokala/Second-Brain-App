import { useQuery } from '@tanstack/react-query'
import { Database, FileText, Moon, Sun } from 'lucide-react'

import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { useTheme } from '../theme/ThemeProvider'
import { SECTION_TITLES, type Section } from './sections'

type VaultStats = {
  file_count: number
  chunk_count: number
  last_ingest_at: string | null
  embed_model: string | null
}

async function fetchVaultStats(): Promise<VaultStats | null> {
  try {
    const res = await fetch('/vault/stats')
    if (!res.ok) return null
    return (await res.json()) as VaultStats
  } catch {
    return null
  }
}

const SECTIONS: Section[] = ['ask', 'knowledge', 'settings', 'help']

type Props = {
  active: Section
  onSelect: (s: Section) => void
}

export function TopBar({ active, onSelect }: Props) {
  const { theme, toggleTheme } = useTheme()
  const { data: stats } = useQuery({
    queryKey: ['vault-stats'],
    queryFn: fetchVaultStats,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b bg-card/80 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-bold tracking-tight text-foreground">{SECTION_TITLES[active]}</h1>
        {/* Mobile section switch (sidebar is hidden < md) */}
        <select
          className="rounded-lg border border-input bg-card px-2 py-1 text-sm text-foreground shadow-sm md:hidden"
          value={active}
          onChange={(e) => onSelect(e.target.value as Section)}
          aria-label="Section"
        >
          {SECTIONS.map((s) => (
            <option key={s} value={s}>
              {SECTION_TITLES[s]}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2">
        {stats ? (
          <div className="hidden items-center gap-2 sm:flex">
            <Badge variant="secondary" title="Indexed files">
              <FileText className="h-3 w-3" aria-hidden="true" />
              {stats.file_count} files
            </Badge>
            <Badge variant="secondary" title="Indexed chunks">
              <Database className="h-3 w-3" aria-hidden="true" />
              {stats.chunk_count} chunks
            </Badge>
          </div>
        ) : null}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  )
}
