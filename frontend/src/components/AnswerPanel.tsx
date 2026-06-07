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
        <h2 className="text-lg font-semibold text-foreground">Answer</h2>
        {truthfulness ? (
          <span className="rounded-full bg-success/10 px-3 py-1 text-sm font-medium text-success">
            Truthfulness {truthfulness.score.toFixed(2)}
          </span>
        ) : null}
      </div>
      <div className="min-h-28 whitespace-pre-wrap rounded-xl bg-muted p-4 text-left text-foreground">
        {answer || (isLoading ? 'Waiting for tokens...' : 'Ask a question to see a grounded answer.')}
      </div>
      {response ? (
        <div className="mt-3 flex flex-wrap gap-3 text-sm text-muted-foreground">
          <span>{response.provider} / {response.model}</span>
          <span>{Math.round(response.processing_time_ms)} ms</span>
          {response.cached ? <span>Cached</span> : null}
        </div>
      ) : null}
    </section>
  )
}
