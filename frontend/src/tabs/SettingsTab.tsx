import { useEffect, useMemo, useState } from 'react'
import { fetchLlmConfig } from '../api/client'
import type { LlmConfigModel } from '../api/generated'

export function SettingsTab() {
  const [data, setData] = useState<{ values: Record<string, unknown>; env_override_keys: string[] } | null>(null)
  const [llmConfig, setLlmConfig] = useState<LlmConfigModel | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({
    openai: '',
    anthropic: '',
    gemini: '',
  })
  const [modelDrafts, setModelDrafts] = useState<Record<string, string>>({})
  const [showModelsByProvider, setShowModelsByProvider] = useState<Record<string, boolean>>({})

  async function load() {
    try {
      const [settingsRes, configRes] = await Promise.all([fetch('/settings'), fetchLlmConfig()])
      if (!settingsRes.ok) throw new Error(await settingsRes.text())
      setData(await settingsRes.json())
      setLlmConfig(configRes)
      setModelDrafts(configRes.default_model_by_provider ?? {})
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function savePatch(patch: Record<string, unknown>) {
    setBusy(true)
    try {
      const res = await fetch('/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patch }),
      })
      if (!res.ok) throw new Error(await res.text())
      setData(await res.json())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const providers = ['openai', 'anthropic', 'gemini']
  const currentDefaults = useMemo(() => {
    const fromSettings = data?.values?.default_model_by_provider
    if (fromSettings && typeof fromSettings === 'object' && !Array.isArray(fromSettings)) {
      return fromSettings as Record<string, string>
    }
    return llmConfig?.default_model_by_provider ?? {}
  }, [data?.values, llmConfig])

  return (
    <div className="app-card space-y-6 p-5">
      <h2 className="text-lg font-bold">Settings</h2>
      {error ? <div className="rounded-lg bg-warning/10 p-3 text-sm">{error}</div> : null}
      <section className="space-y-2">
        <h3 className="font-semibold text-foreground">Providers</h3>
        <p className="text-sm text-muted-foreground">Keys are stored in Postgres unless overridden by env vars.</p>
        <div className="space-y-4">
          {providers.map((provider) => {
            const keyName = `${provider}_api_key`
            const persistedMasked = typeof data?.values?.[keyName] === 'string' ? (data?.values?.[keyName] as string) : ''
            const serverConfigured = !!llmConfig?.provider_key_configured?.[provider]
            const hasStoredKey =
              persistedMasked.trim().length > 0
              || (data?.env_override_keys ?? []).includes(keyName)
              || serverConfigured
            const hasKeyForModelSelection = hasStoredKey || keyDrafts[provider].trim().length > 0
            const modelOptions = llmConfig?.allowed_models_by_provider?.[provider] ?? []
            const selectedModel = modelDrafts[provider] ?? currentDefaults[provider] ?? modelOptions[0] ?? ''
            return (
              <div key={provider} className="rounded-lg border border-border p-3">
                <p className="mb-2 text-sm font-semibold capitalize text-foreground">{provider}</p>
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">API key</label>
                  <input
                    type="password"
                    value={keyDrafts[provider] ?? ''}
                    onChange={(e) => setKeyDrafts((prev) => ({ ...prev, [provider]: e.target.value }))}
                    className="rounded-lg border border-input px-3 py-2 text-sm"
                    placeholder={hasStoredKey ? 'Saved key present. Enter new key to replace.' : `Paste ${provider} API key`}
                  />
                  {hasStoredKey ? (
                    <p className="text-xs text-muted-foreground">
                      Existing key detected ({persistedMasked || 'env override'}).
                    </p>
                  ) : null}
                </div>
                {hasKeyForModelSelection ? (
                  <>
                    <div className="mt-3">
                      <button
                        type="button"
                        className="rounded-lg border border-input px-3 py-2 text-sm"
                        onClick={() =>
                          setShowModelsByProvider((prev) => ({
                            ...prev,
                            [provider]: !prev[provider],
                          }))
                        }
                        disabled={busy}
                      >
                        {showModelsByProvider[provider] ? 'Hide Models' : 'List Models'}
                      </button>
                    </div>
                    {showModelsByProvider[provider] ? (
                      <div className="mt-3 flex flex-col gap-2">
                        <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Model</label>
                        <select
                          value={selectedModel}
                          onChange={(e) => setModelDrafts((prev) => ({ ...prev, [provider]: e.target.value }))}
                          className="rounded-lg border border-input px-3 py-2 text-sm"
                        >
                          {modelOptions.map((model) => (
                            <option key={model} value={model}>
                              {model}
                            </option>
                          ))}
                        </select>
                        {!modelOptions.length ? (
                          <p className="text-xs text-muted-foreground">No models available from server config for this provider.</p>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="mt-3 text-xs text-muted-foreground">Add an API key to enable model selection.</p>
                )}
                <div className="mt-3">
                  <button
                    type="button"
                    className="rounded-lg bg-primary px-3 py-2 text-sm text-white disabled:opacity-60"
                    disabled={busy || (!keyDrafts[provider].trim() && !selectedModel)}
                    onClick={() =>
                      void savePatch({
                        ...(keyDrafts[provider].trim() ? { [keyName]: { secret: keyDrafts[provider].trim() } } : {}),
                        ...(selectedModel
                          ? {
                              default_model_by_provider: {
                                [provider]: selectedModel,
                              },
                            }
                          : {}),
                      })
                    }
                  >
                    Save {provider} settings
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-foreground">Current values (masked)</h3>
        <pre className="max-h-64 overflow-auto rounded-lg bg-secondary p-3 text-xs text-foreground">
          {data ? JSON.stringify(data.values, null, 2) : 'Loading…'}
        </pre>
        {data?.env_override_keys?.length ? (
          <p className="mt-2 text-xs text-muted-foreground">Env overrides: {data.env_override_keys.join(', ')}</p>
        ) : null}
      </section>
    </div>
  )
}
