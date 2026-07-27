export const SEED_QUESTIONS = [
  'What is this knowledge base about?',
  'Summarize the most important documents.',
  'What should I know before getting started?',
] as const

export type SeedQuestion = (typeof SEED_QUESTIONS)[number]
