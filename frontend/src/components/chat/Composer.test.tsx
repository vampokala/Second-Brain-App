import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Composer } from './Composer'

describe('Composer', () => {
  it('sends on Enter and keeps text on Shift+Enter', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<Composer onSend={onSend} />)

    const box = screen.getByPlaceholderText(/Enter to send/)
    await user.type(box, 'hello')
    await user.keyboard('{Enter}')
    expect(onSend).toHaveBeenCalledWith('hello', {
      groundingMode: 'corpus_only',
      includeWebSearch: false,
    })

    onSend.mockClear()
    await user.type(box, 'line1')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    await user.type(box, 'line2')
    expect(onSend).not.toHaveBeenCalled()
    expect((box as HTMLTextAreaElement).value).toContain('line1')
    expect((box as HTMLTextAreaElement).value).toContain('line2')
  })

  it('does not send when disabled', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<Composer onSend={onSend} disabled />)
    const box = screen.getByPlaceholderText(/Enter to send/)
    await user.type(box, 'nope{Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('toggles grounding mode and web search', async () => {
    const user = userEvent.setup()
    const onGroundingModeChange = vi.fn()
    const onIncludeWebSearchChange = vi.fn()
    render(
      <Composer
        onSend={vi.fn()}
        groundingMode="corpus_only"
        onGroundingModeChange={onGroundingModeChange}
        includeWebSearch={false}
        onIncludeWebSearchChange={onIncludeWebSearchChange}
        webSearchAvailable
      />,
    )

    await user.click(screen.getByLabelText(/Corpus only/i))
    expect(onGroundingModeChange).toHaveBeenCalledWith('allow_general')

    await user.click(screen.getByLabelText(/Web search/i))
    expect(onIncludeWebSearchChange).toHaveBeenCalledWith(true)
  })

  it('shows persona chip and action buttons when provided', () => {
    const onSave = vi.fn()
    const onMemory = vi.fn()
    render(
      <Composer
        onSend={vi.fn()}
        personaLabel="Architect"
        onSaveToWiki={onSave}
        onUpdateMemory={onMemory}
      />,
    )
    expect(screen.getByText('Architect')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Save to wiki/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Update memory/i })).toBeInTheDocument()
  })
})
