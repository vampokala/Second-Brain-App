type Props = {
  source: string
  label?: string
  onOpenVault?: (path: string) => void
}

export function CitationPill({ source, label, onOpenVault }: Props) {
  const kind = source.includes('wiki/') ? 'wiki' : 'raw'
  const text = label || source.split('/').pop() || source
  return (
    <button
      type="button"
      className="mr-1 inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-foreground hover:bg-secondary/70"
      onClick={() => {
        if (onOpenVault) onOpenVault(source)
      }}
    >
      <span className="text-[10px] uppercase text-muted-foreground">[{kind}]</span>
      <span className="max-w-[12rem] truncate">{text}</span>
    </button>
  )
}
