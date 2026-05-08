import { useEffect, useRef, useState } from 'react'
import { Link2, Upload } from 'lucide-react'
import { resolveApiBaseUrl } from '../api/client'
import { ingestEventsSource } from '../lib/sseClient'

type Mode = 'file' | 'text' | 'url'

export function IngestTab() {
  const [mode, setMode] = useState<Mode>('file')
  const [log, setLog] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [textBody, setTextBody] = useState('')
  const [textPath, setTextPath] = useState('raw/pasted/note.md')
  const [url, setUrl] = useState('https://')
  const [urlPath, setUrlPath] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const { close } = ingestEventsSource((p) => {
      const line = `${new Date().toISOString().slice(11, 19)} ${JSON.stringify(p)}`
      setLog((prev) => [line, ...prev].slice(0, 80))
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
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }

  async function onUploadFiles() {
    const input = fileRef.current
    if (!input?.files?.length) return
    setBusy(true)
    try {
      const fd = new FormData()
      for (const f of input.files) fd.append('files', f)
      const u = apiRoot ? `${apiRoot}/ingest` : '/ingest'
      const res = await fetch(u, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(await res.text())
      const j = await res.json()
      setLog((prev) => [`upload ok: ${JSON.stringify(j)}`, ...prev].slice(0, 80))
      input.value = ''
    } catch (e) {
      setLog((prev) => [`error: ${e instanceof Error ? e.message : String(e)}`, ...prev].slice(0, 80))
    } finally {
      setBusy(false)
    }
  }

  async function onPasteIngest() {
    setBusy(true)
    try {
      const j = await postJson('/ingest/text', { text: textBody, relpath: textPath })
      setLog((prev) => [`text ok: ${JSON.stringify(j)}`, ...prev].slice(0, 80))
    } catch (e) {
      setLog((prev) => [`error: ${e instanceof Error ? e.message : String(e)}`, ...prev].slice(0, 80))
    } finally {
      setBusy(false)
    }
  }

  async function onUrlIngest() {
    setBusy(true)
    try {
      const body: { url: string; relpath?: string } = { url }
      if (urlPath.trim()) body.relpath = urlPath.trim()
      const j = await postJson('/ingest/url', body)
      setLog((prev) => [`url ok: ${JSON.stringify(j)}`, ...prev].slice(0, 80))
    } catch (e) {
      setLog((prev) => [`error: ${e instanceof Error ? e.message : String(e)}`, ...prev].slice(0, 80))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <section className="app-card p-5">
        <h2 className="text-lg font-semibold text-slate-950">Vault ingest</h2>
        <p className="mt-2 text-sm text-slate-600">
          Requires the API with <code className="rounded bg-slate-100 px-1">DATABASE_URL</code> and pgvector.
          Events stream below from <code className="rounded bg-slate-100 px-1">/events/ingest</code>.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {(
            [
              ['file', 'Files'],
              ['text', 'Text'],
              ['url', 'URL'],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                mode === k ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'
              }`}
              onClick={() => setMode(k)}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {mode === 'file' ? (
        <section className="app-card p-5">
          <h3 className="flex items-center gap-2 text-md font-semibold text-slate-900">
            <Upload className="h-4 w-4" aria-hidden="true" />
            Upload files → raw/uploads/
          </h3>
          <input ref={fileRef} type="file" multiple className="mt-3 block text-sm" />
          <button
            type="button"
            disabled={busy}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={() => void onUploadFiles()}
          >
            {busy ? 'Working…' : 'Ingest files'}
          </button>
        </section>
      ) : null}

      {mode === 'text' ? (
        <section className="app-card space-y-3 p-5">
          <h3 className="text-md font-semibold text-slate-900">Paste markdown / text</h3>
          <label className="block text-xs font-medium text-slate-600">Relative path under vault</label>
          <input
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={textPath}
            onChange={(e) => setTextPath(e.target.value)}
          />
          <textarea
            className="min-h-[200px] w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={textBody}
            onChange={(e) => setTextBody(e.target.value)}
            placeholder="Content to write and ingest…"
          />
          <button
            type="button"
            disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={() => void onPasteIngest()}
          >
            {busy ? 'Working…' : 'Write & ingest'}
          </button>
        </section>
      ) : null}

      {mode === 'url' ? (
        <section className="app-card space-y-3 p-5">
          <h3 className="flex items-center gap-2 text-md font-semibold text-slate-900">
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Fetch URL → markdown in raw/imports/
          </h3>
          <input
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <label className="block text-xs font-medium text-slate-600">Optional relpath (default auto)</label>
          <input
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={urlPath}
            onChange={(e) => setUrlPath(e.target.value)}
            placeholder="raw/imports/custom.md"
          />
          <button
            type="button"
            disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={() => void onUrlIngest()}
          >
            {busy ? 'Working…' : 'Fetch & ingest'}
          </button>
        </section>
      ) : null}

      <section className="app-card p-5">
        <h3 className="text-md font-semibold text-slate-900">Live events</h3>
        <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
          {log.length ? log.join('\n') : 'Waiting for events…'}
        </pre>
      </section>
    </div>
  )
}
