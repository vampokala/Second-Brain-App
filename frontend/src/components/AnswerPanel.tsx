import type { QueryResponseModel } from '../api/generated'

export function AnswerPanel({
  answer,
  response,
  isLoading,
}: {
  answer: string
  response: QueryResponseModel | null
  isLoading: boolean
}) {
  const truthfulness = response?.truthfulness
  return (
    <section className="app-card p-5" aria-live="polite">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-950">Answer</h2>
        {truthfulness ? (
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
            Truthfulness {truthfulness.score.toFixed(2)}
          </span>
        ) : null}
      </div>
      <div className="min-h-28 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-left text-slate-800">
        {answer || (isLoading ? 'Waiting for tokens...' : 'Ask a question to see a grounded answer.')}
      </div>
      {response ? (
        <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-600">
          <span>{response.provider} / {response.model}</span>
          <span>{Math.round(response.processing_time_ms)} ms</span>
          {response.cached ? <span>Cached</span> : null}
        </div>
      ) : null}
    </section>
  )
}
