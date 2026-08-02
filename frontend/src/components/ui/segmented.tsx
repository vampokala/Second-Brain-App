import { cn } from '../../lib/utils'

export type SegmentOption<T extends string> = {
  value: T
  label: string
  icon?: React.ComponentType<{ className?: string }>
}

type Props<T extends string> = {
  value: T
  onChange: (v: T) => void
  options: SegmentOption<T>[]
  className?: string
  'aria-label'?: string
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  ...rest
}: Props<T>) {
  return (
    <div
      role="tablist"
      aria-label={rest['aria-label']}
      className={cn('inline-flex items-center gap-1 rounded-lg border bg-secondary/60 p-1', className)}
    >
      {options.map(({ value: v, label, icon: Icon }) => {
        const isActive = v === value
        return (
          <button
            key={v}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(v)}
            className={cn(
              'inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              isActive
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {Icon ? <Icon className="h-4 w-4" /> : null}
            {label}
          </button>
        )
      })}
    </div>
  )
}
