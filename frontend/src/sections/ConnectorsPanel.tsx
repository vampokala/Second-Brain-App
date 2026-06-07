import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitBranch, Hash, Plug, Plus, RefreshCw, Trash2, Zap } from 'lucide-react'
import { useState } from 'react'

import {
  connectorsClient,
  type Connector,
  type ConnectorType,
} from '../api/connectorsClient'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'

type FieldDef = { key: string; label: string; placeholder?: string; type?: 'text' | 'checkbox' }

const TYPE_META: Record<
  ConnectorType,
  { label: string; icon: typeof Plug; resourceLabel: string; tokenEnv: string; fields: FieldDef[] }
> = {
  github: {
    label: 'GitHub',
    icon: GitBranch,
    resourceLabel: 'owner/repo',
    tokenEnv: 'GITHUB_TOKEN',
    fields: [
      { key: 'branch', label: 'Branch (optional)', placeholder: 'main' },
      { key: 'include_issues', label: 'Include issues & PRs', type: 'checkbox' },
    ],
  },
  jira: {
    label: 'JIRA',
    icon: Plug,
    resourceLabel: 'Project key',
    tokenEnv: 'JIRA_API_TOKEN',
    fields: [
      { key: 'base_url', label: 'Base URL', placeholder: 'https://acme.atlassian.net' },
      { key: 'email', label: 'Account email', placeholder: 'you@acme.com' },
      { key: 'jql', label: 'JQL (optional)', placeholder: 'project = ENG ORDER BY updated' },
    ],
  },
  confluence: {
    label: 'Confluence',
    icon: Plug,
    resourceLabel: 'Space key',
    tokenEnv: 'CONFLUENCE_API_TOKEN',
    fields: [
      { key: 'base_url', label: 'Base URL', placeholder: 'https://acme.atlassian.net' },
      { key: 'email', label: 'Account email', placeholder: 'you@acme.com' },
    ],
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

function AddConnectorForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [type, setType] = useState<ConnectorType>('github')
  const [resourceId, setResourceId] = useState('')
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [intervalMin, setIntervalMin] = useState(0)
  const meta = TYPE_META[type]

  const save = useMutation({
    mutationFn: () =>
      connectorsClient.upsert({
        connector_type: type,
        resource_id: resourceId.trim(),
        config,
        sync_interval_min: intervalMin || null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['connectors'] })
      onDone()
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add a connector</CardTitle>
        <CardDescription>
          Configure a source. The credential is read from the <code>{meta.tokenEnv}</code> environment
          variable on the server and is never stored in the database.
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
              {Object.entries(TYPE_META).map(([k, m]) => (
                <option key={k} value={k}>
                  {m.label}
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

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Sync schedule</span>
          <Select value={String(intervalMin)} onChange={(e) => setIntervalMin(Number(e.target.value))}>
            {INTERVAL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
          <span className="text-xs text-muted-foreground">
            Auto-runs the ingestion pipeline on this cadence. You can always sync manually.
          </span>
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

function ConnectorCard({ connector }: { connector: Connector }) {
  const qc = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const meta = TYPE_META[connector.connector_type]
  const Icon = meta.icon

  const test = useMutation({
    mutationFn: () => connectorsClient.test(connector.id),
    onSuccess: (r) => setMessage(`${r.ok ? '✓' : '✗'} ${r.message}`),
    onError: (e) => setMessage((e as Error).message),
  })
  const sync = useMutation({
    mutationFn: () => connectorsClient.sync(connector.id),
    onSuccess: (r) => {
      setMessage(r.status === 'started' ? 'Sync started — watch progress in Add ▸ events.' : r.detail || r.status)
      setTimeout(() => void qc.invalidateQueries({ queryKey: ['connectors'] }), 1500)
    },
    onError: (e) => setMessage((e as Error).message),
  })
  const remove = useMutation({
    mutationFn: () => connectorsClient.remove(connector.id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['connectors'] }),
  })

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
            <Badge variant={statusVariant(connector.last_status)}>
              {connector.last_status ?? 'never synced'}
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
        {connector.last_error ? (
          <p className="text-xs text-destructive">{connector.last_error}</p>
        ) : null}
        {message ? <p className="text-xs text-muted-foreground">{message}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => test.mutate()} disabled={test.isPending}>
            <Plug className="h-4 w-4" />
            {test.isPending ? 'Testing…' : 'Test'}
          </Button>
          <Button size="sm" onClick={() => sync.mutate()} disabled={sync.isPending}>
            {sync.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            Sync now
          </Button>
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

export function ConnectorsPanel() {
  const [adding, setAdding] = useState(false)
  const { data: connectors, isLoading, isError, error } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsClient.list,
    refetchInterval: 10_000,
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Team connectors</CardTitle>
              <CardDescription>
                Keep the knowledge base current with commits, tickets, and docs. Synced items become
                fully retrievable and citable.
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
            <ConnectorCard key={c.id} connector={c} />
          ))}
        </div>
      ) : !isLoading && !adding ? (
        <Card>
          <CardContent className="py-10 text-center">
            <Plug className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium">No connectors yet</p>
            <p className="text-sm text-muted-foreground">
              Add GitHub, JIRA, Confluence, or Slack to keep knowledge fresh.
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
