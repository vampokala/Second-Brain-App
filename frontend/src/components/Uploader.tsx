import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { uploadDocuments, type SessionSummary, type UploadResult } from '../api/client'
import { formatBytes } from '../lib/format'
import { Button } from './ui/button'

const ACCEPTED = '.pdf,.docx,.txt,.md,.html'
const MAX_FILE_BYTES = 3 * 1024 * 1024

function resultMessage(result: UploadResult) {
  const messages: Record<string, string> = {
    queued: 'Uploaded and indexed.',
    skipped: 'Duplicate upload skipped.',
    oversize: 'File exceeds the 3 MB limit.',
    file_count_cap: 'Session file count cap reached.',
    session_disk_cap: 'Session disk cap reached.',
    type_mismatch: 'File contents do not match the extension.',
  }
  return messages[result.status] ?? messages[result.message] ?? result.message
}

export function Uploader({
  sessionId,
  summary,
  onUploaded,
}: {
  sessionId: string
  summary: SessionSummary | undefined
  onUploaded: () => Promise<unknown>
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [message, setMessage] = useState('')
  const [results, setResults] = useState<UploadResult[]>([])

  const mutation = useMutation({
    mutationFn: (files: File[]) => uploadDocuments(sessionId, files),
    onSuccess: async (response) => {
      setResults(response.results)
      setMessage('Upload finished.')
      await onUploaded()
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : 'Upload failed.')
    },
  })

  const upload = (fileList: FileList | File[]) => {
    if (!summary) {
      return
    }
    const files = Array.from(fileList)
    const maxFiles = summary?.max_files ?? 3
    const currentFiles = summary?.files.length ?? 0
    if (currentFiles + files.length > maxFiles) {
      setMessage(`You can upload ${Math.max(0, maxFiles - currentFiles)} more file(s).`)
      return
    }
    const oversized = files.find((file) => file.size > MAX_FILE_BYTES)
    if (oversized) {
      setMessage(`${oversized.name} is larger than ${formatBytes(MAX_FILE_BYTES)}.`)
      return
    }
    mutation.mutate(files)
  }

  return (
    <div>
      <div
        className="rounded-2xl border-2 border-dashed border-input bg-muted p-8 text-center"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault()
          upload(event.dataTransfer.files)
        }}
      >
        <Upload className="mx-auto mb-3 h-8 w-8 text-primary" aria-hidden="true" />
        <p className="font-medium text-foreground">Drop files here or choose files</p>
        <p className="mt-1 text-sm text-muted-foreground">PDF, DOCX, TXT, Markdown, or HTML.</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          multiple
          className="sr-only"
          onChange={(event) => event.target.files && upload(event.target.files)}
        />
        <Button
          type="button"
          className="mt-4"
          disabled={mutation.isPending || !summary}
          onClick={() => inputRef.current?.click()}
        >
          {mutation.isPending ? 'Uploading...' : 'Choose files'}
        </Button>
      </div>
      {message ? <p className="mt-3 text-sm text-foreground" aria-live="polite">{message}</p> : null}
      {results.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {results.map((result) => (
            <li key={`${result.filename}-${result.status}`} className="rounded-lg bg-muted p-3 text-sm">
              <span className="font-medium text-foreground">{result.filename}</span>: {resultMessage(result)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
