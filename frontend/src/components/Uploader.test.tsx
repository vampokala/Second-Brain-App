import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Uploader } from './Uploader'

describe('Uploader', () => {
  it('shows client-side file count cap messaging', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <Uploader
          sessionId="abc123demo"
          onUploaded={vi.fn()}
          summary={{
            session_id: 'abc123demo',
            expires_at: 1,
            files: [
              { name: 'a.md', size_bytes: 1 },
              { name: 'b.md', size_bytes: 1 },
              { name: 'c.md', size_bytes: 1 },
            ],
            total_bytes: 3,
            max_files: 3,
            max_session_bytes: 100,
          }}
        />
      </QueryClientProvider>,
    )
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, new File(['hello'], 'd.md', { type: 'text/markdown' }))
    expect(screen.getByText(/upload 0 more file/i)).toBeInTheDocument()
  })
})
