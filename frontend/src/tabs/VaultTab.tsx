import { useCallback, useEffect, useMemo, useState } from 'react'
import { Tree } from 'react-arborist'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { parseVaultPathFromHash } from '../lib/vaultDeepLink'

type FileNode = {
  id: string
  name: string
  path: string
  kind: 'file' | 'dir'
  children?: FileNode[]
}

type FileTree = { prefix: string; nodes: FileNode[] }

type ArborNode = { id: string; name: string; children?: ArborNode[] }

function toArborist(nodes: FileNode[]): ArborNode[] {
  return nodes.map((n) => ({
    id: n.path,
    name: n.name,
    children: n.children?.length ? toArborist(n.children) : undefined,
  }))
}

export function VaultTab() {
  const [tree, setTree] = useState<FileTree | null>(null)
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState<{ body: string; frontmatter: Record<string, unknown> | null } | null>(null)
  const [fmOpen, setFmOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTree = useCallback(async () => {
    try {
      const q = filter.trim() ? `&filter=${encodeURIComponent(filter)}` : ''
      const res = await fetch(`/vault/files?prefix=raw/&depth=8${q}`)
      if (!res.ok) throw new Error(await res.text())
      setTree(await res.json())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [filter])

  useEffect(() => {
    const t = setTimeout(() => void loadTree(), 300)
    return () => clearTimeout(t)
  }, [filter, loadTree])

  useEffect(() => {
    const p = parseVaultPathFromHash()
    if (p) setSelected(p)
  }, [])

  useEffect(() => {
    if (!selected) {
      setContent(null)
      return
    }
    void (async () => {
      try {
        const res = await fetch(`/vault/files/${encodeURI(selected)}`)
        if (!res.ok) throw new Error(await res.text())
        const j = await res.json()
        setContent({ body: j.body || '', frontmatter: j.frontmatter || null })
      } catch (e) {
        setError((e as Error).message)
      }
    })()
  }, [selected])

  const arborData = useMemo(() => toArborist(tree?.nodes || []), [tree])

  return (
    <div className="app-card grid min-h-[28rem] grid-cols-1 gap-4 p-5 md:grid-cols-12">
      <div className="md:col-span-4">
        <h2 className="mb-3 text-lg font-bold">Vault</h2>
        <input
          className="mb-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Filter paths…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {error ? <div className="text-sm text-red-600">{error}</div> : null}
        <div className="h-80 overflow-hidden rounded-lg border border-slate-200">
          {arborData.length ? (
            <Tree
              data={arborData}
              width={340}
              height={320}
              indent={16}
              onSelect={(nodes) => {
                const n = nodes[0]
                if (n?.data.id) setSelected(String(n.data.id))
              }}
            >
              {({ node, style, dragHandle }) => (
                <div style={style} ref={dragHandle} className="cursor-pointer text-sm">
                  {node.data.name}
                </div>
              )}
            </Tree>
          ) : (
            <div className="p-4 text-sm text-slate-500">No files (configure DATABASE_URL + vault).</div>
          )}
        </div>
      </div>
      <div className="md:col-span-8">
        <div className="mb-2 text-sm font-medium text-slate-600">{selected || 'Select a file'}</div>
        {content?.frontmatter ? (
          <div className="mb-2">
            <button type="button" className="text-xs font-semibold text-blue-600" onClick={() => setFmOpen(!fmOpen)}>
              {fmOpen ? 'Hide' : 'Show'} frontmatter
            </button>
            {fmOpen ? (
              <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">
                {JSON.stringify(content.frontmatter, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}
        <div className="rounded-lg border border-slate-100 bg-white p-4 text-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content?.body || '_No file selected_'}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
