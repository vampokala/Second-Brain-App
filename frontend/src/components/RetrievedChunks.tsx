import type { RetrievedChunkModel } from '../api/generated'

export function RetrievedChunks({ chunks }: { chunks: RetrievedChunkModel[] }) {
  return (
    <details className="app-card p-5">
      <summary className="cursor-pointer text-lg font-semibold text-slate-950">
        Retrieved chunks ({chunks.length})
      </summary>
      {chunks.length === 0 ? (
        <p className="mt-3 text-sm text-slate-600">No retrieved chunks returned yet.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {chunks.map((chunk) => (
            <li key={chunk.id} className="rounded-xl bg-slate-50 p-3 text-left">
              <div className="flex flex-wrap justify-between gap-2 text-sm">
                <span className="font-medium text-slate-900">{chunk.id}</span>
                <span className="text-slate-600">score {chunk.score.toFixed(3)}</span>
              </div>
              <p className="mt-2 text-sm text-slate-700">{chunk.preview}</p>
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}
