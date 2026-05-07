import { API_BASE_URL, ApiError, networkFailureError } from '../api/client'
import type { CitationModel, QueryRequestModel, RetrievedChunkModel, TruthfulnessModel } from '../api/generated'

export type StreamEvent =
  | { type: 'token'; text: string }
  | {
      type: 'final'
      citations: CitationModel[]
      retrieved?: RetrievedChunkModel[]
      truthfulness?: TruthfulnessModel | null
      provider: string
      model: string
    }
  | { type: 'error'; message: string }

export interface StreamQueryCallbacks {
  onToken: (text: string) => void
  onFinal: (event: Extract<StreamEvent, { type: 'final' }>) => void
  onError?: (message: string) => void
}

function parseSseFrame(frame: string): StreamEvent[] {
  return frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim())
    .filter((data) => data && data !== '[DONE]')
    .map((data) => JSON.parse(data) as StreamEvent)
}

async function parseError(response: Response) {
  try {
    const body = await response.json()
    return body?.detail ? String(body.detail) : `Stream failed with status ${response.status}`
  } catch {
    return `Stream failed with status ${response.status}`
  }
}

export async function streamQuery(request: QueryRequestModel, callbacks: StreamQueryCallbacks) {
  const apiKey = localStorage.getItem('doc-ingestion.api-key')
  const headers = new Headers({ 'Content-Type': 'application/json' })
  if (apiKey) {
    headers.set('X-API-Key', apiKey)
  }

  const streamPath =
    API_BASE_URL && API_BASE_URL.length > 0 ? `${API_BASE_URL}/query/stream` : '/query/stream'
  let response: Response
  try {
    response = await fetch(streamPath, {
      method: 'POST',
      headers,
      body: JSON.stringify({ ...request, stream: true }),
    })
  } catch (cause) {
    throw networkFailureError(cause)
  }

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status, null)
  }
  if (!response.body) {
    throw new ApiError('Streaming is not supported by this browser.', response.status, null)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      for (const event of parseSseFrame(frame)) {
        if (event.type === 'token') {
          callbacks.onToken(event.text)
        } else if (event.type === 'final') {
          callbacks.onFinal(event)
        } else if (event.type === 'error') {
          callbacks.onError?.(event.message)
          throw new ApiError(event.message, response.status, event)
        }
      }
    }

    if (done) {
      break
    }
  }
}

export const testInternals = { parseSseFrame }
