import { describe, expect, it } from 'vitest'

import {
  formatIngestProgressLine,
  normalizeIngestProgress,
  progressRowFromPayload,
  progressStatusFromText,
} from './ingestProgress'

describe('progressStatusFromText', () => {
  it('maps success keywords to ok', () => {
    expect(progressStatusFromText('ingest complete')).toBe('ok')
  })

  it('maps failure keywords to error', () => {
    expect(progressStatusFromText('upload failed')).toBe('error')
  })

  it('defaults to running for unknown text', () => {
    expect(progressStatusFromText('chunking')).toBe('running')
  })

  it('maps skipped to ok', () => {
    expect(progressStatusFromText('file skipped')).toBe('ok')
  })
})

describe('formatIngestProgressLine', () => {
  it('formats counters and path', () => {
    expect(
      formatIngestProgressLine({
        current: 1,
        total: 3,
        relative_path: 'raw/a.csv',
        phase: 'file',
        message: 'extracting',
      }),
    ).toBe('[1/3] raw/a.csv · file: extracting')
  })
})

describe('normalizeIngestProgress', () => {
  it('maps legacy App SSE fields to Lite-shaped payload', () => {
    const n = normalizeIngestProgress({
      file_path: 'raw/notes/doc.pdf',
      event_type: 'ingest',
      status: 'ingested',
      details: { chunk_count: 3, error: null },
      current: 2,
      total: 10,
    })
    expect(n.relative_path).toBe('raw/notes/doc.pdf')
    expect(n.phase).toBe('file')
    expect(n.message).toContain('ingested')
    expect(n.current).toBe(2)
    expect(n.total).toBe(10)
  })

  it('surfaces error detail in message', () => {
    const n = normalizeIngestProgress({
      file_path: 'raw/bad.bin',
      event_type: 'ingest',
      status: 'failed',
      details: { error: 'unsupported' },
    })
    expect(n.message).toContain('unsupported')
  })
})

describe('progressRowFromPayload', () => {
  it('builds a row from legacy SSE', () => {
    const row = progressRowFromPayload({
      file_path: 'raw/a.md',
      event_type: 'ingest',
      status: 'processing',
    })
    expect(row?.label).toBe('raw/a.md')
    expect(row?.status).toBe('running')
  })
})
