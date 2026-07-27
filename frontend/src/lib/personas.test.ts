import { describe, expect, it } from 'vitest'

import {
  DEFAULT_CHAT_PERSONA,
  FALLBACK_PERSONA_OPTIONS,
  normalizeChatPersona,
  personaChipLabel,
  personaLabelForId,
} from './personas'

describe('personas', () => {
  it('normalizes unknown personas to default', () => {
    expect(normalizeChatPersona('')).toBe(DEFAULT_CHAT_PERSONA)
    expect(normalizeChatPersona('unknown')).toBe(DEFAULT_CHAT_PERSONA)
  })

  it('returns labels for known personas', () => {
    expect(personaLabelForId('software_engineer')).toBe('Software engineer')
    expect(FALLBACK_PERSONA_OPTIONS.some((p) => p.id === 'student')).toBe(true)
  })

  it('formats student chip with grade', () => {
    expect(
      personaChipLabel({ chatPersona: 'student', studentGrade: '10' }),
    ).toBe('Student · Grade 10')
  })

  it('formats non-student chip', () => {
    expect(personaChipLabel({ chatPersona: 'architect' })).toBe('Architect')
  })
})
