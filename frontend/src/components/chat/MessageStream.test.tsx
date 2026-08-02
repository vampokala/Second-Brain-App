import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { MessageStream } from './MessageStream'
import { SEED_QUESTIONS } from '../../lib/seedQuestions'

describe('MessageStream', () => {
  it('shows seed questions when empty', async () => {
    const user = userEvent.setup()
    let picked = ''
    render(<MessageStream messages={[]} onSeedQuestion={(q) => { picked = q }} />)
    expect(screen.getByText('Ask your knowledge base')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: SEED_QUESTIONS[0] }))
    expect(picked).toBe(SEED_QUESTIONS[0])
  })

  it('shows searching status before tokens arrive', () => {
    render(<MessageStream messages={[]} searching />)
    expect(screen.getByText('Searching knowledge…')).toBeInTheDocument()
  })

  it('exposes regenerate for assistant messages', async () => {
    const user = userEvent.setup()
    let regenId = ''
    render(
      <MessageStream
        messages={[
          {
            id: 'a1',
            role: 'assistant',
            content: 'Answer',
            citations: [],
          },
        ]}
        onRegenerate={(id) => {
          regenId = id
        }}
      />,
    )
    await user.click(screen.getByRole('button', { name: /Regenerate/i }))
    expect(regenId).toBe('a1')
  })
})
