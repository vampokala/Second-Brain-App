import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Link2, Plug, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { mcpClient, type McpServer } from '../api/mcpClient'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { useToast } from '../components/toast/ToastProvider'
import { saveConnectorToken } from '../lib/connectorTokens'

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

async function openAuthWindow(url: string): Promise<Window | null> {
  // Avoid the "popup" feature string — browsers often block it. Prefer a tab.
  const win = window.open(url, '_blank', 'noopener,noreferrer')
  if (win) {
    try {
      win.focus()
    } catch {
      // ignore
    }
    return win
  }
  return null
}

function ServerCard({
  server,
  onChanged,
}: {
  server: McpServer
  onChanged: () => void
}) {
  const { toast } = useToast()
  const isGithubPreset = server.preset === 'github' || server.preset === 'github_enterprise'
  const [busy, setBusy] = useState(false)
  const [authLink, setAuthLink] = useState<string | null>(null)
  const [atlassianEmail, setAtlassianEmail] = useState(server.authEmail ?? '')
  const [enterpriseMcpUrl, setEnterpriseMcpUrl] = useState(server.url || '')
  const [tokenDraft, setTokenDraft] = useState('')
  const [tokenHint, setTokenHint] = useState<{ masked?: string; envLocked?: boolean }>({})

  useEffect(() => {
    if (server.connected || (!isGithubPreset && server.preset !== 'atlassian')) return
    const settingKey = isGithubPreset ? 'github_token' : 'jira_api_token'
    void (async () => {
      try {
        const res = await fetch('/settings')
        if (!res.ok) return
        const data = (await res.json()) as {
          values: Record<string, unknown>
          env_override_keys: string[]
        }
        const masked = data.values[settingKey]
        setTokenHint({
          masked: typeof masked === 'string' ? masked : undefined,
          envLocked: data.env_override_keys.includes(settingKey),
        })
      } catch {
        setTokenHint({})
      }
    })()
  }, [server.connected, server.preset, isGithubPreset])

  const ensureRegistered = async (opts?: {
    auth_mode?: string
    token_env?: string
    auth_email?: string
    url?: string
  }): Promise<string> => {
    const url =
      opts?.url ||
      (server.preset === 'github_enterprise' ? enterpriseMcpUrl.trim() : undefined) ||
      server.url ||
      undefined
    if (server.preset === 'github_enterprise' && !url) {
      throw new Error(
        'Set the self-hosted github-mcp-server URL (or GITHUB_MCP_URL in .env).',
      )
    }
    const created = await mcpClient.upsertServer({
      preset: server.preset,
      name: server.name,
      url,
      auth_mode: opts?.auth_mode || server.authMode,
      token_env: opts?.token_env,
      auth_email: opts?.auth_email,
    })
    return created.id
  }

  const persistTokenIfNeeded = async (): Promise<void> => {
    const draft = tokenDraft.trim()
    const settingKey = isGithubPreset ? 'github_token' : 'jira_api_token'
    const envName = isGithubPreset ? 'GITHUB_TOKEN' : 'JIRA_API_TOKEN'
    if (draft) {
      if (tokenHint.envLocked) {
        throw new Error(
          `${envName} is set in the container environment and cannot be overwritten from the UI. ` +
            `Update .env and recreate the API container, or unset ${envName}.`,
        )
      }
      await saveConnectorToken(settingKey, draft)
      setTokenDraft('')
      setTokenHint((prev) => ({ ...prev, masked: '****saved' }))
      return
    }
    if (tokenHint.masked || tokenHint.envLocked) {
      return
    }
    throw new Error(
      `Paste your ${envName} below (saved like model provider keys), then connect.`,
    )
  }

  const connect = useMutation({
    mutationFn: async () => {
      setBusy(true)
      setAuthLink(null)
      const id = await ensureRegistered()
      const result = await mcpClient.connectServer(id)
      // Token / sidecar verify: no browser popup.
      if (!result.authorization_url) {
        const status = await mcpClient.serverStatus(id)
        return { connected: status.connected }
      }
      const win = await openAuthWindow(result.authorization_url)
      if (!win) {
        setAuthLink(result.authorization_url)
      }
      const connected = await pollUntilConnected(id)
      return { connected }
    },
    onSuccess: (r) => {
      setBusy(false)
      onChanged()
      if (r.connected) {
        setAuthLink(null)
        toast({ title: 'MCP server connected', tone: 'success' })
      } else {
        toast({
          title: 'Connection timed out',
          description:
            'Finish signing in in the browser tab, then try again. For GitHub, prefer “Use API token”.',
          tone: 'error',
        })
      }
    },
    onError: (e) => {
      setBusy(false)
      const msg = (e as Error).message
      const githubHint =
        isGithubPreset && /GITHUB_OAUTH|OAuth App|Dynamic Client/i.test(msg)
          ? ' Prefer “Use API token” with GITHUB_TOKEN in Settings. For GHES, set GITHUB_HOST and register the OAuth App on that host.'
          : ''
      toast({ title: 'Connect failed', description: `${msg}${githubHint}`, tone: 'error' })
    },
  })

  const connectWithToken = useMutation({
    mutationFn: async () => {
      setBusy(true)
      await persistTokenIfNeeded()
      const tokenEnv = isGithubPreset
        ? 'GITHUB_TOKEN'
        : server.preset === 'atlassian'
          ? 'JIRA_API_TOKEN'
          : undefined
      const email = atlassianEmail.trim()
      if (server.preset === 'atlassian' && !email) {
        throw new Error(
          'Enter your Atlassian account email for personal API token auth (Basic email:token).',
        )
      }
      const createdId = await ensureRegistered({
        auth_mode: 'token',
        token_env: tokenEnv,
        auth_email: server.preset === 'atlassian' ? email : undefined,
        url: server.preset === 'github_enterprise' ? enterpriseMcpUrl.trim() : undefined,
      })
      const result = await mcpClient.connectServer(createdId)
      if (result.authorization_url) {
        throw new Error('Expected token connect without OAuth popup.')
      }
      const status = await mcpClient.serverStatus(createdId)
      return { connected: status.connected }
    },
    onSuccess: (r) => {
      setBusy(false)
      onChanged()
      if (r.connected) {
        toast({ title: 'Connected with API token', tone: 'success' })
      } else {
        toast({
          title: 'Connection incomplete',
          description: isGithubPreset
            ? 'Token was saved, but the MCP probe did not report connected. Check the token scopes and try again.'
            : 'Token was saved, but Atlassian MCP did not report connected. Check email/token and try again.',
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
            ? ' — Connect opens Google login (org Workspace account). Requires GOOGLE_OAUTH_CLIENT_ID/SECRET in .env and workspace-mcp running.'
            : null}
          {server.preset === 'github'
            ? ' — paste a PAT below (saved like model keys); OAuth needs a GitHub OAuth App'
            : null}
          {server.preset === 'github_enterprise'
            ? ' — run github-mcp-server with GITHUB_HOST; paste PAT below + MCP URL'
            : null}
        </p>
        {!server.connected && server.preset === 'atlassian' ? (
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Atlassian account email (for API token)
            </span>
            <Input
              type="email"
              value={atlassianEmail}
              onChange={(e) => setAtlassianEmail(e.target.value)}
              placeholder="you@acme.com"
              disabled={busy}
            />
          </label>
        ) : null}
        {!server.connected && (isGithubPreset || server.preset === 'atlassian') ? (
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              {isGithubPreset ? 'GitHub personal access token' : 'Atlassian API token'}
            </span>
            <Input
              type="password"
              autoComplete="off"
              value={tokenDraft}
              onChange={(e) => setTokenDraft(e.target.value)}
              disabled={busy || tokenHint.envLocked}
              placeholder={
                tokenHint.envLocked
                  ? `Locked by ${isGithubPreset ? 'GITHUB_TOKEN' : 'JIRA_API_TOKEN'} in environment`
                  : tokenHint.masked
                    ? 'Saved token present. Enter a new token to replace.'
                    : isGithubPreset
                      ? 'ghp_… or github_pat_…'
                      : 'Paste Atlassian API token'
              }
            />
            {tokenHint.masked && !tokenHint.envLocked ? (
              <span className="text-xs text-muted-foreground">Saved ({tokenHint.masked})</span>
            ) : null}
          </label>
        ) : null}
        {!server.connected && server.preset === 'github_enterprise' ? (
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Self-hosted github-mcp-server URL
            </span>
            <Input
              value={enterpriseMcpUrl}
              onChange={(e) => setEnterpriseMcpUrl(e.target.value)}
              placeholder="http://localhost:8080/mcp"
              disabled={busy}
            />
          </label>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {!server.connected ? (
            <>
              {isGithubPreset ? (
                <>
                  <Button
                    size="sm"
                    disabled={busy}
                    onClick={() => connectWithToken.mutate()}
                  >
                    <Link2 className="h-4 w-4" />
                    {busy ? 'Connecting…' : 'Use API token'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => connect.mutate()}
                    disabled={busy || connect.isPending}
                  >
                    OAuth (needs GitHub App)
                  </Button>
                </>
              ) : (
                <>
                  <Button size="sm" onClick={() => connect.mutate()} disabled={busy || connect.isPending}>
                    <Link2 className="h-4 w-4" />
                    {busy ? 'Connecting…' : 'Connect'}
                  </Button>
                  {server.authMode === 'oauth' && server.preset === 'atlassian' ? (
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
              )}
            </>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Ready for sync
            </span>
          )}
          {authLink ? (
            <a
              className="text-xs text-primary underline"
              href={authLink}
              target="_blank"
              rel="noreferrer"
            >
              Open sign-in link (popup blocked)
            </a>
          ) : null}
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
