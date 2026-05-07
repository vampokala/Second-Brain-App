import * as RadioGroup from '@radix-ui/react-radio-group'
import type { KnowledgeScope } from '../api/generated'
import { cn } from '../lib/utils'

const options: Array<{ value: KnowledgeScope; label: string; helper: string }> = [
  { value: 'global', label: 'Global sample corpus', helper: 'Use the preloaded public demo documents.' },
  { value: 'session', label: 'My uploads only', helper: 'Ask only against documents in this browser session.' },
  { value: 'both', label: 'Both', helper: 'Blend sample documents with your uploaded files.' },
]

export function ScopeToggle({
  value,
  onChange,
  hasUploads,
}: {
  value: KnowledgeScope
  onChange: (value: KnowledgeScope) => void
  hasUploads: boolean
}) {
  return (
    <RadioGroup.Root
      className="grid gap-3 md:grid-cols-3"
      value={value}
      onValueChange={(next) => onChange(next as KnowledgeScope)}
      aria-label="Knowledge scope"
    >
      {options.map((option) => {
        const disabled = option.value !== 'global' && !hasUploads
        return (
          <RadioGroup.Item
            key={option.value}
            value={option.value}
            disabled={disabled}
            className={cn(
              'rounded-xl border p-4 text-left transition',
              value === option.value ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white',
              disabled && 'cursor-not-allowed opacity-50',
            )}
          >
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  'h-4 w-4 rounded-full border',
                  value === option.value ? 'border-blue-600 bg-blue-600' : 'border-slate-400',
                )}
              />
              <span className="font-medium text-slate-900">{option.label}</span>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              {disabled ? 'Upload a document to enable this scope.' : option.helper}
            </p>
          </RadioGroup.Item>
        )
      })}
    </RadioGroup.Root>
  )
}
