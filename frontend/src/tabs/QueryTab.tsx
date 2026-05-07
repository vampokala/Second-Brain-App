import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AnswerPanel } from '../components/AnswerPanel'
import { CitationsList } from '../components/CitationsList'
import { RetrievedChunks } from '../components/RetrievedChunks'
import { SamplePromptChips } from '../components/SamplePromptChips'
import { ScopeToggle } from '../components/ScopeToggle'
import { queryDocuments, fetchLlmConfig } from '../api/client'
import type { KnowledgeScope, QueryRequestModel, QueryResponseModel } from '../api/generated'
import { streamQuery } from '../lib/streamQuery'
import { useSession } from '../session/SessionContext'

const PROVIDER_KEY_PREFIX = 'doc-ingestion.provider-key.'

function buildRequest(
  query: string,
  sessionId: string | null,
  scope: KnowledgeScope,
  provider: string,
  model: string,
  providerApiKey: string,
): QueryRequestModel {
  const trimmedKey = providerApiKey.trim()
  return {
    query,
    top_k: 5,
    use_llm: true,
    use_rerank: true,
    stream: true,
    include_citations: true,
    session_id: sessionId,
    knowledge_scope: scope,
    provider,
    model,
    ...(trimmedKey ? { provider_api_key: trimmedKey } : {}),
  }
}

function pickDefaultProvider(cfg: { default_provider: string; allowed_models_by_provider: Record<string, string[]> }) {
  const keys = Object.keys(cfg.allowed_models_by_provider)
  if (keys.includes(cfg.default_provider)) {
    return cfg.default_provider
  }
  return keys[0] ?? 'ollama'
}

function pickDefaultModel(
  cfg: { default_model_by_provider: Record<string, string>; allowed_models_by_provider: Record<string, string[]> },
  provider: string,
) {
  const models = cfg.allowed_models_by_provider[provider] ?? []
  const def = cfg.default_model_by_provider[provider]
  if (def && models.includes(def)) {
    return def
  }
  return models[0] ?? ''
}

