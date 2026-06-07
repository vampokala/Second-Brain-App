export type Section = 'ask' | 'knowledge' | 'settings' | 'help'

export type AskView = 'chat' | 'quick'

export const SECTION_TITLES: Record<Section, string> = {
  ask: 'Ask',
  knowledge: 'Knowledge',
  settings: 'Settings',
  help: 'Help',
}
