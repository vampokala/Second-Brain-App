import { useEffect, useMemo, useState } from 'react'
import { fetchLlmConfig } from '../api/client'
import { chatsClient } from '../api/chatsClient'
import { vaultClient } from '../api/vaultClient'
import type { LlmConfigModel } from '../api/generated'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { Textarea } from '../components/ui/textarea'
import { useToast } from '../components/toast/ToastProvider'
import { CONNECTOR_TOKEN_SETTINGS, GOOGLE_OAUTH_SETTINGS } from '../lib/connectorTokens'
import {
  DEFAULT_CHAT_PERSONA,
  DEFAULT_STUDENT_GRADE,
  FALLBACK_GRADE_OPTIONS,
  FALLBACK_PERSONA_OPTIONS,
  normalizeChatPersona,
} from '../lib/personas'

export function SettingsTab() {
  const { toast } = useToast()
  const [data, setData] = useState<{ values: Record<string, unknown>; env_override_keys: string[] } | null>(
    null,
  )
  const [llmConfig, setLlmConfig] = useState<LlmConfigModel | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({
    openai: '',
    anthropic: '',
    gemini: '',
    gateway: '',
  })
  const [gatewayUrlDraft, setGatewayUrlDraft] = useState('')
  const [gatewayModelDraft, setGatewayModelDraft] = useState('')
  const [connectorDrafts, setConnectorDrafts] = useState<Record<string, string>>({})
  const [modelDrafts, setModelDrafts] = useState<Record<string, string>>({})
  const [showModelsByProvider, setShowModelsByProvider] = useState<Record<string, boolean>>({})
  const [personaOptions, setPersonaOptions] = useState(FALLBACK_PERSONA_OPTIONS)
  const [gradeOptions, setGradeOptions] = useState(FALLBACK_GRADE_OPTIONS)
  const [chatPersona, setChatPersona] = useState(DEFAULT_CHAT_PERSONA)
  const [studentGrade, setStudentGrade] = useState(DEFAULT_STUDENT_GRADE)
  const [personaAddon, setPersonaAddon] = useState('')
  const [rollingMemoryEnabled, setRollingMemoryEnabled] = useState(true)
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  const [visionIngestEnabled, setVisionIngestEnabled] = useState(false)
  const [braveKeyDraft, setBraveKeyDraft] = useState('')
  const [clearVault, setClearVault] = useState(false)
  const [clearMemory, setClearMemory] = useState(false)
  const [clearChats, setClearChats] = useState(false)
  const [clearConfirm, setClearConfirm] = useState('')
  const [clearBusy, setClearBusy] = useState(false)

  const canClear =
    clearConfirm === 'delete' && (clearVault || clearMemory || clearChats) && !clearBusy

  async function onClearSelected() {
    if (!canClear) return
    setClearBusy(true)
    try {
      const res = await vaultClient.clear({
        confirm: 'delete',
        clear_vault: clearVault,
        clear_memory: clearMemory,
        clear_chats: clearChats,
      })
      toast({ title: 'Cleared', description: res.detail, tone: 'success' })
      setClearConfirm('')
      setClearVault(false)
      setClearMemory(false)
      setClearChats(false)
    } catch (e) {
      toast({ title: 'Clear failed', description: (e as Error).message, tone: 'error' })
    } finally {
      setClearBusy(false)
    }
  }

  async function load() {
    try {
      const [settingsRes, configRes, personasRes] = await Promise.all([
        fetch('/settings'),
        fetchLlmConfig(),
        chatsClient.listPersonas().catch(() => null),
      ])
      if (!settingsRes.ok) throw new Error(await settingsRes.text())
      const settingsPayload = await settingsRes.json()
      setData(settingsPayload)
      setLlmConfig(configRes)
      setModelDrafts(configRes.default_model_by_provider ?? {})
      const values = settingsPayload.values as Record<string, unknown>
      const savedGatewayUrl =
        typeof values.gateway_base_url === 'string' ? values.gateway_base_url : ''
      setGatewayUrlDraft(savedGatewayUrl || configRes.gateway_base_url || '')
      const savedGatewayModel =
        configRes.default_model_by_provider?.gateway ||
        (typeof (values.default_model_by_provider as Record<string, string> | undefined)?.gateway ===
        'string'
          ? (values.default_model_by_provider as Record<string, string>).gateway
          : '')
      setGatewayModelDraft(savedGatewayModel)
      setChatPersona(normalizeChatPersona(String(values.chat_persona ?? DEFAULT_CHAT_PERSONA)))
      setStudentGrade(String(values.student_grade ?? DEFAULT_STUDENT_GRADE))
      setPersonaAddon(typeof values.persona_prompt_addon === 'string' ? values.persona_prompt_addon : '')
      setRollingMemoryEnabled(values.rolling_memory_enabled !== false)
      setWebSearchEnabled(values.web_search_enabled === true)
      setVisionIngestEnabled(values.vision_ingest_enabled === true)
      if (personasRes) {
        setPersonaOptions(personasRes.personas.length ? personasRes.personas : FALLBACK_PERSONA_OPTIONS)
        setGradeOptions(personasRes.grades.length ? personasRes.grades : FALLBACK_GRADE_OPTIONS)
      }
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
      toast({ title: 'Settings saved', tone: 'success' })
    } catch (e) {
      setError((e as Error).message)
      toast({ title: 'Save failed', description: (e as Error).message, tone: 'error' })
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

  const gatewayKeyName = 'gateway_api_key'
  const gatewayUrlLocked = (data?.env_override_keys ?? []).includes('gateway_base_url')
  const gatewayKeyLocked = (data?.env_override_keys ?? []).includes(gatewayKeyName)
  const gatewayKeyMasked =
    typeof data?.values?.[gatewayKeyName] === 'string' ? (data.values[gatewayKeyName] as string) : ''
  const gatewayHasStoredKey =
    gatewayKeyMasked.trim().length > 0 ||
    gatewayKeyLocked ||
    !!llmConfig?.provider_key_configured?.gateway
  const gatewayCanSave =
    !busy &&
    (gatewayUrlDraft.trim().length > 0 ||
      keyDrafts.gateway.trim().length > 0 ||
      gatewayModelDraft.trim().length > 0)

  async function saveGatewaySettings() {
    const model = gatewayModelDraft.trim()
    const url = gatewayUrlDraft.trim()
    const key = keyDrafts.gateway.trim()
    await savePatch({
      ...(url ? { gateway_base_url: url } : {}),
      ...(key ? { [gatewayKeyName]: { secret: key } } : {}),
      ...(model
        ? {
            default_model_by_provider: { gateway: model },
            allowed_models_by_provider: { gateway: [model] },
          }
        : {}),
    })
    setKeyDrafts((prev) => ({ ...prev, gateway: '' }))
    await load()
  }

  return (
    <div className="app-card space-y-6 p-5">
      <h2 className="text-lg font-bold">Settings</h2>
      {error ? <div className="rounded-lg bg-warning/10 p-3 text-sm">{error}</div> : null}

      <section className="space-y-2">
        <h3 className="font-semibold text-foreground">AI Gateway</h3>
        <p className="text-sm text-muted-foreground">
          Use an org LiteLLM / OpenAI-compatible gateway: base URL, API key, and default model.
          Values are stored in Postgres unless overridden by Docker/env vars.
        </p>
        <div className="space-y-3 rounded-lg border border-border p-3">
          <label className="block space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Base URL
            </span>
            <Input
              type="url"
              value={gatewayUrlDraft}
              disabled={gatewayUrlLocked || busy}
              onChange={(e) => setGatewayUrlDraft(e.target.value)}
              placeholder="http://localhost:4000/v1"
            />
            {gatewayUrlLocked ? (
              <p className="text-xs text-muted-foreground">Locked by GATEWAY_BASE_URL env.</p>
            ) : null}
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              API key
            </span>
            <Input
              type="password"
              value={keyDrafts.gateway ?? ''}
              disabled={gatewayKeyLocked || busy}
              onChange={(e) => setKeyDrafts((prev) => ({ ...prev, gateway: e.target.value }))}
              placeholder={
                gatewayHasStoredKey
                  ? 'Saved key present. Enter new key to replace.'
                  : 'Paste gateway API key'
              }
            />
            {gatewayHasStoredKey ? (
              <p className="text-xs text-muted-foreground">
                Existing key detected ({gatewayKeyMasked || 'env override'}).
              </p>
            ) : null}
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Default model
            </span>
            <Input
              type="text"
              value={gatewayModelDraft}
              disabled={busy}
              onChange={(e) => setGatewayModelDraft(e.target.value)}
              placeholder="e.g. gpt-4o-mini or org-route-name"
            />
          </label>
          <Button type="button" disabled={!gatewayCanSave} onClick={() => void saveGatewaySettings()}>
            Save AI Gateway settings
          </Button>
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="font-semibold text-foreground">Providers</h3>
        <p className="text-sm text-muted-foreground">
          Keys are stored in Postgres (masked on read) unless overridden by Docker/env vars.
        </p>
        <div className="space-y-4">
          {providers.map((provider) => {
            const keyName = `${provider}_api_key`
            const persistedMasked =
              typeof data?.values?.[keyName] === 'string' ? (data?.values?.[keyName] as string) : ''
            const serverConfigured = !!llmConfig?.provider_key_configured?.[provider]
            const hasStoredKey =
              persistedMasked.trim().length > 0 ||
              (data?.env_override_keys ?? []).includes(keyName) ||
              serverConfigured
            const hasKeyForModelSelection = hasStoredKey || keyDrafts[provider].trim().length > 0
            const modelOptions = llmConfig?.allowed_models_by_provider?.[provider] ?? []
            const selectedModel = modelDrafts[provider] ?? currentDefaults[provider] ?? modelOptions[0] ?? ''
            return (
              <div key={provider} className="rounded-lg border border-border p-3">
                <p className="mb-2 text-sm font-semibold capitalize text-foreground">{provider}</p>
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    API key
                  </label>
                  <Input
                    type="password"
                    value={keyDrafts[provider] ?? ''}
                    onChange={(e) => setKeyDrafts((prev) => ({ ...prev, [provider]: e.target.value }))}
                    placeholder={
                      hasStoredKey
                        ? 'Saved key present. Enter new key to replace.'
                        : `Paste ${provider} API key`
                    }
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
                        <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Model
                        </label>
                        <select
                          value={selectedModel}
                          onChange={(e) =>
                            setModelDrafts((prev) => ({ ...prev, [provider]: e.target.value }))
                          }
                          className="rounded-lg border border-input px-3 py-2 text-sm"
                        >
                          {modelOptions.map((model) => (
                            <option key={model} value={model}>
                              {model}
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="mt-3 text-xs text-muted-foreground">Add an API key to enable model selection.</p>
                )}
                <div className="mt-3">
                  <Button
                    type="button"
                    disabled={busy || (!keyDrafts[provider].trim() && !selectedModel)}
                    onClick={() =>
                      void savePatch({
                        ...(keyDrafts[provider].trim()
                          ? { [keyName]: { secret: keyDrafts[provider].trim() } }
                          : {}),
                        ...(selectedModel
                          ? { default_model_by_provider: { [provider]: selectedModel } }
                          : {}),
                      })
                    }
                  >
                    Save {provider} settings
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="font-semibold text-foreground">Chat persona</h3>
        <p className="text-sm text-muted-foreground">
          Persona shapes tone and expertise. Optional notes append to the system prompt for this workspace.
        </p>
        <div className="rounded-lg border border-border p-3 space-y-3">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Persona</span>
            <Select value={chatPersona} onChange={(e) => setChatPersona(e.target.value)}>
              {personaOptions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </Select>
          </label>
          {chatPersona === 'student' ? (
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Grade</span>
              <Select value={studentGrade} onChange={(e) => setStudentGrade(e.target.value)}>
                {gradeOptions.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.label}
                  </option>
                ))}
              </Select>
            </label>
          ) : null}
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Persona notes (optional)</span>
            <Textarea
              value={personaAddon}
              onChange={(e) => setPersonaAddon(e.target.value)}
              placeholder="Extra instructions appended to the persona prompt…"
              rows={3}
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={rollingMemoryEnabled}
              onChange={(e) => setRollingMemoryEnabled(e.target.checked)}
            />
            Rolling memory enabled
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={webSearchEnabled}
              onChange={(e) => setWebSearchEnabled(e.target.checked)}
            />
            Web search enabled
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={visionIngestEnabled}
              onChange={(e) => setVisionIngestEnabled(e.target.checked)}
            />
            Vision ingest enabled
          </label>
          <div className="space-y-1.5">
            <span className="text-sm font-medium">Brave Search API key</span>
            <Input
              type="password"
              value={braveKeyDraft}
              onChange={(e) => setBraveKeyDraft(e.target.value)}
              placeholder={
                typeof data?.values?.brave_search_api_key === 'string'
                  ? 'Saved key present. Enter new key to replace.'
                  : 'Paste Brave Search API key'
              }
            />
          </div>
          <Button
            type="button"
            disabled={busy}
            onClick={() =>
              void savePatch({
                chat_persona: chatPersona,
                ...(chatPersona === 'student' ? { student_grade: studentGrade } : {}),
                persona_prompt_addon: personaAddon,
                rolling_memory_enabled: rollingMemoryEnabled,
                web_search_enabled: webSearchEnabled,
                vision_ingest_enabled: visionIngestEnabled,
                ...(braveKeyDraft.trim()
                  ? { brave_search_api_key: { secret: braveKeyDraft.trim() } }
                  : {}),
              }).then(() => setBraveKeyDraft(''))
            }
          >
            Save chat settings
          </Button>
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="font-semibold text-foreground">Connector credentials</h3>
        <p className="text-sm text-muted-foreground">
          Enter tokens here or when adding a connector. Stored as app settings (masked) — not on the
          connector row. Docker <code className="rounded bg-secondary px-1">.env</code> still wins if
          set.
        </p>
        <div className="space-y-3">
          {CONNECTOR_TOKEN_SETTINGS.map((c) => {
            const masked =
              typeof data?.values?.[c.settingKey] === 'string'
                ? (data.values[c.settingKey] as string)
                : ''
            const envLocked = (data?.env_override_keys ?? []).includes(c.settingKey)
            const hasStored = masked.trim().length > 0 || envLocked
            return (
              <div key={c.settingKey} className="rounded-lg border border-border p-3">
                <p className="mb-1 text-sm font-semibold text-foreground">{c.label}</p>
                <p className="mb-2 text-xs text-muted-foreground">{c.helper}</p>
                <Input
                  type="password"
                  value={connectorDrafts[c.settingKey] ?? ''}
                  disabled={envLocked || busy}
                  onChange={(e) =>
                    setConnectorDrafts((prev) => ({ ...prev, [c.settingKey]: e.target.value }))
                  }
                  placeholder={
                    envLocked
                      ? `Locked by ${c.envName} in environment`
                      : hasStored
                        ? 'Saved token present. Enter new token to replace.'
                        : `Paste ${c.envName}`
                  }
                />
                {hasStored ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {envLocked ? `Env override (${c.envName})` : `Saved (${masked})`}
                  </p>
                ) : null}
                <Button
                  className="mt-3"
                  type="button"
                  disabled={busy || envLocked || !(connectorDrafts[c.settingKey] ?? '').trim()}
                  onClick={() => {
                    const secret = (connectorDrafts[c.settingKey] ?? '').trim()
                    void savePatch({ [c.settingKey]: { secret } }).then(() =>
                      setConnectorDrafts((prev) => ({ ...prev, [c.settingKey]: '' })),
                    )
                  }}
                >
                  Save {c.label} token
                </Button>
              </div>
            )
          })}
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="font-semibold text-foreground">Google Workspace OAuth</h3>
        <p className="text-sm text-muted-foreground">
          Used when you click Connect on Google Workspace (opens your org&apos;s Google login). Put
          the same values in <code className="rounded bg-secondary px-1">.env</code> so the
          workspace-mcp container receives them, then recreate the stack.
        </p>
        <div className="space-y-3">
          {GOOGLE_OAUTH_SETTINGS.map((c) => {
            const masked =
              typeof data?.values?.[c.settingKey] === 'string'
                ? (data.values[c.settingKey] as string)
                : ''
            const envLocked = (data?.env_override_keys ?? []).includes(c.settingKey)
            const hasStored = masked.trim().length > 0 || envLocked
            return (
              <div key={c.settingKey} className="rounded-lg border border-border p-3">
                <p className="mb-1 text-sm font-semibold text-foreground">{c.label}</p>
                <p className="mb-2 text-xs text-muted-foreground">{c.helper}</p>
                <Input
                  type="password"
                  value={connectorDrafts[c.settingKey] ?? ''}
                  disabled={envLocked || busy}
                  onChange={(e) =>
                    setConnectorDrafts((prev) => ({ ...prev, [c.settingKey]: e.target.value }))
                  }
                  placeholder={
                    envLocked
                      ? `Locked by ${c.envName} in environment`
                      : hasStored
                        ? 'Saved value present. Enter new value to replace.'
                        : `Paste ${c.envName}`
                  }
                />
                {hasStored ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {envLocked ? `Env override (${c.envName})` : `Saved (${masked})`}
                  </p>
                ) : null}
                <Button
                  className="mt-3"
                  type="button"
                  disabled={busy || envLocked || !(connectorDrafts[c.settingKey] ?? '').trim()}
                  onClick={() => {
                    const secret = (connectorDrafts[c.settingKey] ?? '').trim()
                    void savePatch({ [c.settingKey]: { secret } }).then(() =>
                      setConnectorDrafts((prev) => ({ ...prev, [c.settingKey]: '' })),
                    )
                  }}
                >
                  Save {c.label}
                </Button>
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
          <p className="mt-2 text-xs text-muted-foreground">
            Env overrides: {data.env_override_keys.join(', ')}
          </p>
        ) : null}
      </section>

      <section className="space-y-3 rounded-xl border border-destructive/40 bg-card p-5">
        <h3 className="font-semibold text-destructive">Danger zone</h3>
        <p className="text-sm text-muted-foreground">
          Permanently delete selected data. Settings, API keys, and connector configs are never
          removed. Type <code className="rounded bg-secondary px-1">delete</code> to confirm.
        </p>
        <div className="space-y-2 text-sm text-foreground">
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={clearVault}
              onChange={(e) => setClearVault(e.target.checked)}
            />
            <span>
              <span className="font-medium">Vault files &amp; search index</span>
              <span className="block text-xs text-muted-foreground">
                Deletes raw/wiki files, chunks, BM25, embed queue, ingest events, and the ingest
                manifest.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={clearMemory}
              onChange={(e) => setClearMemory(e.target.checked)}
            />
            <span>
              <span className="font-medium">Rolling memory</span>
              <span className="block text-xs text-muted-foreground">
                Removes context/memory.md.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={clearChats}
              onChange={(e) => setClearChats(e.target.checked)}
            />
            <span>
              <span className="font-medium">Chat history</span>
              <span className="block text-xs text-muted-foreground">
                Deletes all conversations and messages.
              </span>
            </span>
          </label>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="clear-confirm">
            Type delete to confirm
          </label>
          <Input
            id="clear-confirm"
            value={clearConfirm}
            onChange={(e) => setClearConfirm(e.target.value)}
            placeholder="delete"
            autoComplete="off"
          />
        </div>
        <Button
          type="button"
          variant="destructive"
          disabled={!canClear}
          onClick={() => void onClearSelected()}
        >
          {clearBusy ? 'Deleting…' : 'Delete selected'}
        </Button>
      </section>
    </div>
  )
}
