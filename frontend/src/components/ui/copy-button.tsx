import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

import { cn } from '../../lib/utils'

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      return true
    } catch {
      return false
    }
  }
}

type Props = {
  text: string
  label: string
  className?: string
}

export function CopyButton({ text, label, className }: Props) {
  const [copied, setCopied] = useState(false)
  const disabled = !text.trim().length

  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={async () => {
        if (disabled) return
        const ok = await copyToClipboard(text)
        if (ok) {
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1600)
        }
      }}
      className={cn(
        'inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}
