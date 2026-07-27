import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { TruthfulnessBadge } from './TruthfulnessBadge'

describe('TruthfulnessBadge', () => {
  it('shows score and success variant for high scores', () => {
    render(
      <TruthfulnessBadge
        truthfulness={{
          score: 0.92,
          nli_faithfulness: 0.9,
          citation_groundedness: 0.95,
          uncited_claims: 0,
        }}
      />,
    )
    expect(screen.getByText('Truthfulness 0.92')).toBeInTheDocument()
  })

  it('uses warning variant for mid scores', () => {
    const { container } = render(
      <TruthfulnessBadge
        truthfulness={{
          score: 0.7,
          nli_faithfulness: 0.65,
          citation_groundedness: 0.72,
          uncited_claims: 1,
        }}
      />,
    )
    expect(container.textContent).toContain('Truthfulness 0.70')
  })
})
