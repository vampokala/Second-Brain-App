import type { ConnectorType } from './connectorsClient'

export type McpServer = {
  id: string
  preset: string
  name: string
  url: string
  authMode: string
  connected: boolean
  connectorTypes: string[]
  enabled: boolean
}

type McpServerApi = {
  id: string
  preset: string
  name: string
  url: string
  auth_mode: string
  connected: boolean
  connector_types: string[]
  enabled: boolean
}

export type McpTool = {
  name: string
  description: string
  inputSchema: unknown
}

export type McpServerUpsert = {
  preset: string
  name?: string
  url?: string
  auth_mode?: string
  token_env?: string
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { detail?: string }
      detail = typeof body.detail === 'string' ? body.detail : ''
    } catch {
      detail = await res.text().catch(() => '')
    }
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return (await res.json()) as T
}

function mapServer(row: McpServerApi): McpServer {
  return {
    id: row.id,
    preset: row.preset,
    name: row.name,
    url: row.url,
    authMode: row.auth_mode,
    connected: row.connected,
    connectorTypes: row.connector_types ?? [],
    enabled: row.enabled,
  }
}

export const mcpClient = {
  listServers: async (): Promise<McpServer[]> => {
    const rows = await fetch('/mcp/servers').then((r) => asJson<McpServerApi[]>(r))
    return rows.map(mapServer)
  },
  upsertServer: async (body: McpServerUpsert): Promise<McpServer> => {
    const row = await fetch('/mcp/servers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => asJson<McpServerApi>(r))
    return mapServer(row)
  },
  removeServer: (id: string) =>
    fetch(`/mcp/servers/${id}`, { method: 'DELETE' }).then((r) => asJson<{ status: string }>(r)),
  connectServer: (id: string) =>
    fetch(`/mcp/servers/${id}/connect`, { method: 'POST' }).then((r) =>
      asJson<{ authorization_url: string; state: string }>(r),
    ),
  serverStatus: async (id: string): Promise<McpServer> => {
    const row = await fetch(`/mcp/servers/${id}/status`).then((r) => asJson<McpServerApi>(r))
    return mapServer(row)
  },
  listTools: async (id: string): Promise<McpTool[]> => {
    const rows = await fetch(`/mcp/servers/${id}/tools`).then((r) =>
      asJson<Array<{ name: string; description: string; input_schema: unknown }>>(r),
    )
    return rows.map((t) => ({
      name: t.name,
      description: t.description,
      inputSchema: t.input_schema,
    }))
  },
}

export type McpConnectorType =
  | 'mcp_jira'
  | 'mcp_confluence'
  | 'mcp_github'
  | 'mcp_gmail'
  | 'mcp_gchat'
  | 'mcp_custom'

export type ExtendedConnectorType = ConnectorType | McpConnectorType

export function isMcpConnectorType(type: string): type is McpConnectorType {
  return type.startsWith('mcp_')
}
