import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const fetchLlmConfig = vi.fn()

vi.mock('../api/client', () => ({
  fetchLlmConfig: (...args: unknown[]) => fetchLlmConfig(...args),
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

describe('SettingsTab AI Gateway', () => {
  beforeEach(() => {
    fetchLlmConfig.mockResolvedValue({
      default_provider: 'ollama',
      default_model_by_provider: { gateway: '' },
      allowed_models_by_provider: { gateway: [] },
      provider_key_configured: { gateway: false },
      gateway_base_url: 'http://localhost:4000/v1',
      demo_mode: false,
    })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ values: {}, env_override_keys: [] }),
    }) as unknown as typeof fetch
  })

  it('saves gateway url, api key, and default model together', async () => {
    render(<SettingsTab />)
    await waitFor(() => {
      expect(screen.getByText('AI Gateway')).toBeInTheDocument()
    })

    const url = screen.getByPlaceholderText('http://localhost:4000/v1')
    const key = screen.getByPlaceholderText('Paste gateway API key')
    const model = screen.getByPlaceholderText('e.g. gpt-4o-mini or org-route-name')

    fireEvent.change(url, { target: { value: 'http://litellm.corp/v1' } })
    fireEvent.change(key, { target: { value: 'sk-org-key' } })
    fireEvent.change(model, { target: { value: 'acme-gpt' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save AI Gateway settings' }))

    await waitFor(() => {
      const patchCalls = vi.mocked(globalThis.fetch).mock.calls.filter(
        (c) => c[0] === '/settings' && (c[1] as RequestInit | undefined)?.method === 'PATCH',
      )
      expect(patchCalls.length).toBeGreaterThan(0)
      const body = JSON.parse(String((patchCalls[0][1] as RequestInit).body))
      expect(body.patch.gateway_base_url).toBe('http://litellm.corp/v1')
      expect(body.patch.gateway_api_key).toEqual({ secret: 'sk-org-key' })
      expect(body.patch.default_model_by_provider).toEqual({ gateway: 'acme-gpt' })
      expect(body.patch.allowed_models_by_provider).toEqual({ gateway: ['acme-gpt'] })
    })
  })

  it('disables save when all gateway fields are empty', async () => {
    fetchLlmConfig.mockResolvedValue({
      default_provider: 'ollama',
      default_model_by_provider: {},
      allowed_models_by_provider: {},
      provider_key_configured: {},
      gateway_base_url: '',
      demo_mode: false,
    })
    render(<SettingsTab />)
    await waitFor(() => {
      expect(screen.getByText('AI Gateway')).toBeInTheDocument()
    })
    // Clear the prefilled URL from llm config (empty in this case).
    const save = screen.getByRole('button', { name: 'Save AI Gateway settings' })
    expect(save).toBeDisabled()
  })
})
