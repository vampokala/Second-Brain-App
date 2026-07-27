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

vi.mock('../components/toast/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

import { mcpClient } from '../api/mcpClient'

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
})
