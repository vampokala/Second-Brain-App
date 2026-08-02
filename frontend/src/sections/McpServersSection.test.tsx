import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { McpServersSection } from './McpServersSection'

vi.mock('../api/mcpClient', () => ({
  mcpClient: {
    listServers: vi.fn(),
    upsertServer: vi.fn(),
    removeServer: vi.fn(),
    connectServer: vi.fn(),
    serverStatus: vi.fn(),
    listTools: vi.fn(),
  },
}))

vi.mock('../lib/connectorTokens', () => ({
  saveConnectorToken: vi.fn(),
}))

vi.mock('../components/toast/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

import { mcpClient } from '../api/mcpClient'
import { saveConnectorToken } from '../lib/connectorTokens'

function wrap(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('McpServersSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.mocked(mcpClient.listServers).mockResolvedValue([
      {
        id: 'preset:atlassian',
        preset: 'atlassian',
        name: 'Atlassian (JIRA + Confluence)',
        url: 'https://mcp.atlassian.com/v1/mcp/authv2',
        authMode: 'oauth',
        connected: false,
        connectorTypes: ['mcp_jira', 'mcp_confluence'],
        enabled: false,
      },
    ])
  })

  it('renders preset cards with disconnected state', async () => {
    wrap(<McpServersSection />)
    expect(await screen.findByText(/Atlassian/i)).toBeInTheDocument()
    expect(screen.getByText(/Not connected/i)).toBeInTheDocument()
  })

  it('connect click opens popup and polls until connected', async () => {
    vi.useFakeTimers()
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    vi.mocked(mcpClient.upsertServer).mockResolvedValue({
      id: 'srv-1',
      preset: 'atlassian',
      name: 'Atlassian (JIRA + Confluence)',
      url: 'https://mcp.atlassian.com/v1/mcp/authv2',
      authMode: 'oauth',
      connected: false,
      connectorTypes: ['mcp_jira'],
      enabled: true,
    })
    vi.mocked(mcpClient.connectServer).mockResolvedValue({
      authorization_url: 'https://auth.example/authorize',
      state: 's',
    })
    vi.mocked(mcpClient.serverStatus).mockResolvedValue({
      id: 'srv-1',
      preset: 'atlassian',
      name: 'Atlassian',
      url: 'https://x',
      authMode: 'oauth',
      connected: true,
      connectorTypes: [],
      enabled: true,
    })

    wrap(<McpServersSection />)
    await screen.findByText(/Not connected/i)
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })
    await user.click(screen.getByRole('button', { name: /Connect/i }))
    await vi.advanceTimersByTimeAsync(2500)
    await waitFor(() => expect(open).toHaveBeenCalled())
    await waitFor(() => expect(mcpClient.connectServer).toHaveBeenCalled())
    vi.useRealTimers()
  })

  it('saves GitHub PAT via settings then connects with token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ values: {}, env_override_keys: [] }),
      }),
    )
    vi.mocked(mcpClient.listServers).mockResolvedValue([
      {
        id: 'preset:github',
        preset: 'github',
        name: 'GitHub',
        url: 'https://api.githubcopilot.com/mcp',
        authMode: 'oauth',
        connected: false,
        connectorTypes: ['mcp_github'],
        enabled: false,
      },
    ])
    vi.mocked(saveConnectorToken).mockResolvedValue({ values: {}, env_override_keys: [] })
    vi.mocked(mcpClient.upsertServer).mockResolvedValue({
      id: 'gh-1',
      preset: 'github',
      name: 'GitHub',
      url: 'https://api.githubcopilot.com/mcp',
      authMode: 'token',
      connected: false,
      connectorTypes: ['mcp_github'],
      enabled: true,
    })
    vi.mocked(mcpClient.connectServer).mockResolvedValue({
      authorization_url: '',
      state: 'verified',
    })
    vi.mocked(mcpClient.serverStatus).mockResolvedValue({
      id: 'gh-1',
      preset: 'github',
      name: 'GitHub',
      url: 'https://api.githubcopilot.com/mcp',
      authMode: 'token',
      connected: true,
      connectorTypes: ['mcp_github'],
      enabled: true,
    })

    wrap(<McpServersSection />)
    expect(await screen.findByPlaceholderText(/ghp_/i)).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(screen.getByPlaceholderText(/ghp_/i), 'ghp_testtoken')
    await user.click(screen.getByRole('button', { name: /Use API token/i }))
    await waitFor(() =>
      expect(saveConnectorToken).toHaveBeenCalledWith('github_token', 'ghp_testtoken'),
    )
    await waitFor(() => expect(mcpClient.connectServer).toHaveBeenCalledWith('gh-1'))
  })
})
