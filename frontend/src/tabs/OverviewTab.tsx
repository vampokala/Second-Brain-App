export function OverviewTab() {
  return (
    <div className="space-y-5">
      <section className="app-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Overview</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Doc Ingestion answers questions using retrieved document chunks, optional citations in the answer,
          and quality signals so you can judge how grounded a reply is. Use this page as a quick reference
          for scopes, citations, truthfulness, and retrieval scores.
        </p>
      </section>

      <section className="app-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Knowledge scope</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          On the Query tab, choose where the system searches before the model answers. Uploads require an
          active session with at least one file.
        </p>
        <dl className="mt-4 space-y-4 text-sm">
          <div>
            <dt className="font-semibold text-foreground">Global sample corpus</dt>
            <dd className="mt-1 text-muted-foreground">
              Search the preloaded public demo documents only. Always available.
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-foreground">My uploads only</dt>
            <dd className="mt-1 text-muted-foreground">
              Search only files you uploaded in this browser session. Enabled after you upload at least one
              document.
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-foreground">Both</dt>
            <dd className="mt-1 text-muted-foreground">
              Combine the global demo corpus with your session uploads so answers can draw from either
              source.
            </dd>
          </div>
        </dl>
        <p className="mt-4 rounded-lg border border-border bg-muted p-3 text-sm text-muted-foreground">
          Session uploads are private to your session, expire after inactivity, and are not merged into the
          shared global corpus.
        </p>
      </section>

      <section className="app-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Citations</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted-foreground">
          <li>
            The model is steered to ground answers in retrieved text and to mark supporting passages with
            citation markers (for example references to documents or chunks).
          </li>
          <li>
            In the Citations panel, each entry may show a <span className="font-medium text-foreground">global</span>{' '}
            or <span className="font-medium text-foreground">yours</span> badge so you can see whether evidence
            came from the demo corpus or your uploads.
          </li>
          <li>
            <span className="font-medium text-foreground">Verification</span> summarizes how well the cited
            chunk supports the span that cited it. The <span className="font-medium text-foreground">score</span>{' '}
            (0–1) is a verification confidence for that citation; it feeds into the truthfulness score
            below.
          </li>
        </ul>
      </section>

      <section className="app-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Truthfulness</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          When present, the <span className="font-medium text-foreground">Truthfulness</span> value next to the
          answer is a single number from <strong>0</strong> to <strong>1</strong>. It blends two signals:
        </p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted-foreground">
          <li>
            <span className="font-medium text-foreground">NLI faithfulness</span> — for substantive sentences
            in the answer, the share that an entailment model judges as supported by at least one retrieved
            chunk (high entailment probability).
          </li>
          <li>
            <span className="font-medium text-foreground">Citation groundedness</span> — the average citation{' '}
            <span className="font-medium text-foreground">verification_score</span> across returned citations.
          </li>
        </ul>
        <p className="mt-3 text-sm text-muted-foreground">
          The headline score is approximately <strong>60%</strong> NLI faithfulness plus{' '}
          <strong>40%</strong> citation groundedness.
        </p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[280px] border-collapse text-left text-sm">
            <caption className="sr-only">Truthfulness score bands</caption>
            <thead>
              <tr className="border-b border-border bg-muted">
                <th className="px-3 py-2 font-semibold text-foreground">Range</th>
                <th className="px-3 py-2 font-semibold text-foreground">How to read it</th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground">
              <tr className="border-b border-border">
                <td className="px-3 py-2 font-medium text-foreground">≥ 0.80</td>
                <td className="px-3 py-2">Strong grounding: most claims align with sources and citations verify well.</td>
              </tr>
              <tr className="border-b border-border">
                <td className="px-3 py-2 font-medium text-foreground">0.50 – 0.79</td>
                <td className="px-3 py-2">Mixed: treat as helpful but verify important facts in the cited text.</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-foreground">&lt; 0.50</td>
                <td className="px-3 py-2">
                  Weak: the answer may paraphrase loosely, omit citations, or go beyond the retrieved evidence.
                  Read the retrieved chunks and citations carefully.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Truthfulness can be unavailable if scoring is disabled or errors occur; that does not imply the
          answer is ungrounded.
        </p>
      </section>

      <section className="app-card p-5">
        <h2 className="text-lg font-semibold text-foreground">Retrieved chunk scores</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Under <span className="font-medium text-foreground">Retrieved chunks</span>, each line shows a{' '}
          <span className="font-medium text-foreground">score</span> from hybrid search (BM25 plus dense
          vectors, fused with reciprocal rank fusion). These numbers are <strong>not</strong> on the same
          0–1 scale as truthfulness or citation verification.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Typical top hits often appear in roughly the <strong>0.01–0.03</strong> range depending on settings.
          Compare scores <strong>relative to other chunks in the same answer</strong> (ranking), not to a fixed
          threshold like 0.8.
        </p>
      </section>
    </div>
  )
}
