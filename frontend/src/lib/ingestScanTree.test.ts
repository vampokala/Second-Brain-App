import { describe, expect, it } from 'vitest'

import {
  buildScanTree,
  checkStateForNode,
  collectFilePaths,
  selectAllPaths,
  toggleNodeSelection,
} from './ingestScanTree'

describe('ingestScanTree', () => {
  const files = [
    { path: 'raw/notes/a.md', change: 'new' as const },
    { path: 'raw/notes/b.md', change: 'changed' as const },
    { path: 'raw/other.md', change: 'new' as const },
  ]

  it('builds nested directory tree with dirs before files', () => {
    const tree = buildScanTree(files)
    expect(tree).toHaveLength(1)
    expect(tree[0].name).toBe('raw')
    expect(tree[0].kind).toBe('dir')
    const children = tree[0].children
    expect(children[0].name).toBe('notes')
    expect(children[0].kind).toBe('dir')
    expect(children[1].name).toBe('other.md')
    expect(children[1].kind).toBe('file')
  })

  it('collects descendant file paths under a directory', () => {
    const tree = buildScanTree(files)
    const notes = tree[0].children.find((c) => c.name === 'notes')!
    expect(collectFilePaths(notes).sort()).toEqual(['raw/notes/a.md', 'raw/notes/b.md'])
  })

  it('toggles directory selection for all children', () => {
    const tree = buildScanTree(files)
    const notes = tree[0].children.find((c) => c.name === 'notes')!
    let selected = new Set<string>()
    selected = toggleNodeSelection(notes, selected)
    expect(checkStateForNode(notes, selected)).toBe('checked')
    expect(selected.has('raw/notes/a.md')).toBe(true)
    expect(selected.has('raw/notes/b.md')).toBe(true)

    selected = toggleNodeSelection(notes, selected)
    expect(checkStateForNode(notes, selected)).toBe('unchecked')
  })

  it('reports indeterminate when some children selected', () => {
    const tree = buildScanTree(files)
    const notes = tree[0].children.find((c) => c.name === 'notes')!
    const selected = new Set(['raw/notes/a.md'])
    expect(checkStateForNode(notes, selected)).toBe('indeterminate')
  })

  it('selectAllPaths returns every file path', () => {
    expect(selectAllPaths(files).size).toBe(3)
  })
})
