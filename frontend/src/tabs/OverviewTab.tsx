import { ExternalLink } from 'lucide-react'

import { Button } from '../components/ui/button'

export function OverviewTab() {
  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-card p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Help</p>
        <h2 className="mt-1 text-xl font-semibold text-foreground">Demo script</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Walk through Ask → citations → vault → ingest in under a minute. Keep this open as a
          cheat sheet during the demo.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-base font-semibold text-foreground">Observability</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Open the Langfuse dashboard to inspect traces, retrieval hits, and generation quality during
          the demo.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          asChild
        >
          <a href="/observability/dashboard" target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-3.5 w-3.5" />
            Open observability dashboard
          </a>
        </Button>
      </section>

      <DemoCard
        step="1"
        title="Ask a seeded question"
        body="Open Ask. A chat is ready with three starter questions. Pick one or type your own — Enter sends, Shift+Enter adds a newline."
      />
      <DemoCard
        step="2"
        title="Watch retrieval, then Sources"
        body='While answering you will see “Searching knowledge…”. Open Sources for titles, previews, scores, and jump into the vault file.'
      />
      <DemoCard
        step="3"
        title="Choose scope"
        body="Use the Vault / Global pills in the Ask header. Vault searches your indexed knowledge base; Global uses the shared demo corpus."
      />
      <DemoCard
        step="4"
        title="Add knowledge"
        body="Knowledge → Add: drop files or paste text. Progress rows show human status; raw event JSON lives under Advanced. In demo mode, session uploads use the scope toggle (global / my uploads / both)."
      />
      <DemoCard
        step="5"
        title="Browse & ask about a file"
        body='Knowledge → Browse: open a file, then “Ask about this file” to jump back to Ask with a ready prompt. Connectors: Sync now, then “Ask about synced items”.'
      />
      <DemoCard
        step="6"
        title="Sync a public GitHub repo"
        body="Knowledge → Connectors: add a public repo (no token required for demo), run Sync now, then Ask about the synced README or issues."
      />

      <section className="rounded-xl border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">Session uploads (demo)</p>
        <p className="mt-1">
          Browser-session files stay private, expire after inactivity, and are not merged into the
          shared vault. They are separate from vault ingest under Knowledge → Add.
        </p>
      </section>
    </div>
  )
}

function DemoCard({ step, title, body }: { step: string; title: string; body: string }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start gap-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
          {step}
        </span>
        <div>
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{body}</p>
        </div>
      </div>
    </section>
  )
}
