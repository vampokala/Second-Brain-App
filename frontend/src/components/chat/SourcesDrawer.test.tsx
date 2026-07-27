import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { SourcesDrawer } from './SourcesDrawer'

describe('SourcesDrawer', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <SourcesDrawer open={false} onClose={() => undefined} citations={[]} chunks={[]} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows citation title, score, preview, and vault action', async () => {
    const user = userEvent.setup()
    let opened = ''
    render(
      <SourcesDrawer
        open
        onClose={() => undefined}
        citations={[
          {
            chunk_id: '1',
            source: 'raw/docs/a.md',
            title: 'Alpha',
            score: 0.42,
            preview: 'preview text',
          },
        ]}
        chunks={[]}
        onOpenVault={(p) => {
          opened = p
        }}
      />,
    )
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText(/score 0\.420/)).toBeInTheDocument()
    expect(screen.getByText('preview text')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Open in vault/i }))
    expect(opened).toBe('raw/docs/a.md')
  })

  it('shows empty copy when no sources', () => {
    render(<SourcesDrawer open onClose={() => undefined} citations={[]} chunks={[]} />)
    expect(screen.getByText(/No sources for this answer yet/i)).toBeInTheDocument()
  })
})
