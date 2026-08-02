import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook, screen } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'

import { ToastProvider, useToast } from './ToastProvider'

describe('ToastProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows and dismisses a toast', () => {
    const { result } = renderHook(() => useToast(), {
      wrapper: ({ children }) => <ToastProvider>{children}</ToastProvider>,
    })

    act(() => {
      result.current.toast({ title: 'Saved', tone: 'success' })
    })
    expect(screen.getByText('Saved')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByText('Saved')).not.toBeInTheDocument()
  })

  it('auto-dismisses after duration', () => {
    const { result } = renderHook(() => useToast(), {
      wrapper: ({ children }) => <ToastProvider>{children}</ToastProvider>,
    })
    act(() => {
      result.current.toast({ title: 'Temp', durationMs: 1000 })
    })
    expect(screen.getByText('Temp')).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(1100)
    })
    expect(screen.queryByText('Temp')).not.toBeInTheDocument()
  })
})
