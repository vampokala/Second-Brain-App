import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Link2, Plug, Plus } from 'lucide-react'
import { useState } from 'react'

import { mcpClient, type McpServer } from '../api/mcpClient'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { useToast } from '../components/toast/ToastProvider'

const POLL_MS = 2000
const POLL_TIMEOUT_MS = 120_000

async function pollUntilConnected(id: string): Promise<boolean> {
  const started = Date.now()
  while (Date.now() - started < POLL_TIMEOUT_MS) {
    const status = await mcpClient.serverStatus(id)
    if (status.connected) return true
    await new Promise((r) => window.setTimeout(r, POLL_MS))
  }
  return false
}

function ServerCard({
  server,
  onChanged,
}: {
  server: McpServer
  onChanged: () => void
}) {
  const { toast } = useToast()
  const [busy, setBusy] = useState(false)

  const ensureRegistered = async (): Promise<string> => {
    if (!server.id.startsWith('preset:')) return server.id
    const created = await mcpClient.upsertServer({
      preset: server.preset,
      name: server.name,
      url: server.url || undefined,
      auth_mode: server.authMode,
    })
    return created.id
  }

  const connect = useMutation({
    mutationFn: async () => {
      setBusy(true)
      const id = await ensureRegistered()
      const result = await mcpClient.connectServer(id)
      // Token / sidecar verify: no browser popup.
      if (!result.authorization_url) {
        const status = await mcpClient.serverStatus(id)
        return { connected: status.connected }
      }
      window.open(result.authorization_url, '_blank', 'popup,width=600,height=700')
      const connected = await pollUntilConnected(id)
      return { connected }
    },
    onSuccess: (r) => {
      setBusy(false)
      onChanged()
      if (r.connected) {
        toast({ title: 'MCP server connected', tone: 'success' })
      } else {
        toast({
          title: 'Connection timed out',
          description:
            'Finish signing in in the popup, then try Connect again. For GitHub you can also use “Use API token”.',
          tone: 'error',
        })
      }
    },
    onError: (e) => {
      setBusy(false)
      toast({ title: 'Connect failed', description: (e as Error).message, tone: 'error' })
    },
  })

  const connectWithToken = useMutation({
    mutationFn: async () => {
      setBusy(true)
      const tokenEnv =
        server.preset === 'github'
          ? 'GITHUB_TOKEN'
          : server.preset === 'atlassian'
            ? 'JIRA_API_TOKEN'
            : undefined
      const created = await mcpClient.upsertServer({
        preset: server.preset,
        name: server.name,
        url: server.url || undefined,
        auth_mode: 'token',
        token_env: tokenEnv,
      })
      const result = await mcpClient.connectServer(created.id)
      if (result.authorization_url) {
        throw new Error('Expected token connect without OAuth popup.')
      }
      const status = await mcpClient.serverStatus(created.id)
      return { connected: status.connected }
    },
    onSuccess: (r) => {
      setBusy(false)
      onChanged()
      if (r.connected) {
        toast({ title: 'Connected with API token', tone: 'success' })
      } else {
        toast({
          title: 'Token not found',
          description: 'Save GITHUB_TOKEN (or the Atlassian token) in Settings first.',
          tone: 'error',
        })
      }
    },
    onError: (e) => {
      setBusy(false)
      toast({ title: 'Connect failed', description: (e as Error).message, tone: 'error' })
    },
  })

  const remove = useMutation({
    mutationFn: () => mcpClient.removeServer(server.id),
    onSuccess: () => {
      onChanged()
      toast({ title: 'MCP server removed', tone: 'success' })
    },
    onError: (e) => {
      toast({ title: 'Remove failed', description: (e as Error).message, tone: 'error' })
    },
  })

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{server.name}</CardTitle>
            <CardDescription className="break-all text-xs">{server.url || 'URL required'}</CardDescription>
          </div>
          <Badge variant={server.connected ? 'success' : 'secondary'}>
            {server.connected ? 'Connected' : 'Not connected'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Enables: {server.connectorTypes.join(', ') || '—'}
          {server.preset === 'google_workspace'
            ? ' — requires workspace-mcp sidecar + Google OAuth client in .env'
            : null}
        </p>
        <div className="flex flex-wrap gap-2">
          {!server.connected ? (
            <>
              <Button size="sm" onClick={() => connect.mutate()} disabled={busy || connect.isPending}>
                <Link2 className="h-4 w-4" />
                {busy ? 'Connecting…' : 'Connect'}
              </Button>
              {server.authMode === 'oauth' &&
              (server.preset === 'github' || server.preset === 'atlassian') ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => connectWithToken.mutate()}
                >
                  Use API token
                </Button>
              ) : null}
            </>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Ready for sync
            </span>
          )}
          {!server.id.startsWith('preset:') ? (
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive"
              onClick={() => remove.mutate()}
              disabled={remove.isPending}
            >
              Disconnect
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

function AddCustomServer({ onDone }: { onDone: () => void }) {
  const { toast } = useToast()
  const [name, setName] = useState('Custom MCP')
  const [url, setUrl] = useState('')
  const [authMode, setAuthMode] = useState('oauth')
  const [tokenEnv, setTokenEnv] = useState('')

  const save = useMutation({
    mutationFn: () =>
      mcpClient.upsertServer({
        preset: 'custom',
        name: name.trim(),
        url: url.trim(),
        auth_mode: authMode,
        token_env: tokenEnv.trim() || undefined,
      }),
    onSuccess: () => {
      toast({ title: 'Custom MCP server saved', tone: 'success' })
      onDone()
    },
    onError: (e) => {
      toast({ title: 'Save failed', description: (e as Error).message, tone: 'error' })
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add custom MCP server</CardTitle>
        <CardDescription>Any streamable-HTTP MCP endpoint.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Name</span>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">URL</span>
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/mcp"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Auth mode</span>
          <Select value={authMode} onChange={(e) => setAuthMode(e.target.value)}>
            <option value="oauth">OAuth 2.1</option>
            <option value="token">API token (env)</option>
            <option value="none">None</option>
          </Select>
        </label>
        {authMode === 'token' ? (
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Token env var</span>
            <Input
              value={tokenEnv}
              onChange={(e) => setTokenEnv(e.target.value)}
              placeholder="MY_MCP_TOKEN"
            />
          </label>
        ) : null}
        <div className="flex gap-2">
          <Button onClick={() => save.mutate()} disabled={!url.trim() || save.isPending}>
            <Plus className="h-4 w-4" />
            Save
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function McpServersSection() {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: mcpClient.listServers,
    refetchInterval: 15_000,
  })

  const refresh = () => void qc.invalidateQueries({ queryKey: ['mcp-servers'] })

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>MCP servers</CardTitle>
              <CardDescription>
                Connect Atlassian, GitHub, Google Workspace, or any MCP server via OAuth — then add
                sync connectors below.
              </CardDescription>
            </div>
            {!adding ? (
              <Button variant="outline" onClick={() => setAdding(true)}>
                <Plus className="h-4 w-4" />
                Custom server
              </Button>
            ) : null}
          </div>
        </CardHeader>
      </Card>

      {adding ? (
        <AddCustomServer
          onDone={() => {
            setAdding(false)
            refresh()
          }}
        />
      ) : null}

      {isLoading ? <p className="text-sm text-muted-foreground">Loading MCP servers…</p> : null}
      {isError ? <p className="text-sm text-destructive">{(error as Error).message}</p> : null}

      {data && data.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((s) => (
            <ServerCard key={s.id} server={s} onChanged={refresh} />
          ))}
        </div>
      ) : !isLoading ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            <Plug className="mx-auto mb-2 h-6 w-6" />
            No MCP servers configured yet.
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
