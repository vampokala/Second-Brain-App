/** Setting keys for connector tokens (PATCH /settings → process env). */
export const CONNECTOR_TOKEN_SETTINGS = [
  {
    type: 'github',
    settingKey: 'github_token',
    envName: 'GITHUB_TOKEN',
    label: 'GitHub',
    helper: 'Personal access token (optional for public repos).',
  },
  {
    type: 'jira',
    settingKey: 'jira_api_token',
    envName: 'JIRA_API_TOKEN',
    label: 'JIRA',
    helper: 'Atlassian API token (pair with account email on the connector).',
  },
  {
    type: 'confluence',
    settingKey: 'confluence_api_token',
    envName: 'CONFLUENCE_API_TOKEN',
    label: 'Confluence',
    helper: 'Atlassian API token (pair with account email on the connector).',
  },
  {
    type: 'slack',
    settingKey: 'slack_bot_token',
    envName: 'SLACK_BOT_TOKEN',
    label: 'Slack',
    helper: 'Bot token with channels:history and channels:read.',
  },
] as const

export type ConnectorTokenSetting = (typeof CONNECTOR_TOKEN_SETTINGS)[number]

export function tokenSettingForType(type: string): ConnectorTokenSetting | undefined {
  const legacy =
    type === 'mcp_github'
      ? 'github'
      : type === 'mcp_jira'
        ? 'jira'
        : type === 'mcp_confluence'
          ? 'confluence'
          : type
  return CONNECTOR_TOKEN_SETTINGS.find((c) => c.type === legacy)
}

export async function saveConnectorToken(
  settingKey: string,
  secret: string,
): Promise<{ values: Record<string, unknown>; env_override_keys: string[] }> {
  const res = await fetch('/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patch: { [settingKey]: { secret } } }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ values: Record<string, unknown>; env_override_keys: string[] }>
}
