import { beforeEach, describe, expect, it, vi } from 'vitest'

import { mcpClient } from './mcpClient'

describe('mcpClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('maps listServers response shape', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: '1',
            preset: 'atlassian',
            name: 'Atlassian',
            url: 'https://mcp.atlassian.com/v1/mcp/authv2',
            auth_mode: 'oauth',
            connected: false,
            connector_types: ['mcp_jira', 'mcp_confluence'],
            enabled: true,
          },
        ],
      }),
    )
    const rows = await mcpClient.listServers()
    expect(rows[0].authMode).toBe('oauth')
    expect(rows[0].connectorTypes).toContain('mcp_jira')
  })

  it('throws with server detail message on non-2xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => ({ detail: 'Unable to list tools' }),
        text: async () => '',
      }),
    )
    await expect(mcpClient.listTools('1')).rejects.toThrow(/Unable to list tools/)
  })
})
