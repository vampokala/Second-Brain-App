import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link2, Upload } from 'lucide-react'

import { fetchLlmConfig, resolveApiBaseUrl } from '../api/client'
import { ingestClient } from '../api/ingestClient'
import { ScopeToggle } from '../components/ScopeToggle'
import { Uploader } from '../components/Uploader'
import { useToast } from '../components/toast/ToastProvider'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { ingestEventsSource } from '../lib/sseClient'
import {
  formatIngestProgressLine,
  normalizeIngestProgress,
  progressRowFromPayload,
  type ProgressRow,
} from '../lib/ingestProgress'
import { useSession } from '../session/SessionContext'
import type { KnowledgeScope } from '../api/generated'

type Mode = 'file' | 'text' | 'url'

export function IngestTab() {
  const { toast } = useToast()
  const session = useSession()
  const [mode, setMode] = useState<Mode>('file')
  const [rawLog, setRawLog] = useState<string[]>([])
  const [progress, setProgress] = useState<ProgressRow[]>([])
  const [busy, setBusy] = useState(false)
  const [textBody, setTextBody] = useState('')
  const [textPath, setTextPath] = useState('raw/pasted/note.md')
  const [url, setUrl] = useState('https://')
  const [urlPath, setUrlPath] = useState('')
  const [sessionScope, setSessionScope] = useState<KnowledgeScope>('global')
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: llmConfig } = useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLlmConfig,
    staleTime: Infinity,
  })
  const { data: capabilities } = useQuery({
    queryKey: ['ingest-capabilities'],
    queryFn: () => ingestClient.capabilities(),
    staleTime: 60_000,
  })
  const isDemo = !!llmConfig?.demo_mode

  useEffect(() => {
    const { close } = ingestEventsSource((p) => {
      const payload = p as Record<string, unknown>
      const line = `${new Date().toISOString().slice(11, 19)} ${JSON.stringify(p)}`
      setRawLog((prev) => [line, ...prev].slice(0, 80))
      const normalized = normalizeIngestProgress(payload)
      const formatted = formatIngestProgressLine(normalized)
      const row = progressRowFromPayload(payload)
      if (row) {
        setProgress((prev) => [{ ...row, detail: formatted || row.detail }, ...prev].slice(0, 40))
      }
    })
    return close
  }, [])

  const apiRoot = resolveApiBaseUrl()

  async function postJson(path: string, body: object) {
    const u = apiRoot ? `${apiRoot}${path}` : path
    const res = await fetch(u, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const raw = await res.text()
      let detail = raw
      try {
        const parsed = JSON.parse(raw) as { detail?: unknown }
        if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
          detail = parsed.detail
        }
      } catch {
        // keep raw body when response is not JSON
      }
      throw new Error(detail || `Request failed (${res.status})`)
    }
    return res.json()
  }

  async function uploadFiles(files: FileList | File[]) {
    const list = Array.from(files)
    if (!list.length) return
    setBusy(true)
    setProgress((prev) => [
      { id: `up-${Date.now()}`, label: `Uploading ${list.length} file(s)`, status: 'running' },
      ...prev,
    ])
    try {
      const fd = new FormData()
      for (const f of list) fd.append('files', f)
      const u = apiRoot ? `${apiRoot}/ingest` : '/ingest'
      const res = await fetch(u, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(await res.text())
      await res.json()
      setProgress((prev) => [
        {
          id: `ok-${Date.now()}`,
          label: `${list.length} file(s) ingested`,
          status: 'ok',
        },
        ...prev,
      ])
      toast({ title: 'Files ingested', tone: 'success' })
      if (fileRef.current) fileRef.current.value = ''
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setProgress((prev) => [
        { id: `err-${Date.now()}`, label: 'Upload failed', status: 'error', detail: msg },
        ...prev,
      ])
      toast({ title: 'Ingest failed', description: msg, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  async function onPasteIngest() {
    setBusy(true)
    try {
      await postJson('/ingest/text', { text: textBody, relpath: textPath })
      setProgress((prev) => [
        { id: `text-${Date.now()}`, label: textPath, status: 'ok', detail: 'Text written & ingested' },
        ...prev,
      ])
      toast({ title: 'Text ingested', tone: 'success' })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast({ title: 'Text ingest failed', description: msg, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  async function onUrlIngest() {
    setBusy(true)
    try {
      const body: { url: string; relpath?: string } = { url }
      if (urlPath.trim()) body.relpath = urlPath.trim()
      await postJson('/ingest/url', body)
      setProgress((prev) => [
        { id: `url-${Date.now()}`, label: url, status: 'ok', detail: 'URL fetched & ingested' },
        ...prev,
      ])
      toast({ title: 'URL ingested', tone: 'success' })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast({ title: 'URL ingest failed', description: msg, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Add to vault</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Drop files, paste text, or fetch a URL. Progress appears below as each step finishes.
        </p>
        {capabilities ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {capabilities.default_provider && capabilities.default_model
              ? `${capabilities.default_provider} · ${capabilities.default_model} · `
              : null}
            Supported: {capabilities.supported_extensions.slice(0, 12).join(', ')}
            {capabilities.supported_extensions.length > 12 ? ', …' : ''}
            {capabilities.vision_enabled ? ' · vision on' : ''}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {(
            [
              ['file', 'Files'],
              ['text', 'Text'],
              ['url', 'URL'],
            ] as const
          ).map(([k, label]) => (
            <Button
              key={k}
              type="button"
              variant={mode === k ? 'default' : 'secondary'}
              size="sm"
              onClick={() => setMode(k)}
            >
              {label}
            </Button>
          ))}
          {busy ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                void ingestClient.cancel().then(() => {
                  toast({ title: 'Cancel requested', tone: 'success' })
                })
              }}
            >
              Stop
            </Button>
          ) : null}
        </div>
      </section>

      {mode === 'file' ? (
        <section className="rounded-xl border border-border bg-card p-5">
          <h3 className="flex items-center gap-2 text-md font-semibold text-foreground">
            <Upload className="h-4 w-4" aria-hidden="true" />
            Upload files
          </h3>
          <div
            className={`mt-3 rounded-2xl border-2 border-dashed p-8 text-center transition ${
              dragOver ? 'border-primary bg-primary/5' : 'border-input bg-muted/40'
            }`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              void uploadFiles(e.dataTransfer.files)
            }}
          >
            <p className="font-medium text-foreground">Drop files here or choose files</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {capabilities
                ? `Includes ${capabilities.supported_extensions.slice(0, 8).join(', ')}${
                    capabilities.supported_extensions.length > 8 ? ', …' : ''
                  }`
                : 'PDF, DOCX, spreadsheets, slides, notebooks, code, and more'}
            </p>
            <input
              ref={fileRef}
              type="file"
              multiple
              className="sr-only"
              onChange={(e) => e.target.files && void uploadFiles(e.target.files)}
            />
            <Button
              className="mt-4"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              {busy ? 'Working…' : 'Choose files'}
            </Button>
          </div>
        </section>
      ) : null}

      {mode === 'text' ? (
        <section className="space-y-3 rounded-xl border border-border bg-card p-5">
          <h3 className="text-md font-semibold text-foreground">Paste markdown / text</h3>
          <label className="block text-xs font-medium text-muted-foreground">Path under vault</label>
          <Input value={textPath} onChange={(e) => setTextPath(e.target.value)} />
          <textarea
            className="min-h-[200px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            value={textBody}
            onChange={(e) => setTextBody(e.target.value)}
            placeholder="Content to write and ingest…"
          />
          <Button disabled={busy || !textBody.trim()} onClick={() => void onPasteIngest()}>
            {busy ? 'Working…' : 'Write & ingest'}
          </Button>
        </section>
      ) : null}

      {mode === 'url' ? (
        <section className="space-y-3 rounded-xl border border-border bg-card p-5">
          <h3 className="flex items-center gap-2 text-md font-semibold text-foreground">
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Fetch URL
          </h3>
          <Input value={url} onChange={(e) => setUrl(e.target.value)} />
          <label className="block text-xs font-medium text-muted-foreground">
            Optional path (default auto)
          </label>
          <Input
            value={urlPath}
            onChange={(e) => setUrlPath(e.target.value)}
            placeholder="raw/imports/custom.md"
          />
          <Button disabled={busy || !url.trim()} onClick={() => void onUrlIngest()}>
            {busy ? 'Working…' : 'Fetch & ingest'}
          </Button>
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
                className="flex items-start justify-between gap-3 rounded-lg bg-muted/50 px-3 py-2 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">{row.label}</p>
                  {row.detail ? (
                    <p className="text-xs text-muted-foreground">{row.detail}</p>
                  ) : null}
                </div>
                <span
                  className={
                    row.status === 'ok'
                      ? 'text-xs font-semibold text-success'
                      : row.status === 'error'
                        ? 'text-xs font-semibold text-destructive'
                        : 'text-xs font-semibold text-muted-foreground'
                  }
                >
                  {row.status === 'ok' ? 'Done' : row.status === 'error' ? 'Error' : 'Running'}
                </span>
              </li>
            ))}
          </ul>
        )}
        <details className="mt-4">
          <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
            Advanced · raw events
          </summary>
          <pre className="mt-2 max-h-60 overflow-auto rounded-lg bg-secondary p-3 text-xs text-foreground">
            {rawLog.length ? rawLog.join('\n') : 'No raw events yet.'}
          </pre>
        </details>
      </section>

      {isDemo && session.sessionId ? (
        <section className="space-y-4 rounded-xl border border-border bg-card p-5">
          <div>
            <h3 className="text-md font-semibold text-foreground">Session uploads (demo)</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Private to this browser session. Not added to the shared vault.
            </p>
          </div>
          <ScopeToggle
            value={sessionScope}
            onChange={setSessionScope}
            hasUploads={session.hasUploads}
          />
          <Uploader
            sessionId={session.sessionId}
            summary={session.summary}
            onUploaded={async () => {
              await session.refreshSession()
              toast({ title: 'Session upload complete', tone: 'success' })
            }}
          />
        </section>
      ) : null}
    </div>
  )
}
