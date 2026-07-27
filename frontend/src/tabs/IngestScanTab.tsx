import { useEffect, useRef, useState } from 'react'
import { Play, RefreshCw, Square } from 'lucide-react'

import {
  ingestClient,
  type IngestScanFile,
  type IngestScanPreviewSummary,
  type IngestScanSummary,
} from '../api/ingestClient'
import { vaultClient } from '../api/vaultClient'
import { useToast } from '../components/toast/ToastProvider'
import { Button } from '../components/ui/button'
import { ingestEventsSource } from '../lib/sseClient'
import {
  formatIngestProgressLine,
  normalizeIngestProgress,
  progressRowFromPayload,
  type ProgressRow,
} from '../lib/ingestProgress'
import {
  buildScanTree,
  checkStateForNode,
  selectAllPaths,
  toggleNodeSelection,
  type ScanTreeNode,
} from '../lib/ingestScanTree'

function summaryFromScanEvent(raw: Record<string, unknown>): IngestScanSummary | null {
  const details =
    raw.details && typeof raw.details === 'object'
      ? (raw.details as Record<string, unknown>)
      : {}
  const status = String(raw.status || '')
  const phase = String(raw.phase || raw.event_type || '')
  if (phase !== 'scan' || status !== 'complete') return null
  return {
    total: Number(details.total ?? raw.total ?? 0),
    ingested: Number(details.ingested ?? 0),
    skipped: Number(details.skipped ?? 0),
    failed: Number(details.failed ?? 0),
    cancelled: Number(details.cancelled ?? 0),
  }
}

function failedPathsFromScanEvent(
  raw: Record<string, unknown>,
): Array<{ path: string; error: string }> {
  const details =
    raw.details && typeof raw.details === 'object'
      ? (raw.details as Record<string, unknown>)
      : {}
  const list = details.failed_paths
  if (!Array.isArray(list)) return []
  return list
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const row = item as Record<string, unknown>
      const path = String(row.path || '')
      if (!path) return null
      return { path, error: String(row.error || 'failed') }
    })
    .filter((x): x is { path: string; error: string } => x !== null)
}

