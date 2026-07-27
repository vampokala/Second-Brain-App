import { BookmarkPlus, BrainCircuit, Send } from 'lucide-react'
import { useState } from 'react'

import type { GroundingMode } from '../../api/chatsClient'
import type { ChatMetaEvent } from '../../lib/streamChat'
import { Button } from '../ui/button'

export type SendOptions = {
  groundingMode: GroundingMode
  includeWebSearch: boolean
}

type Props = {
  onSend: (text: string, opts?: SendOptions) => void
  personaLabel?: string
  onOpenPersonaSettings?: () => void
  groundingMode?: GroundingMode
  onGroundingModeChange?: (mode: GroundingMode) => void
  includeWebSearch?: boolean
  onIncludeWebSearchChange?: (enabled: boolean) => void
  webSearchAvailable?: boolean
  onSaveToWiki?: () => void
  onUpdateMemory?: () => void
  disabled?: boolean
  lastMeta?: ChatMetaEvent | null
}

export function Composer({
  onSend,
  personaLabel,
  onOpenPersonaSettings,
  groundingMode = 'corpus_only',
  onGroundingModeChange,
  includeWebSearch = false,
  onIncludeWebSearchChange,
  webSearchAvailable = false,
  onSaveToWiki,
  onUpdateMemory,
  disabled,
  lastMeta,
}: Props) {
  const [text, setText] = useState('')
  const corpusOnly = groundingMode === 'corpus_only'

  function submit() {
    const t = text.trim()
    if (!t || disabled) return
    onSend(t, { groundingMode, includeWebSearch })
    setText('')
  }

  return (
    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
      <textarea
        className="w-full resize-none rounded-lg border border-border bg-background p-3 text-sm outline-none focus:border-primary"
        rows={3}
        maxLength={32000}
        placeholder="Message… (Enter to send, Shift+Enter for newline)"
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== 'Enter' || e.shiftKey) return
          e.preventDefault()
          submit()
        }}
      />

      <div className="mt-2 space-y-2 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <label className="flex cursor-pointer items-center gap-2 text-foreground">
            <input
              id="composer-corpus-only"
              type="checkbox"
              className="rounded border-border"
              checked={corpusOnly}
              disabled={disabled}
              onChange={(e) =>
                onGroundingModeChange?.(e.target.checked ? 'corpus_only' : 'allow_general')
              }
            />
            Corpus only
          </label>
          <label
            className="flex cursor-pointer items-center gap-2 text-foreground"
            title={
              !webSearchAvailable ? 'Add a Brave Search API key in Settings to enable web search.' : undefined
            }
          >
            <input
              id="composer-web-search"
              type="checkbox"
              className="rounded border-border"
              checked={includeWebSearch}
              disabled={disabled || !webSearchAvailable}
              onChange={(e) => onIncludeWebSearchChange?.(e.target.checked)}
            />
            Web search
          </label>
          {personaLabel ? (
            onOpenPersonaSettings ? (
              <button
                type="button"
                className="ml-auto shrink-0 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-foreground hover:bg-secondary/80"
                onClick={onOpenPersonaSettings}
                title="Change persona in Settings"
              >
                {personaLabel}
              </button>
            ) : (
              <span className="ml-auto shrink-0 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-foreground">
                {personaLabel}
              </span>
            )
          ) : null}
        </div>

        {!corpusOnly && !includeWebSearch ? (
          <p>Answers may use general knowledge — not limited to your corpus or the web.</p>
        ) : null}

        {lastMeta && !disabled ? (
          <p className="text-[10px] uppercase tracking-wide">
            Last send: corpus {lastMeta.grounding_mode === 'corpus_only' ? 'on' : 'off'}
            {' · '}
            web {lastMeta.include_web_search ? 'on' : 'off'}
            {lastMeta.grounding_mode === 'corpus_only' ? (
              <>
                {' · '}
                {lastMeta.hit_count} hits
                {typeof lastMeta.max_score === 'number'
                  ? ` (max ${lastMeta.max_score.toFixed(2)})`
                  : ''}
              </>
            ) : (
              ' · corpus retrieval skipped'
            )}
            {lastMeta.include_web_search && typeof lastMeta.web_pages_fetched === 'number' ? (
              <> · {lastMeta.web_pages_fetched} web page(s)</>
            ) : null}
            {lastMeta.persona_display ? <> · persona {lastMeta.persona_display}</> : null}
            {lastMeta.persona_addon_applied ? ' · custom notes on' : ''}
          </p>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1">
          {onSaveToWiki ? (
            <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={onSaveToWiki}>
              <BookmarkPlus className="h-3.5 w-3.5" />
              Save to wiki
            </Button>
          ) : null}
          {onUpdateMemory ? (
            <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={onUpdateMemory}>
              <BrainCircuit className="h-3.5 w-3.5" />
              Update memory
            </Button>
          ) : null}
        </div>
        <Button type="button" disabled={disabled || !text.trim()} onClick={submit}>
          <Send className="h-3.5 w-3.5" />
          Send
        </Button>
      </div>
    </div>
  )
}