export function QueryTab() {
  const { sessionId, hasUploads, summary } = useSession()
  const [queryText, setQueryText] = useState('')
  const [scope, setScope] = useState<KnowledgeScope>('global')
  const [streamingText, setStreamingText] = useState('')
  const [response, setResponse] = useState<QueryResponseModel | null>(null)
  const [message, setMessage] = useState('')
  const answerRef = useRef('')

  const { data: llmConfig, isLoading: llmConfigLoading, isError: llmConfigError } = useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLlmConfig,
    staleTime: Infinity,
  })

  const [providerChoice, setProviderChoice] = useState<string | null>(null)
  const [modelChoice, setModelChoice] = useState<string | null>(null)

  const defaultProvider = llmConfig ? pickDefaultProvider(llmConfig) : ''
  const provider = providerChoice ?? defaultProvider
  const model =
    modelChoice !== null
      ? modelChoice
      : llmConfig && provider
        ? pickDefaultModel(llmConfig, provider)
        : ''

  const baselineApiKey = useMemo(() => {
    if (!provider || provider === 'ollama') {
      return ''
    }
    return localStorage.getItem(`${PROVIDER_KEY_PREFIX}${provider}`) ?? ''
  }, [provider])

  const [prevProvider, setPrevProvider] = useState(provider)
  const [providerApiKeyDraft, setProviderApiKeyDraft] = useState<string | null>(null)
  const [useCustomProviderKey, setUseCustomProviderKey] = useState(false)
  if (provider !== prevProvider) {
    setPrevProvider(provider)
    setProviderApiKeyDraft(null)
    setUseCustomProviderKey(false)
  }
  const providerApiKey = providerApiKeyDraft ?? baselineApiKey
  const [rememberProviderKey, setRememberProviderKey] = useState(true)

  const handleProviderChange = (next: string) => {
    setProviderChoice(next)
    if (llmConfig) {
      setModelChoice(pickDefaultModel(llmConfig, next))
    }
  }

  const fallbackMutation = useMutation({
    mutationFn: (request: QueryRequestModel) => queryDocuments({ ...request, stream: false }),
    onSuccess: (data) => {
      setResponse(data)
      setStreamingText(data.answer)
      setMessage('Streaming was unavailable, so the non-streaming response was shown.')
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : 'Query failed.')
    },
  })

  const [isStreaming, setIsStreaming] = useState(false)

  const modelOptions = llmConfig && provider ? llmConfig.allowed_models_by_provider[provider] ?? [] : []
  const serverProviderKeyConfigured = !!(llmConfig && provider && llmConfig.provider_key_configured?.[provider])
  const isDemoMode = !!llmConfig?.demo_mode
  const needsProviderKey = provider !== '' && provider !== 'ollama' && !serverProviderKeyConfigured && !isDemoMode

  const submit = async () => {
    const trimmed = queryText.trim()
    if (!trimmed) {
      setMessage('Enter a question first.')
      return
    }
    if (!provider || !model) {
      setMessage('Select a provider and model.')
      return
    }
    const effectiveProviderKey = useCustomProviderKey ? providerApiKey : ''
    if (needsProviderKey && !effectiveProviderKey.trim()) {
      setMessage(`No server key is configured for ${provider}. Paste your ${provider} API key to continue.`)
      return
    }
    if (scope !== 'global' && !hasUploads) {
      setScope('global')
      setMessage('Upload at least one document before querying My uploads.')
      return
    }

    if (rememberProviderKey && needsProviderKey && effectiveProviderKey.trim()) {
      localStorage.setItem(`${PROVIDER_KEY_PREFIX}${provider}`, providerApiKey.trim())
    }

    const request = buildRequest(trimmed, sessionId, scope, provider, model, effectiveProviderKey)
    answerRef.current = ''
    setStreamingText('')
    setResponse(null)
    setMessage('')
    setIsStreaming(true)
    try {
      await streamQuery(request, {
        onToken: (token) => {
          answerRef.current += token
          setStreamingText(answerRef.current)
        },
        onFinal: (final) => {
          setResponse({
            query: trimmed,
            provider: final.provider,
            model: final.model,
            answer: answerRef.current,
            processing_time_ms: 0,
            cached: false,
            validation_issues: [],
            citations: final.citations ?? [],
            retrieved: final.retrieved ?? [],
            truthfulness: final.truthfulness ?? null,
          })
        },
      })
    } catch {
      await fallbackMutation.mutateAsync(request)
    } finally {
      setIsStreaming(false)
    }
  }

  const answer = streamingText || response?.answer || ''
  const providerOptions = llmConfig ? Object.keys(llmConfig.allowed_models_by_provider).sort() : []
  const runDisabled =
    !provider
    || !model
    || llmConfigLoading
    || (needsProviderKey && !providerApiKey.trim())
    || isStreaming
    || fallbackMutation.isPending

  return (
    <div className="space-y-5">
      <section className="app-card space-y-5 p-5">
        <SamplePromptChips
          onSelect={(prompt) => {
            setQueryText(prompt)
            setScope('global')
          }}
        />

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">Knowledge scope</p>
          <ScopeToggle value={scope} onChange={setScope} hasUploads={hasUploads} />
        </div>

        {llmConfigError ? (
          <p className="text-sm text-red-700" role="alert">
            Could not load model options from the API. Check that the server is running and try refreshing.
          </p>
        ) : null}

        {llmConfig ? (
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">Provider</span>
              <select
                className="w-full rounded-xl border border-slate-300 bg-white p-3 text-slate-900 shadow-sm"
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
              >
                {providerOptions.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">Model</span>
              <select
                className="w-full rounded-xl border border-slate-300 bg-white p-3 text-slate-900 shadow-sm"
                value={model}
                onChange={(e) => setModelChoice(e.target.value)}
                disabled={modelOptions.length === 0}
              >
                {modelOptions.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <p className="text-sm text-slate-600">{llmConfigLoading ? 'Loading model options…' : null}</p>
        )}

        {provider !== '' && provider !== 'ollama' && !isDemoMode ? (
          <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">
                {provider}
                {' '}
                API key
              </span>
              <input
                type="password"
                autoComplete="off"
                className="w-full rounded-xl border border-slate-300 bg-white p-3 text-slate-900 shadow-sm"
                placeholder={
                  serverProviderKeyConfigured
                    ? "Optional override: paste your own key for this request"
                    : "Required: paste your key (server key not configured)"
                }
                value={providerApiKey}
                onChange={(e) => setProviderApiKeyDraft(e.target.value)}
              />
            </label>
            <p className="text-xs text-slate-600">
              {serverProviderKeyConfigured
                ? `Server key is configured for ${provider}. ${
                    isDemoMode ? 'Demo users can query without providing a key.' : 'Your key is optional.'
                  }`
                : `No server key configured for ${provider}. Provide your own key to run this provider.`}
            </p>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={rememberProviderKey}
                onChange={(e) => setRememberProviderKey(e.target.checked)}
              />
              Remember in this browser
            </label>
          </div>
        ) : null}
        {provider !== '' && provider !== 'ollama' && isDemoMode ? (
          <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs text-slate-600">
              Demo mode uses server-side provider secrets by default.
            </p>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={useCustomProviderKey}
                onChange={(e) => setUseCustomProviderKey(e.target.checked)}
              />
              Use my own API key for this provider
            </label>
            {useCustomProviderKey ? (
              <>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    {provider}
                    {' '}
                    API key
                  </span>
                  <input
                    type="password"
                    autoComplete="off"
                    className="w-full rounded-xl border border-slate-300 bg-white p-3 text-slate-900 shadow-sm"
                    placeholder="Optional override: paste your key for this request"
                    value={providerApiKey}
                    onChange={(e) => setProviderApiKeyDraft(e.target.value)}
                  />
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={rememberProviderKey}
                    onChange={(e) => setRememberProviderKey(e.target.checked)}
                  />
                  Remember in this browser
                </label>
              </>
            ) : null}
          </div>
        ) : null}

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">Question</span>
          <textarea
            className="min-h-32 w-full rounded-xl border border-slate-300 p-3 text-slate-900 shadow-sm"
            placeholder="Ask a question about the sample corpus or your uploaded documents..."
            value={queryText}
            onChange={(event) => setQueryText(event.target.value)}
          />
        </label>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            disabled={runDisabled}
            onClick={() => void submit()}
          >
            {isStreaming || fallbackMutation.isPending ? 'Running...' : 'Run'}
          </button>
          {message ? <p className="text-sm text-slate-700" aria-live="polite">{message}</p> : null}
        </div>
      </section>

      <AnswerPanel answer={answer} response={response} isLoading={isStreaming || fallbackMutation.isPending} />
      <CitationsList citations={response?.citations ?? []} sessionFiles={summary?.files ?? []} />
      <RetrievedChunks chunks={response?.retrieved ?? []} />
    </div>
  )
}
