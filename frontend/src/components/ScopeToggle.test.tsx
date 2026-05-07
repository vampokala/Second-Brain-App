import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScopeToggle } from './ScopeToggle'

describe('ScopeToggle', () => {
  it('disables Mine and Both until uploads exist', () => {
    render(<ScopeToggle value="global" onChange={vi.fn()} hasUploads={false} />)
    expect(screen.getByRole('radio', { name: /my uploads only/i })).toBeDisabled()
    expect(screen.getByRole('radio', { name: /both/i })).toBeDisabled()
  })

  it('enables session scopes after upload', async () => {
    const onChange = vi.fn()
    render(<ScopeToggle value="global" onChange={onChange} hasUploads />)
    await userEvent.click(screen.getByRole('radio', { name: /my uploads only/i }))
    expect(onChange).toHaveBeenCalledWith('session')
  })
})
