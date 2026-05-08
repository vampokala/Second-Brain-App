/** Hash URL for Vault tab deep-linking from citations. */
export function vaultPathQuery(path: string): string {
  const q = encodeURIComponent(path.replace(/^\//, ''))
  return `#/vault?path=${q}`
}

export function parseVaultPathFromHash(): string | null {
  if (typeof window === 'undefined') return null
  const { hash } = window.location
  if (!hash.includes('vault')) return null
  const m = hash.match(/path=([^&]+)/)
  return m ? decodeURIComponent(m[1]) : null
}
