import { useState } from 'react'

type Props = {
  onSend: (text: string) => void
  disabled?: boolean
}

export function Composer({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const est = Math.max(1, Math.ceil(text.length / 4))

  function submit() {
    const t = text.trim()
    if (!t || disabled) return
    onSend(t)
    setText('')
  }

  return (
    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
      <textarea
        className="w-full resize-none rounded-lg border border-border p-3 text-sm outline-none focus:border-primary"
        rows={3}
        maxLength={32000}
        placeholder="Message… (⌘/Ctrl+Enter)"
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            submit()
          }
        }}
      />
      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>~{est} tokens (est.)</span>
        <button
          type="button"
          disabled={disabled}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          onClick={submit}
        >
          Send
        </button>
      </div>
    </div>
  )
}
