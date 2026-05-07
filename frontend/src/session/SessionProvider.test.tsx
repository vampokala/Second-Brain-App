import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { useSession } from './SessionContext'
import { SessionProvider } from './SessionProvider'

function TestConsumer() {
  const { sessionId, hasUploads } = useSession()
  return (
    <div>
      <span>session:{sessionId}</span>
      <span>uploads:{String(hasUploads)}</span>
    </div>
  )
}

function renderWithProvider() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <TestConsumer />
      </SessionProvider>
    </QueryClientProvider>,
  )
}

describe('SessionProvider', () => {
  it('mints and stores a session on first mount', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByText('session:abc123demo')).toBeInTheDocument())
    expect(localStorage.getItem('doc-ingestion.demo.session')).toContain('abc123demo')
  })
})
