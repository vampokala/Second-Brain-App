import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import { IngestScanTab } from './IngestScanTab'

vi.mock('../api/ingestClient', () => ({
  ingestClient: {
    scanPreview: vi.fn(),
    ingestPaths: vi.fn(),
    cancel: vi.fn(),
  },
}))

vi.mock('../api/vaultClient', () => ({
  vaultClient: {
    stats: vi.fn().mockResolvedValue({
      file_count: 0,
      chunk_count: 0,
      vault_path: '/vault',
      vault_host_path: '/Users/demo/Second-Brain',
    }),
  },
}))

const sseHandlers: Array<(p: Record<string, unknown>) => void> = []

vi.mock('../lib/sseClient', () => ({
  ingestEventsSource: (onMessage: (p: Record<string, unknown>) => void) => {
    sseHandlers.push(onMessage)
    return { close: vi.fn() }
  },
}))

vi.mock('../components/toast/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

import { ingestClient } from '../api/ingestClient'

describe('IngestScanTab', () => {
  beforeEach(() => {
    vi.mocked(ingestClient.scanPreview).mockReset()
    vi.mocked(ingestClient.ingestPaths).mockReset()
    vi.mocked(ingestClient.cancel).mockReset()
    sseHandlers.length = 0
  })

  it('shows the current vault folder from stats', async () => {
    render(<IngestScanTab />)
    await waitFor(() => {
      expect(screen.getByText(/vault folder/i)).toBeInTheDocument()
    })
    expect(screen.getByText('/Users/demo/Second-Brain')).toBeInTheDocument()
  })

  it('scan fills candidates and enables ingest for selected paths', async () => {
    vi.mocked(ingestClient.scanPreview).mockResolvedValue({
      files: [
        { path: 'raw/notes/a.md', change: 'new', size: 1, mtime_ms: 1 },
        { path: 'raw/notes/b.md', change: 'changed', size: 2, mtime_ms: 2 },
      ],
      summary: { total_scanned: 3, new: 1, changed: 1, unchanged: 1 },
    })
    vi.mocked(ingestClient.ingestPaths).mockResolvedValue({
      status: 'started',
      selected: 2,
    })

    render(<IngestScanTab />)

    const ingestBtn = screen.getByRole('button', { name: /^ingest$/i })
    expect(ingestBtn).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /^scan$/i }))

    await waitFor(() => {
      expect(ingestClient.scanPreview).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(screen.getByText('Candidates')).toBeInTheDocument()
    })
    expect(screen.getByText(/2 selected/)).toBeInTheDocument()
    expect(ingestBtn).not.toBeDisabled()

    fireEvent.click(ingestBtn)
    await waitFor(() => {
      expect(ingestClient.ingestPaths).toHaveBeenCalledWith(
        expect.arrayContaining(['raw/notes/a.md', 'raw/notes/b.md']),
      )
    })
  })

  it('directory checkbox selects child files', async () => {
    vi.mocked(ingestClient.scanPreview).mockResolvedValue({
      files: [
        { path: 'raw/notes/a.md', change: 'new', size: 1, mtime_ms: 1 },
        { path: 'raw/notes/b.md', change: 'changed', size: 2, mtime_ms: 2 },
      ],
      summary: { total_scanned: 2, new: 1, changed: 1, unchanged: 0 },
    })

    render(<IngestScanTab />)
    fireEvent.click(screen.getByRole('button', { name: /^scan$/i }))
    await waitFor(() => {
      expect(screen.getByText('Candidates')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(screen.getByText(/0 selected/)).toBeInTheDocument()

    const dirBox = screen.getByRole('checkbox', { name: /select directory notes/i })
    fireEvent.click(dirBox)
    expect(screen.getByText(/2 selected/)).toBeInTheDocument()
  })

  it('shows summary from SSE complete after ingest', async () => {
    vi.mocked(ingestClient.scanPreview).mockResolvedValue({
      files: [{ path: 'raw/a.md', change: 'new', size: 1, mtime_ms: 1 }],
      summary: { total_scanned: 1, new: 1, changed: 0, unchanged: 0 },
    })
    vi.mocked(ingestClient.ingestPaths).mockResolvedValue({ status: 'started', selected: 1 })

    render(<IngestScanTab />)
    fireEvent.click(screen.getByRole('button', { name: /^scan$/i }))
    await waitFor(() => expect(screen.getByText('Candidates')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^ingest$/i }))

    const handler = sseHandlers[0]
    expect(handler).toBeTruthy()
    handler({
      phase: 'scan',
      status: 'complete',
      details: {
        total: 1,
        ingested: 1,
        skipped: 0,
        failed: 0,
        cancelled: 0,
        failed_paths: [],
      },
    })

    await waitFor(() => {
      expect(screen.getByText('Summary')).toBeInTheDocument()
    })
  })

  it('disables ingest when nothing is selected', async () => {
    vi.mocked(ingestClient.scanPreview).mockResolvedValue({
      files: [{ path: 'raw/a.md', change: 'new', size: 1, mtime_ms: 1 }],
      summary: { total_scanned: 1, new: 1, changed: 0, unchanged: 0 },
    })

    render(<IngestScanTab />)
    fireEvent.click(screen.getByRole('button', { name: /^scan$/i }))
    await waitFor(() => expect(screen.getByText('Candidates')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(screen.getByRole('button', { name: /^ingest$/i })).toBeDisabled()
  })
})
