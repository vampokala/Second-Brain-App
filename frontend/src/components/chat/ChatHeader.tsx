import { cn } from '../../lib/utils'

type Props = {
  provider: string
  model: string
  scope: string
  title?: string | null
  allowedModelsByProvider?: Record<string, string[]>
  defaultModelByProvider?: Record<string, string>
  providerKeyConfigured?: Record<string, boolean>
  onProviderModelChange?: (p: string, m: string) => void
  onScopeToggle?: (s: string) => void
}

const PROVIDER_OPTIONS = ['ollama', 'openai', 'anthropic', 'gemini']

const SCOPE_PILLS: Array<{ value: string; label: string; helper: string }> = [
  { value: 'vault', label: 'Vault', helper: 'Search your indexed vault' },
  { value: 'global', label: 'Global', helper: 'Search the shared demo corpus' },
]

function pickModelForProvider(
  provider: string,
  defaults?: Record<string, string>,
  allowed?: Record<string, string[]>,
  fallback = '',
): string {
  const list = allowed?.[provider] ?? []
  const def = defaults?.[provider]
  if (def && list.includes(def)) return def
  return list[0] ?? fallback
}

export function ChatHeader({
  provider,
  model,
  scope,
  title,
  allowedModelsByProvider,
  defaultModelByProvider,
  providerKeyConfigured,
  onProviderModelChange,
  onScopeToggle,
}: Props) {
  const models = allowedModelsByProvider?.[provider] ?? []
  const showModelSelect = models.length > 0
  const knownModel = showModelSelect ? models.includes(model) : true
  const modelOptions = showModelSelect
    ? models.flatMap((m) => [`${provider}::${m}`])
    : []

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-foreground">{title?.trim() || 'New chat'}</p>
      </div>

      <div
        className="inline-flex rounded-lg border border-border bg-card p-0.5"
        role="group"
        aria-label="Knowledge scope"
      >
        {SCOPE_PILLS.map((pill) => (
          <button
            key={pill.value}
            type="button"
            title={pill.helper}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition',
              scope === pill.value
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
            onClick={() => onScopeToggle?.(pill.value)}
          >
            {pill.label}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="sr-only">Model</span>
        {showModelSelect ? (
          <select
            className="max-w-[14rem] rounded-lg border border-border bg-card px-2 py-1.5 text-sm text-foreground"
            value={`${provider}::${model}`}
            aria-label="Model"
            onChange={(e) => {
              const [nextProvider, nextModel] = e.target.value.split('::')
              if (!nextProvider || !nextModel) return
              onProviderModelChange?.(nextProvider, nextModel)
            }}
          >
            {!knownModel && model ? (
              <option value={`${provider}::${model}`}>
                {provider}/{model} (custom)
              </option>
            ) : null}
            {PROVIDER_OPTIONS.flatMap((p) => {
              const list = allowedModelsByProvider?.[p] ?? []
              const configured = providerKeyConfigured?.[p]
              return list.map((m) => (
                <option key={`${p}::${m}`} value={`${p}::${m}`}>
                  {configured === false ? `${p}/${m} (no key)` : `${p}/${m}`}
                </option>
              ))
            })}
            {modelOptions.length === 0 ? (
              <option value={`${provider}::${model}`}>{provider}/{model || '—'}</option>
            ) : null}
          </select>
        ) : (
          <div className="flex items-center gap-1">
            <select
              className="rounded-lg border border-border bg-card px-2 py-1.5 text-sm"
              value={provider}
              aria-label="Provider"
              onChange={(e) => {
                const nextProvider = e.target.value
                const nextModel = pickModelForProvider(
                  nextProvider,
                  defaultModelByProvider,
                  allowedModelsByProvider,
                  model,
                )
                onProviderModelChange?.(nextProvider, nextModel)
              }}
            >
              {PROVIDER_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {providerKeyConfigured?.[p] === false ? `${p} (no key)` : p}
                </option>
              ))}
            </select>
            <input
              className="w-36 rounded-lg border border-border bg-card px-2 py-1.5 text-sm"
              value={model}
              aria-label="Model name"
              onChange={(e) => onProviderModelChange?.(provider, e.target.value)}
            />
          </div>
        )}
      </label>
    </div>
  )
}
