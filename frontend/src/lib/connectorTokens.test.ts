import { describe, expect, it } from 'vitest'

import { CONNECTOR_TOKEN_SETTINGS, tokenSettingForType } from './connectorTokens'

describe('connectorTokens', () => {
  it('maps each connector type to a settings key', () => {
    expect(CONNECTOR_TOKEN_SETTINGS).toHaveLength(4)
    expect(tokenSettingForType('github')?.settingKey).toBe('github_token')
    expect(tokenSettingForType('jira')?.envName).toBe('JIRA_API_TOKEN')
    expect(tokenSettingForType('confluence')?.settingKey).toBe('confluence_api_token')
    expect(tokenSettingForType('slack')?.settingKey).toBe('slack_bot_token')
    expect(tokenSettingForType('mcp_github')?.settingKey).toBe('github_token')
    expect(tokenSettingForType('mcp_jira')?.envName).toBe('JIRA_API_TOKEN')
  })

  it('returns undefined for unknown types', () => {
    expect(tokenSettingForType('notion')).toBeUndefined()
  })
})
