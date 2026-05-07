const prompts = [
  'What is retrieval augmented generation?',
  'How does hybrid retrieval improve document search?',
  'Explain BM25 vs vector search.',
  'What makes citations useful in a RAG system?',
]

export function SamplePromptChips({ onSelect }: { onSelect: (prompt: string) => void }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-slate-700">Try a sample</p>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm hover:border-blue-300 hover:text-blue-700"
            onClick={() => onSelect(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  )
}
