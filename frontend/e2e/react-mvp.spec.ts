import { test, expect, type Page } from '@playwright/test'

async function mockLlmConfig(page: Page) {
  await page.route('**/config/llm', async (route) => {
    await route.fulfill({
      json: {
        default_provider: 'ollama',
        default_model_by_provider: {
          ollama: 'qwen2.5:7b',
          openai: 'gpt-4o-mini',
        },
        allowed_models_by_provider: {
          ollama: ['qwen2.5:7b'],
          openai: ['gpt-4o-mini'],
        },
        provider_key_configured: {
          ollama: true,
          openai: true,
        },
        demo_mode: true,
      },
    })
  })
}

test('no uploads keeps Mine and Both disabled', async ({ page }) => {
  await mockLlmConfig(page)
  await page.route('**/sessions', async (route) => {
    await route.fulfill({
      json: {
        session_id: 'abc123demo',
        expires_at: Math.floor(Date.now() / 1000) + 1800,
        files: [],
        total_bytes: 0,
        max_session_bytes: 8388608,
        max_files: 3,
      },
    })
  })
  await page.route('**/sessions/abc123demo', async (route) => {
    await route.fulfill({
      json: {
        session_id: 'abc123demo',
        expires_at: Math.floor(Date.now() / 1000) + 1800,
        files: [],
        total_bytes: 0,
        max_session_bytes: 8388608,
        max_files: 3,
      },
    })
  })

  await page.goto('/')
  await page.getByRole('tab', { name: 'Query' }).click()
  await expect(page.getByRole('radio', { name: /my uploads only/i })).toBeDisabled()
  await expect(page.getByRole('radio', { name: /both/i })).toBeDisabled()
})

test('query streams an answer', async ({ page }) => {
  await mockLlmConfig(page)
  await page.route('**/sessions', async (route) => {
    await route.fulfill({
      json: {
        session_id: 'abc123demo',
        expires_at: Math.floor(Date.now() / 1000) + 1800,
        files: [],
        total_bytes: 0,
        max_session_bytes: 8388608,
        max_files: 3,
      },
    })
  })
  await page.route('**/query/stream', async (route) => {
    await route.fulfill({
      contentType: 'text/event-stream',
      body: 'data: {"type":"token","text":"Hello from stream"}\n\ndata: {"type":"final","citations":[],"provider":"ollama","model":"llama3"}\n\ndata: [DONE]\n\n',
    })
  })

  await page.goto('/')
  await page.getByRole('tab', { name: 'Query' }).click()
  await page.getByRole('textbox', { name: /question/i }).fill('What is RAG?')
  await page.getByRole('button', { name: 'Run' }).click()
  await expect(page.getByText('Hello from stream')).toBeVisible()
})
