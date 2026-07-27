import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitBranch, Hash, Mail, MessageSquare, Plug, Plus, RefreshCw, Trash2, Zap } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  connectorsClient,
  type Connector,
  type ConnectorType,
} from '../api/connectorsClient'
import { mcpClient, type McpServer, type McpTool } from '../api/mcpClient'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { useToast } from '../components/toast/ToastProvider'
import { saveConnectorToken, tokenSettingForType } from '../lib/connectorTokens'
import { McpServersSection } from './McpServersSection'

type FieldDef = { key: string; label: string; placeholder?: string; type?: 'text' | 'checkbox' }

const TYPE_META: Record<
  ConnectorType,
  {
    label: string
    icon: typeof Plug
    resourceLabel: string
    tokenEnv?: string
    fields: FieldDef[]
    mcp?: boolean
    legacy?: boolean
    preset?: string
  }
> = {
  mcp_jira: {
    label: 'JIRA (MCP)',
    icon: Plug,
    resourceLabel: 'Project key',
    fields: [
      { key: 'jql', label: 'JQL (optional)', placeholder: 'project = ENG ORDER BY updated' },
      { key: 'jql_extra', label: 'Extra JQL AND clause (optional)' },
    ],
    mcp: true,
    preset: 'atlassian',
  },
  mcp_confluence: {
    label: 'Confluence (MCP)',
    icon: Plug,
    resourceLabel: 'Space key',
    fields: [],
    mcp: true,
    preset: 'atlassian',
  },
  mcp_github: {
    label: 'GitHub (MCP)',
    icon: GitBranch,
    resourceLabel: 'owner/repo',
    tokenEnv: 'GITHUB_TOKEN',
    fields: [{ key: 'include_issues', label: 'Include issues & PRs', type: 'checkbox' }],
    mcp: true,
    preset: 'github',
  },
  mcp_gmail: {
    label: 'Gmail (MCP)',
    icon: Mail,
    resourceLabel: 'Gmail query / label',
    fields: [],
    mcp: true,
    preset: 'google_workspace',
  },
  mcp_gchat: {
    label: 'Google Chat (MCP)',
    icon: MessageSquare,
    resourceLabel: 'Space ID',
    fields: [],
    mcp: true,
    preset: 'google_workspace',
  },
  mcp_custom: {
    label: 'Custom MCP tool',
    icon: Plug,
    resourceLabel: 'Resource label',
    fields: [],
    mcp: true,
    preset: 'custom',
  },
  github: {
    label: 'GitHub (legacy token)',
    icon: GitBranch,
    resourceLabel: 'owner/repo',
    tokenEnv: 'GITHUB_TOKEN',
    fields: [
      { key: 'branch', label: 'Branch (optional)', placeholder: 'main' },
      { key: 'include_issues', label: 'Include issues & PRs', type: 'checkbox' },
    ],
    legacy: true,
  },
  jira: {
    label: 'JIRA (legacy token)',
    icon: Plug,
    resourceLabel: 'Project key',
    tokenEnv: 'JIRA_API_TOKEN',
    fields: [
      { key: 'base_url', label: 'Base URL', placeholder: 'https://acme.atlassian.net' },
      { key: 'email', label: 'Account email', placeholder: 'you@acme.com' },
      { key: 'jql', label: 'JQL (optional)', placeholder: 'project = ENG ORDER BY updated' },
    ],
    legacy: true,
  },
  confluence: {
    label: 'Confluence (legacy token)',
    icon: Plug,
    resourceLabel: 'Space key',
    tokenEnv: 'CONFLUENCE_API_TOKEN',
    fields: [
      { key: 'base_url', label: 'Base URL', placeholder: 'https://acme.atlassian.net' },
      { key: 'email', label: 'Account email', placeholder: 'you@acme.com' },
    ],
    legacy: true,
  },
  slack: {
    label: 'Slack',
    icon: Hash,
    resourceLabel: 'Channel ID',
    tokenEnv: 'SLACK_BOT_TOKEN',
    fields: [
      { key: 'include_threads', label: 'Include thread replies', type: 'checkbox' },
      { key: 'workspace_url', label: 'Workspace URL (optional)', placeholder: 'https://acme.slack.com' },
    ],
  },
}

