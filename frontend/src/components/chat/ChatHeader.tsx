type Props = {
  provider: string
  model: string
  scope: string
  allowedModelsByProvider?: Record<string, string[]>
  defaultModelByProvider?: Record<string, string>
  providerKeyConfigured?: Record<string, boolean>
  onProviderModelChange?: (p: string, m: string) => void
  onScopeToggle?: (s: string) => void
}

const PROVIDER_OPTIONS = ['ollama', 'openai', 'anthropic', 'gemini']

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
  allowedModelsByProvider,
  defaultModelByProvider,
  providerKeyConfigured,
  onProviderModelChange,
  onScopeToggle,
}: Props) {
  const models = allowedModelsByProvider?.[provider] ?? []
  const showModelSelect = models.length > 0
  const knownModel = showModelSelect ? models.includes(model) : true

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border pb-3">
      <label className="text-xs text-muted-foreground">
        Provider
        <select
          className="ml-1 rounded-lg border border-border px-2 py-1 text-sm"
          value={provider}
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
          {PROVIDER_OPTIONS.map((p) => {
            const configured = providerKeyConfigured?.[p]
            const label = configured === false ? `${p} (no key)` : p
            return (
              <option key={p} value={p}>
                {label}
              </option>
            )
          })}
        </select>
      </label>
      <label className="text-xs text-muted-foreground">
        Model
        {showModelSelect ? (
          <select
            className="ml-1 w-48 rounded-lg border border-border px-2 py-1 text-sm"
            value={model}
            onChange={(e) => onProviderModelChange?.(provider, e.target.value)}
          >
            {!knownModel && model ? (
              <option key="__custom__" value={model}>
                {model} (custom)
              </option>
            ) : null}
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="ml-1 w-40 rounded-lg border border-border px-2 py-1 text-sm"
            value={model}
            onChange={(e) => onProviderModelChange?.(provider, e.target.value)}
          />
        )}
      </label>
      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        Scope
        <select
          className="rounded-lg border border-border px-2 py-1 text-sm"
          value={scope}
          onChange={(e) => onScopeToggle?.(e.target.value)}
        >
          <option value="vault">vault</option>
          <option value="global">global</option>
        </select>
      </label>
    </div>
  )
}
