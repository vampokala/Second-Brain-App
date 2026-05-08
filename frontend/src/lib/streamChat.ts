export type ChatSseEvent =
  | { event: 'token'; data: { text: string } }
  | { event: 'retrieval'; data: { chunks: unknown[] } }
  | { event: 'citations'; data: { citations: unknown[] } }
  | { event: 'final'; data: { message_id: string; provider: string; model: string; elapsed_ms: number } }
  | { event: 'error'; data: { message: string } }

export async function streamChatPost(
  url: string,
  body: object,
  onEvent: (e: ChatSseEvent) => void,
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    onEvent({ event: 'error', data: { message: (await res.text()) || res.statusText } })
    return
  }
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let split
    while ((split = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, split)
      buf = buf.slice(split + 2)
      let eventName: string | null = null
      let dataRaw: string | null = null
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        if (line.startsWith('data:')) dataRaw = line.slice(5).trim()
      }
      if (eventName && dataRaw) {
        try {
          const data = JSON.parse(dataRaw) as Record<string, unknown>
          onEvent({ event: eventName as ChatSseEvent['event'], data: data as never })
        } catch {
          /* skip malformed */
        }
      }
    }
  }
}
