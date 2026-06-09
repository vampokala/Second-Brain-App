import { test, expect, type Page } from '@playwright/test'

async function mockLlmConfig(page: Page) {
  await page.route('**/config/llm', async (route) => {
    await route.fulfill({
      json: {
        default_provider: 'ollama',
        default_model_by_provider: { ollama: 'qwen2.5:7b' },
        allowed_models_by_provider: { ollama: ['qwen2.5:7b'] },
        provider_key_configured: { ollama: true },
        demo_mode: false,
      },
    })
  })
  await page.route('**/vault/stats', async (route) => {
    await route.fulfill({ json: { file_count: 0, chunk_count: 0, last_ingest_at: null, embed_model: null } })
  })
}

const CHAT_ID = '11111111-1111-1111-1111-111111111111'

function detail(messages: unknown[]) {
  return {
    id: CHAT_ID,
    title: 'Mock Chat',
    pinned: false,
    system_prompt: null,
    provider: 'ollama',
    model: 'qwen2.5:7b',
    knowledge_scope: 'vault',
    messages,
  }
}

test.describe('ask (chat)', () => {
  test('shows the chat composer and new-chat control', async ({ page }) => {
    await mockLlmConfig(page)
    await page.route('**/chats', async (route) => route.fulfill({ json: [] }))
    await page.goto('/')
    await expect(page.getByRole('button', { name: '+ New chat' })).toBeVisible()
    await expect(page.getByPlaceholder(/^Message/)).toBeVisible()
  })

  test('renders retrieved chunks under the assistant answer', async ({ page }) => {
    await mockLlmConfig(page)

    await page.route('**/chats', async (route) => {
      await route.fulfill({
        json: [
          {
            id: CHAT_ID,
            title: 'Mock Chat',
            updated_at: new Date().toISOString(),
            model: 'qwen2.5:7b',
            provider: 'ollama',
            pinned: false,
          },
        ],
      })
    })
    await page.route('**/chats/search**', async (route) => route.fulfill({ json: [] }))

    // First GET (on select) = empty; after sending, GET returns the assistant turn.
    let detailCalls = 0
    await page.route(`**/chats/${CHAT_ID}`, async (route) => {
      if (route.request().method() !== 'GET') return route.fallback()
      detailCalls += 1
      const messages =
        detailCalls === 1
          ? []
          : [
              { id: 'user-1', role: 'user', content: 'hi', parent_id: null, created_at: '', citations: [] },
              {
                id: 'asst-1',
                role: 'assistant',
                content: 'Markdown and PDF.',
                parent_id: 'user-1',
                created_at: '',
                citations: [],
                // Persisted on the message (survives reload); panel reads from here.
                retrieved: [
                  { id: 'c1', score: 0.42, source: 'raw/a.md', preview: 'alpha preview' },
                  { id: 'c2', score: 0.31, source: 'raw/b.md', preview: 'beta preview' },
                ],
              },
            ]
      await route.fulfill({ json: detail(messages) })
    })

    // The streamed answer: a retrieval event with two chunks, then tokens, then final.
    await page.route(`**/chats/${CHAT_ID}/messages`, async (route) => {
      const body = [
        'event: retrieval',
        'data: {"chunks":[{"id":"c1","score":0.42,"source":"raw/a.md","preview":"alpha preview"},{"id":"c2","score":0.31,"source":"raw/b.md","preview":"beta preview"}]}',
        '',
        'event: token',
        'data: {"text":"Markdown and PDF."}',
        '',
        'event: final',
        'data: {"message_id":"asst-1","provider":"ollama","model":"qwen2.5:7b","elapsed_ms":5}',
        '',
        '',
      ].join('\n')
      await route.fulfill({ contentType: 'text/event-stream', body })
    })

    await page.goto('/')
    await page.getByText('Mock Chat').click()
    await page.getByPlaceholder(/^Message/).fill('what formats?')
    await page.getByRole('button', { name: 'Send' }).click()

    const panel = page.getByText(/Retrieved chunks \(2\)/)
    await expect(panel).toBeVisible()
    await panel.click()
    await expect(page.getByText('raw/a.md')).toBeVisible()
    await expect(page.getByText('beta preview')).toBeVisible()
  })
})
