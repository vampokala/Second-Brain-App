/** Keep ids aligned with backend `src/core/personas.py`. */

export const DEFAULT_CHAT_PERSONA = 'wiki_maintainer'
export const DEFAULT_STUDENT_GRADE = '9'

/** Used until GET /settings/personas returns options. */
export const FALLBACK_PERSONA_OPTIONS: { id: string; label: string }[] = [
  { id: 'wiki_maintainer', label: 'Wiki maintainer' },
  { id: 'software_engineer', label: 'Software engineer' },
  { id: 'business_analyst', label: 'Business analyst' },
  { id: 'product_owner', label: 'Product owner' },
  { id: 'tester', label: 'Tester / QA' },
  { id: 'architect', label: 'Architect' },
  { id: 'technical_manager', label: 'Technical manager' },
  { id: 'small_business_owner', label: 'Small business owner' },
  { id: 'student', label: 'Student' },
]

export const FALLBACK_GRADE_OPTIONS: { id: string; label: string }[] = [
  { id: 'K', label: 'Kindergarten' },
  ...Array.from({ length: 12 }, (_, i) => ({
    id: String(i + 1),
    label: `Grade ${i + 1}`,
  })),
]

const KNOWN = new Set(FALLBACK_PERSONA_OPTIONS.map((p) => p.id))

const LABELS: Record<string, string> = Object.fromEntries(
  FALLBACK_PERSONA_OPTIONS.map((p) => [p.id, p.label]),
)

export function normalizeChatPersona(raw: string | undefined | null): string {
  const s = (raw ?? '').trim()
  if (KNOWN.has(s)) return s
  return DEFAULT_CHAT_PERSONA
}

export function resolvedStudentGradeToken(grade: string | undefined | null): string {
  const g = (grade ?? '').trim()
  if (g.toLowerCase() === 'k') return 'K'
  const n = Number.parseInt(g, 10)
  if (Number.isFinite(n) && n >= 1 && n <= 12) return String(n)
  return DEFAULT_STUDENT_GRADE
}

export function gradeDisplayLabel(gradeToken: string): string {
  const t = gradeToken.trim()
  if (t === 'K' || t === 'k') return 'Kindergarten'
  const n = Number.parseInt(t, 10)
  if (Number.isFinite(n) && n >= 1 && n <= 12) return `Grade ${n}`
  return 'Grade 9'
}

export function personaLabelForId(id: string): string {
  return LABELS[normalizeChatPersona(id)] ?? LABELS[DEFAULT_CHAT_PERSONA]
}

/** Chip text next to chat checkboxes (matches server `persona_display`). */
export function personaChipLabel(cfg: {
  chatPersona?: string | null
  studentGrade?: string | null
}): string {
  const id = normalizeChatPersona(cfg.chatPersona ?? undefined)
  if (id === 'student') {
    const tok = resolvedStudentGradeToken(cfg.studentGrade)
    return `Student · ${gradeDisplayLabel(tok)}`
  }
  return personaLabelForId(id)
}
