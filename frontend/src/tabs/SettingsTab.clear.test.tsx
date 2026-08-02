import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/client', () => ({
  fetchLlmConfig: vi.fn().mockResolvedValue({
    default_model_by_provider: {},
    allowed_models_by_provider: {},
    provider_key_configured: {},
    gateway_base_url: 'http://localhost:4000/v1',
  }),
}))

vi.mock('../api/chatsClient', () => ({
  chatsClient: {
    listPersonas: vi.fn().mockResolvedValue(null),
  },
}))

vi.mock('../api/vaultClient', () => ({
  vaultClient: {
    clear: vi.fn(),
  },
}))

vi.mock('../components/toast/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

import { SettingsTab } from './SettingsTab'
import { vaultClient } from '../api/vaultClient'

describe('SettingsTab danger zone', () => {
  beforeEach(() => {
    vi.mocked(vaultClient.clear).mockReset()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ values: {}, env_override_keys: [] }),
    }) as unknown as typeof fetch
  })

  it('keeps Delete disabled until delete is typed and a checkbox is checked', async () => {
    render(<SettingsTab />)
    await waitFor(() => {
      expect(screen.getByText('Danger zone')).toBeInTheDocument()
    })

    const deleteBtn = screen.getByRole('button', { name: /delete selected/i })
    expect(deleteBtn).toBeDisabled()

    const vaultBox = screen.getByRole('checkbox', { name: /vault files/i })
    fireEvent.click(vaultBox)
    expect(deleteBtn).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/type delete to confirm/i), {
      target: { value: 'delete' },
    })
    expect(deleteBtn).not.toBeDisabled()
  })

  it('calls vaultClient.clear with selected flags', async () => {
    vi.mocked(vaultClient.clear).mockResolvedValue({
      cleared: { vault: true, memory: false, chats: false },
      detail: 'Cleared: vault',
    })

    render(<SettingsTab />)
    await waitFor(() => {
      expect(screen.getByText('Danger zone')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('checkbox', { name: /vault files/i }))
    fireEvent.change(screen.getByLabelText(/type delete to confirm/i), {
      target: { value: 'delete' },
    })
    fireEvent.click(screen.getByRole('button', { name: /delete selected/i }))

    await waitFor(() => {
      expect(vaultClient.clear).toHaveBeenCalledWith({
        confirm: 'delete',
        clear_vault: true,
        clear_memory: false,
        clear_chats: false,
      })
    })
  })
})
