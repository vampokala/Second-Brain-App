export type GroundingMode = 'corpus_only' | 'allow_general'

export type ChatMetaEvent = {
  grounding_mode: GroundingMode
  include_web_search: boolean
  hit_count: number
  max_score?: number
  web_pages_fetched?: number
  persona_display?: string
  persona_addon_applied?: boolean
  brave_key_configured?: boolean
}

export type ChatTruthfulness = {
  nli_faithfulness: number
  citation_groundedness: number
  uncited_claims: number
  score: number
}

export type ChatSseEvent =
  | { event: 'token'; data: { text: string } }
  | { event: 'retrieval'; data: { chunks: unknown[] } }
  | { event: 'citations'; data: { citations: unknown[] } }
  | { event: 'meta'; data: ChatMetaEvent }
  | {
      event: 'final'
      data: {
        message_id: string
        provider: string
        model: string
        elapsed_ms: number
        citation_count?: number
        retrieved_count?: number
        truthfulness?: ChatTruthfulness
      }
    }
  | { event: 'error'; data: { message: string } }

export async function streamChatPost(
  url: string,
  body: object | null,
  onEvent: (e: ChatSseEvent) => void,
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: body === null ? undefined : JSON.stringify(body),
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
