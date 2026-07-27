import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ConversationList } from './ConversationList'
import type { ChatListItem } from '../../api/chatsClient'

const chats: ChatListItem[] = [
  {
    id: '1',
    title: 'Pinned chat',
    updated_at: new Date().toISOString(),
    model: 'm',
    provider: 'ollama',
    pinned: true,
  },
  {
    id: '2',
    title: 'Recent chat',
    updated_at: new Date().toISOString(),
    model: 'm',
    provider: 'ollama',
    pinned: false,
  },
]

describe('ConversationList', () => {
  it('calls onPin when Pin is chosen from the menu', async () => {
    const user = userEvent.setup()
    const onPin = vi.fn()
    render(
      <ConversationList
        chats={chats}
        activeId="2"
        onSelect={() => undefined}
        onNew={() => undefined}
        onDelete={() => undefined}
        onPin={onPin}
        searchQuery=""
        onSearchChange={() => undefined}
      />,
    )

    const menus = screen.getAllByLabelText('Chat actions')
    await user.click(menus[1])
    await user.click(screen.getByRole('button', { name: /^Pin$/ }))
    expect(onPin).toHaveBeenCalledWith('2', true)
  })
})