function statusVariant(status: string | null) {
  if (status === 'ok') return 'success' as const
  if (status === 'failed') return 'destructive' as const
  return 'secondary' as const
}

const INTERVAL_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: 'Manual only' },
  { value: 15, label: 'Every 15 min' },
  { value: 60, label: 'Hourly' },
  { value: 360, label: 'Every 6 hours' },
  { value: 1440, label: 'Daily' },
]

function intervalLabel(min: number | null): string {
  if (!min || min <= 0) return 'Manual'
  return INTERVAL_OPTIONS.find((o) => o.value === min)?.label ?? `Every ${min} min`
}

function availableTypes(servers: McpServer[] | undefined): ConnectorType[] {
  const connectedPresets = new Set(
    (servers ?? []).filter((s) => s.connected || s.authMode === 'token' || s.authMode === 'none').map((s) => s.preset),
  )
  const types = Object.entries(TYPE_META)
    .filter(([, meta]) => {
      if (!meta.mcp) return true
      if (!meta.preset) return true
      return connectedPresets.has(meta.preset)
    })
    .map(([k]) => k as ConnectorType)
  return types.length > 0 ? types : (['github'] as ConnectorType[])
}

function AddConnectorForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const { data: mcpServers } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: mcpClient.listServers,
  })
  const types = useMemo(() => availableTypes(mcpServers), [mcpServers])
  const [type, setType] = useState<ConnectorType>(types[0] ?? 'mcp_jira')
  const [resourceId, setResourceId] = useState('')
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [intervalMin, setIntervalMin] = useState(0)
  const [tokenDraft, setTokenDraft] = useState('')
  const [tokenStatus, setTokenStatus] = useState<{ masked?: string; envLocked?: boolean }>({})
  const [tools, setTools] = useState<McpTool[]>([])
  const meta = TYPE_META[type]
  const tokenMeta = tokenSettingForType(type)
  const showToken =
    Boolean(meta.legacy || meta.tokenEnv) && (meta.legacy || !meta.mcp || Boolean(tokenMeta))

  useEffect(() => {
    if (!types.includes(type)) setType(types[0] ?? 'github')
  }, [types, type])

  useEffect(() => {
    setTokenDraft('')
    void (async () => {
      if (!tokenMeta) return
      try {
        const res = await fetch('/settings')
        if (!res.ok) return
        const data = (await res.json()) as {
          values: Record<string, unknown>
          env_override_keys: string[]
        }
        const masked = data.values[tokenMeta.settingKey]
        setTokenStatus({
          masked: typeof masked === 'string' ? masked : undefined,
          envLocked: data.env_override_keys.includes(tokenMeta.settingKey),
        })
      } catch {
        setTokenStatus({})
      }
    })()
  }, [type, tokenMeta])

  useEffect(() => {
    if (type !== 'mcp_custom') return
    const serverId = String(config.server_id || '')
    if (!serverId) {
      setTools([])
      return
    }
    void mcpClient
      .listTools(serverId)
      .then(setTools)
      .catch(() => setTools([]))
  }, [type, config.server_id])

  const save = useMutation({
    mutationFn: async () => {
      if (tokenDraft.trim() && tokenMeta && !tokenStatus.envLocked && showToken) {
        await saveConnectorToken(tokenMeta.settingKey, tokenDraft.trim())
      }
      const nextConfig = { ...config }
      if (meta.mcp && meta.preset && !nextConfig.server_id) {
        const match = (mcpServers ?? []).find(
          (s) => s.preset === meta.preset && !s.id.startsWith('preset:'),
        )
        if (match) nextConfig.server_id = match.id
      }
      return connectorsClient.upsert({
        connector_type: type,
        resource_id: resourceId.trim(),
        config: nextConfig,
        sync_interval_min: intervalMin || null,
      })
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['connectors'] })
      toast({ title: 'Connector saved', tone: 'success' })
      onDone()
    },
    onError: (e) => {
      toast({ title: 'Save failed', description: (e as Error).message, tone: 'error' })
    },
  })

  const customServers = (mcpServers ?? []).filter(
    (s) => s.preset === 'custom' && !s.id.startsWith('preset:'),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add a connector</CardTitle>
        <CardDescription>
          Prefer MCP types (OAuth). Legacy token connectors remain available. Tokens are stored as
          app settings — never on the connector row.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1.5">
            <span className="text-sm font-medium">Type</span>
            <Select
              value={type}
              onChange={(e) => {
                setType(e.target.value as ConnectorType)
                setConfig({})
              }}
            >
              {types.map((k) => (
                <option key={k} value={k}>
                  {TYPE_META[k].label}
                </option>
              ))}
            </Select>
          </label>
          <label className="space-y-1.5">
            <span className="text-sm font-medium">{meta.resourceLabel}</span>
            <Input
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              placeholder={meta.resourceLabel}
            />
          </label>
        </div>

        {type === 'mcp_custom' ? (
          <>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">MCP server</span>
              <Select
                value={String(config.server_id || '')}
                onChange={(e) => setConfig((c) => ({ ...c, server_id: e.target.value }))}
              >
                <option value="">Select server…</option>
                {customServers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Tool</span>
              <Select
                value={String(config.tool_name || '')}
                onChange={(e) => setConfig((c) => ({ ...c, tool_name: e.target.value }))}
              >
                <option value="">Select tool…</option>
                {tools.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name}
                  </option>
                ))}
              </Select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Tool args (JSON)</span>
              <Input
                value={String(config.tool_args_text || '{}')}
                onChange={(e) => {
                  const text = e.target.value
                  let parsed: unknown = {}
                  try {
                    parsed = JSON.parse(text)
                  } catch {
                    parsed = {}
                  }
                  setConfig((c) => ({
                    ...c,
                    tool_args_text: text,
                    tool_args: parsed,
                  }))
                }}
                placeholder='{"query":"{since}"}'
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Items path (optional)</span>
              <Input
                value={String(config.items_path || '')}
                onChange={(e) => setConfig((c) => ({ ...c, items_path: e.target.value }))}
                placeholder="results"
              />
            </label>
          </>
        ) : null}

        {meta.fields.map((f) =>
          f.type === 'checkbox' ? (
            <label key={f.key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!!config[f.key]}
                onChange={(e) => setConfig((c) => ({ ...c, [f.key]: e.target.checked }))}
              />
              {f.label}
            </label>
          ) : (
            <label key={f.key} className="block space-y-1.5">
              <span className="text-sm font-medium">{f.label}</span>
              <Input
                value={(config[f.key] as string) ?? ''}
                onChange={(e) => setConfig((c) => ({ ...c, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
              />
            </label>
          ),
        )}

        {showToken && tokenMeta ? (
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">
              {tokenMeta.label} token ({tokenMeta.envName})
            </span>
            <Input
              type="password"
              value={tokenDraft}
              disabled={tokenStatus.envLocked}
              onChange={(e) => setTokenDraft(e.target.value)}
              placeholder={
                tokenStatus.envLocked
                  ? `Locked by ${tokenMeta.envName} in environment`
                  : tokenStatus.masked
                    ? 'Saved token present. Enter new token to replace.'
                    : `Paste ${tokenMeta.envName}`
              }
            />
          </label>
        ) : null}

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Sync schedule</span>
          <Select value={String(intervalMin)} onChange={(e) => setIntervalMin(Number(e.target.value))}>
            {INTERVAL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </label>

        {save.isError ? (
          <p className="text-sm text-destructive">{(save.error as Error).message}</p>
        ) : null}

        <div className="flex items-center gap-2">
          <Button onClick={() => save.mutate()} disabled={!resourceId.trim() || save.isPending}>
            <Plus className="h-4 w-4" />
            {save.isPending ? 'Saving…' : 'Save connector'}
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function ConnectorCard({
  connector,
  onAskAbout,
}: {
  connector: Connector
  onAskAbout?: (prompt: string) => void
}) {
  const qc = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncedJustNow, setSyncedJustNow] = useState(false)
  const meta = TYPE_META[connector.connector_type] ?? {
    label: connector.connector_type,
    icon: Plug,
    resourceLabel: 'Resource',
    fields: [],
  }
  const Icon = meta.icon

  const test = useMutation({
    mutationFn: () => connectorsClient.test(connector.id),
    onSuccess: (r) => setMessage(`${r.ok ? '✓' : '✗'} ${r.message}`),
    onError: (e) => setMessage((e as Error).message),
  })
  const sync = useMutation({
    mutationFn: () => connectorsClient.sync(connector.id),
    onMutate: () => {
      setSyncing(true)
      setSyncedJustNow(false)
      setMessage('Sync in progress…')
    },
    onSuccess: (r) => {
      setMessage(
        r.status === 'started' ? 'Sync started — refreshing status…' : r.detail || r.status,
      )
      const poll = window.setInterval(() => {
        void qc.invalidateQueries({ queryKey: ['connectors'] })
      }, 2000)
      window.setTimeout(() => {
        window.clearInterval(poll)
        setSyncing(false)
        setSyncedJustNow(true)
        setMessage('Sync finished — ask about the synced items below.')
        void qc.invalidateQueries({ queryKey: ['connectors'] })
      }, 8000)
    },
    onError: (e) => {
      setSyncing(false)
      setMessage((e as Error).message)
    },
  })
  const remove = useMutation({
    mutationFn: () => connectorsClient.remove(connector.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['connectors'] }),
  })

  const showAskCta = syncedJustNow || (connector.item_count > 0 && connector.last_status === 'ok')

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-secondary text-foreground">
              <Icon className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <CardTitle className="text-base">{connector.resource_id}</CardTitle>
              <CardDescription>{meta.label}</CardDescription>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge variant={syncing ? 'secondary' : statusVariant(connector.last_status)}>
              {syncing ? 'syncing…' : connector.last_status ?? 'never synced'}
            </Badge>
            <Badge variant="outline">{intervalLabel(connector.sync_interval_min)}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{connector.item_count} items</span>
          {connector.last_sync_at ? (
            <span>last sync {new Date(connector.last_sync_at).toLocaleString()}</span>
          ) : null}
          {connector.sync_interval_min && connector.next_sync_at ? (
            <span>next sync {new Date(connector.next_sync_at).toLocaleString()}</span>
          ) : null}
        </div>
        {syncing ? (
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            Pulling latest items into the knowledge base…
          </div>
        ) : null}
        {connector.last_error ? (
          <p className="text-xs text-destructive">{connector.last_error}</p>
        ) : null}
        {message ? <p className="text-xs text-muted-foreground">{message}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => test.mutate()} disabled={test.isPending}>
            <Plug className="h-4 w-4" />
            {test.isPending ? 'Testing…' : 'Test'}
          </Button>
          <Button size="sm" onClick={() => sync.mutate()} disabled={sync.isPending || syncing}>
            {sync.isPending || syncing ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
            )}
            Sync now
          </Button>
          {showAskCta && onAskAbout ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                onAskAbout(
                  `What changed in the synced ${meta.label} source "${connector.resource_id}"? Summarize key items and cite sources.`,
                )
              }
            >
              Ask about synced items
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
            className="text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-4 w-4" />
            Remove
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function ConnectorsPanel({ onAskAbout }: { onAskAbout?: (prompt: string) => void }) {
  const [adding, setAdding] = useState(false)
  const { data: connectors, isLoading, isError, error } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsClient.list,
    refetchInterval: 10_000,
  })

  return (
    <div className="space-y-4">
      <McpServersSection />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Sync connectors</CardTitle>
              <CardDescription>
                Keep the knowledge base current. Synced items become fully retrievable and citable.
              </CardDescription>
            </div>
            {!adding ? (
              <Button onClick={() => setAdding(true)}>
                <Plus className="h-4 w-4" />
                Add connector
              </Button>
            ) : null}
          </div>
        </CardHeader>
      </Card>

      {adding ? <AddConnectorForm onDone={() => setAdding(false)} /> : null}

      {isLoading ? <p className="text-sm text-muted-foreground">Loading connectors…</p> : null}
      {isError ? (
        <p className="text-sm text-destructive">{(error as Error).message}</p>
      ) : null}

      {connectors && connectors.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {connectors.map((c) => (
            <ConnectorCard key={c.id} connector={c} onAskAbout={onAskAbout} />
          ))}
        </div>
      ) : !isLoading && !adding ? (
        <Card>
          <CardContent className="py-10 text-center">
            <Plug className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium">No connectors yet</p>
            <p className="text-sm text-muted-foreground">
              Connect an MCP server above, then add a sync connector.
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
