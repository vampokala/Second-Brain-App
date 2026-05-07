import * as Progress from '@radix-ui/react-progress'
import { RotateCcw } from 'lucide-react'
import { Uploader } from '../components/Uploader'
import { formatBytes, formatTtl } from '../lib/format'
import { useSession } from '../session/SessionContext'

export function DocumentsTab() {
  const { sessionId, summary, expiresAt, refreshSession, clearSession, isMintingSession } = useSession()
  const usedBytes = summary?.total_bytes ?? 0
  const maxBytes = summary?.max_session_bytes ?? 8 * 1024 * 1024
  const files = summary?.files ?? []
  const maxFiles = summary?.max_files ?? 3
  const bytePercent = Math.min(100, (usedBytes / maxBytes) * 100)
  const filePercent = Math.min(100, (files.length / maxFiles) * 100)

  return (
    <div className="space-y-5">
      <section className="app-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">My documents</h2>
            <p className="mt-1 text-sm text-slate-600">
              Up to 3 files, 3 MB each, 8 MB total. Sessions expire after 30 minutes of inactivity.
            </p>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
            disabled={!sessionId || isMintingSession}
            onClick={() => void clearSession()}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Clear my session
          </button>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div>
            <div className="mb-2 flex justify-between text-sm">
              <span>Disk used</span>
              <span>{formatBytes(usedBytes)} / {formatBytes(maxBytes)}</span>
            </div>
            <Progress.Root className="h-2 overflow-hidden rounded-full bg-slate-100" value={bytePercent}>
              <Progress.Indicator className="h-full bg-blue-600" style={{ width: `${bytePercent}%` }} />
            </Progress.Root>
          </div>
          <div>
            <div className="mb-2 flex justify-between text-sm">
              <span>Files</span>
              <span>{files.length} / {maxFiles}</span>
            </div>
            <Progress.Root className="h-2 overflow-hidden rounded-full bg-slate-100" value={filePercent}>
              <Progress.Indicator className="h-full bg-emerald-600" style={{ width: `${filePercent}%` }} />
            </Progress.Root>
          </div>
        </div>
        <p className="mt-4 text-sm text-slate-600">Session expires in {formatTtl(expiresAt)}.</p>
      </section>

      {sessionId ? (
        <section className="app-card p-5">
          <Uploader sessionId={sessionId} summary={summary} onUploaded={refreshSession} />
        </section>
      ) : null}

      <section className="app-card p-5">
        <h2 className="mb-3 text-lg font-semibold text-slate-950">Indexed files</h2>
        {files.length === 0 ? (
          <p className="text-sm text-slate-600">No uploaded documents yet.</p>
        ) : (
          <ul className="space-y-2">
            {files.map((file) => (
              <li key={file.name} className="flex justify-between rounded-lg bg-slate-50 p-3 text-sm">
                <span className="font-medium text-slate-900">{file.name}</span>
                <span className="text-slate-600">{formatBytes(file.size_bytes)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
