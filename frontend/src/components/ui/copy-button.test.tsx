import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { CopyButton } from './copy-button'

describe('CopyButton', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('copies text and shows check feedback', async () => {
    const user = userEvent.setup()
    render(<CopyButton text="hello world" label="Copy message" />)
    const btn = screen.getByRole('button', { name: 'Copy message' })

    await user.click(btn)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello world')
    expect(btn.querySelector('svg')).toBeTruthy()
  })

  it('is disabled for empty text', () => {
    render(<CopyButton text="" label="Copy empty" />)
    expect(screen.getByRole('button', { name: 'Copy empty' })).toBeDisabled()
  })
})
