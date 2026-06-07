const prompts = [
  'What is retrieval augmented generation?',
  'How does hybrid retrieval improve document search?',
  'Explain BM25 vs vector search.',
  'What makes citations useful in a RAG system?',
]

export function SamplePromptChips({ onSelect }: { onSelect: (prompt: string) => void }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-foreground">Try a sample</p>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="rounded-full border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm hover:border-primary hover:text-primary"
            onClick={() => onSelect(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  )
}
