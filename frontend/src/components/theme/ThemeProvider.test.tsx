import { describe, expect, it, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'

import { ThemeProvider, useTheme } from './ThemeProvider'

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('cycles light → system → dark', () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    })

    act(() => result.current.setTheme('light'))
    expect(result.current.theme).toBe('light')
    expect(result.current.resolvedTheme).toBe('light')

    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('system')

    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