function TreeCheckbox({
  node,
  selected,
  onToggle,
  depth,
}: {
  node: ScanTreeNode
  selected: Set<string>
  onToggle: (node: ScanTreeNode) => void
  depth: number
}) {
  const state = checkStateForNode(node, selected)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.indeterminate = state === 'indeterminate'
    }
  }, [state])

  return (
    <li>
      <label
        className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-secondary/60"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <input
          ref={inputRef}
          type="checkbox"
          className="h-4 w-4 accent-foreground"
          checked={state === 'checked'}
          onChange={() => onToggle(node)}
          aria-label={node.kind === 'dir' ? `Select directory ${node.name}` : `Select ${node.name}`}
        />
        <span className="min-w-0 truncate text-sm text-foreground">
          {node.kind === 'dir' ? `${node.name}/` : node.name}
        </span>
        {node.kind === 'file' && node.change ? (
          <span className="shrink-0 text-xs text-muted-foreground">{node.change}</span>
        ) : null}
      </label>
      {node.kind === 'dir' && node.children.length > 0 ? (
        <ul>
          {node.children.map((child) => (
            <TreeCheckbox
              key={child.id}
              node={child}
              selected={selected}
              onToggle={onToggle}
              depth={depth + 1}
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export function IngestScanTab() {
  const { toast } = useToast()
  const [scanning, setScanning] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [files, setFiles] = useState<IngestScanFile[]>([])
  const [previewSummary, setPreviewSummary] = useState<IngestScanPreviewSummary | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [progress, setProgress] = useState<ProgressRow[]>([])
  const [summary, setSummary] = useState<IngestScanSummary | null>(null)
  const [failedPaths, setFailedPaths] = useState<Array<{ path: string; error: string }>>([])
  const [vaultFolder, setVaultFolder] = useState<string | null>(null)

  const tree = buildScanTree(files)
  const selectedCount = selected.size
  const busy = scanning || ingesting

  useEffect(() => {
    let cancelled = false
    void vaultClient
      .stats()
      .then((stats) => {
        if (cancelled) return
        const host = stats.vault_host_path?.trim()
        const path = stats.vault_path?.trim()
        setVaultFolder(host || path || null)
      })
      .catch(() => {
        if (!cancelled) setVaultFolder(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const { close } = ingestEventsSource((p) => {
      const payload = p as Record<string, unknown>
      const normalized = normalizeIngestProgress(payload)
      const scanSummary = summaryFromScanEvent(payload)
      if (scanSummary) {
        setSummary(scanSummary)
        setFailedPaths(failedPathsFromScanEvent(payload))
        setIngesting(false)
        toast({
          title: 'Ingest complete',
          description: `${scanSummary.ingested} ingested, ${scanSummary.skipped} skipped, ${scanSummary.failed} failed`,
        })
        return
      }
      if (String(payload.status || '') === 'failed' && String(payload.phase || payload.event_type) === 'scan') {
        setIngesting(false)
        toast({
          title: 'Ingest failed',
          description: String(normalized.message || 'Selected ingest failed'),
          tone: 'error',
        })
        return
      }
      const row = progressRowFromPayload(payload)
      if (!row) return
      setProgress((prev) => {
        const withoutDup = prev.filter((r) => r.label !== row.label || r.status === 'running')
        const next = [row, ...withoutDup.filter((r) => r.id !== row.id)]
        return next.slice(0, 60)
      })
    })
    return () => close()
  }, [toast])

  async function onScan() {
    setScanning(true)
    setSummary(null)
    setFailedPaths([])
    setProgress([])
    setSelected(new Set())
    setFiles([])
    setPreviewSummary(null)
    try {
      const preview = await ingestClient.scanPreview()
      setFiles(preview.files)
      setPreviewSummary(preview.summary)
      setSelected(selectAllPaths(preview.files))
      toast({
        title: 'Scan complete',
        description: `${preview.summary.new} new, ${preview.summary.changed} changed (${preview.summary.unchanged} unchanged)`,
      })
    } catch (e) {
      toast({
        title: 'Scan failed',
        description: (e as Error).message,
        tone: 'error',
      })
    } finally {
      setScanning(false)
    }
  }

  async function onIngest() {
    const paths = Array.from(selected)
    if (paths.length === 0) return
    setIngesting(true)
    setSummary(null)
    setFailedPaths([])
    setProgress([])
    try {
      await ingestClient.ingestPaths(paths)
      toast({
        title: 'Ingest started',
        description: `Indexing ${paths.length} selected file(s). Progress updates below.`,
      })
    } catch (e) {
      setIngesting(false)
      toast({
        title: 'Ingest failed',
        description: (e as Error).message,
        tone: 'error',
      })
    }
  }

  async function onStop() {
    try {
      await ingestClient.cancel()
      toast({ title: 'Cancel requested', description: 'Ingest will stop after the current file.' })
    } catch (e) {
      toast({
        title: 'Cancel failed',
        description: (e as Error).message,
        tone: 'error',
      })
    }
  }

  function onToggleNode(node: ScanTreeNode) {
    setSelected((prev) => toggleNodeSelection(node, prev))
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-md font-semibold text-foreground">Scan vault</h3>
        {vaultFolder ? (
          <p className="mt-2 text-sm text-foreground">
            <span className="text-muted-foreground">Vault folder: </span>
            <code className="break-all rounded bg-secondary px-1.5 py-0.5 text-sm">{vaultFolder}</code>
          </p>
        ) : null}
        <p className="mt-2 text-sm text-muted-foreground">
          Scan finds new and changed files under{' '}
          <code className="rounded bg-secondary px-1">raw/</code> and{' '}
          <code className="rounded bg-secondary px-1">wiki/</code>. Select what to index, then click
          Ingest. Unchanged files are skipped via the content-hash manifest.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" disabled={busy} onClick={() => void onScan()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {scanning ? 'Scanning…' : 'Scan'}
          </Button>
          <Button
            type="button"
            disabled={busy || selectedCount === 0}
            onClick={() => void onIngest()}
          >
            <Play className="mr-2 h-4 w-4" />
            {ingesting ? 'Ingesting…' : 'Ingest'}
          </Button>
          {ingesting ? (
            <Button type="button" variant="outline" onClick={() => void onStop()}>
              <Square className="mr-2 h-4 w-4" />
              Stop
            </Button>
          ) : null}
        </div>
      </section>

      {previewSummary || files.length > 0 ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-md font-semibold text-foreground">Candidates</h3>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span>{selectedCount} selected</span>
              {previewSummary ? (
                <span>
                  · {previewSummary.new} new, {previewSummary.changed} changed,{' '}
                  {previewSummary.unchanged} unchanged
                </span>
              ) : null}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy || files.length === 0}
              onClick={() => setSelected(selectAllPaths(files))}
            >
              Select all
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy || selectedCount === 0}
              onClick={() => setSelected(new Set())}
            >
              Clear
            </Button>
          </div>
          {files.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              No new or changed files. Vault is up to date.
            </p>
          ) : (
            <ul className="mt-3 max-h-80 overflow-y-auto rounded-lg border border-border/60 py-1">
              {tree.map((node) => (
                <TreeCheckbox
                  key={node.id}
                  node={node}
                  selected={selected}
                  onToggle={onToggleNode}
                  depth={0}
                />
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {summary ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-md font-semibold text-foreground">Summary</h3>
          <ul className="mt-3 grid gap-2 text-sm sm:grid-cols-2 md:grid-cols-5">
            <li>
              <span className="text-muted-foreground">Total</span>
              <p className="font-medium text-foreground">{summary.total}</p>
            </li>
            <li>
              <span className="text-muted-foreground">Ingested</span>
              <p className="font-medium text-foreground">{summary.ingested}</p>
            </li>
            <li>
              <span className="text-muted-foreground">Skipped</span>
              <p className="font-medium text-foreground">{summary.skipped}</p>
            </li>
            <li>
              <span className="text-muted-foreground">Failed</span>
              <p className="font-medium text-foreground">{summary.failed}</p>
            </li>
            <li>
              <span className="text-muted-foreground">Cancelled</span>
              <p className="font-medium text-foreground">{summary.cancelled}</p>
            </li>
          </ul>
          {failedPaths.length > 0 ? (
            <div className="mt-4">
              <p className="text-sm font-medium text-foreground">Failed files</p>
              <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                {failedPaths.map((f) => (
                  <li key={f.path} className="truncate">
                    {f.path}: {f.error}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-md font-semibold text-foreground">Progress</h3>
        {progress.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Waiting for ingest activity…</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {progress.map((row) => (
              <li
                key={row.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-border/60 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">{row.label}</p>
                  {row.detail ? (
                    <p className="text-xs text-muted-foreground">
                      {formatIngestProgressLine({
                        relative_path: row.label,
                        message: row.detail,
                        phase: 'file',
                      })}
                    </p>
                  ) : null}
                </div>
                <span
                  className={
                    row.status === 'ok'
                      ? 'shrink-0 text-sm text-emerald-500'
                      : row.status === 'error'
                        ? 'shrink-0 text-sm text-destructive'
                        : 'shrink-0 text-sm text-foreground'
                  }
                >
                  {row.status === 'ok' ? 'Done' : row.status === 'error' ? 'Error' : 'Running'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
