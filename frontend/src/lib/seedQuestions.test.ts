import { describe, expect, it } from 'vitest'

import { SEED_QUESTIONS } from './seedQuestions'

describe('seedQuestions', () => {
  it('exposes exactly three starter prompts', () => {
    expect(SEED_QUESTIONS).toHaveLength(3)
    for (const q of SEED_QUESTIONS) {
      expect(q.length).toBeGreaterThan(8)
    }
  })
})
