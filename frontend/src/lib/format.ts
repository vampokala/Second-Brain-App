export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B'
  }
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export function formatTtl(expiresAt: number | null) {
  if (!expiresAt) {
    return 'unknown'
  }
  const seconds = Math.max(0, expiresAt - Math.floor(Date.now() / 1000))
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${minutes}:${remainder.toString().padStart(2, '0')}`
}

export function shortSessionId(sessionId: string | null) {
  return sessionId ? `...${sessionId.slice(-5)}` : 'pending'
}
