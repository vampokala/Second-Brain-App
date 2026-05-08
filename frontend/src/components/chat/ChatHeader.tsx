type Props = {
  provider: string
  model: string
  scope: string
  onProviderModelChange?: (p: string, m: string) => void
  onScopeToggle?: (s: string) => void
}

export function ChatHeader({ provider, model, scope, onProviderModelChange, onScopeToggle }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 pb-3">
      <label className="text-xs text-slate-600">
        Provider
        <select
          className="ml-1 rounded-lg border border-slate-200 px-2 py-1 text-sm"
          value={provider}
          onChange={(e) => onProviderModelChange?.(e.target.value, model)}
        >
          <option value="ollama">ollama</option>
          <option value="openai">openai</option>
          <option value="anthropic">anthropic</option>
        </select>
      </label>
      <label className="text-xs text-slate-600">
        Model
        <input
          className="ml-1 w-40 rounded-lg border border-slate-200 px-2 py-1 text-sm"
          value={model}
          onChange={(e) => onProviderModelChange?.(provider, e.target.value)}
        />
      </label>
      <label className="flex items-center gap-2 text-xs text-slate-600">
        Scope
        <select
          className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
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
