export type ScanTreeNode = {
  id: string
  name: string
  kind: 'dir' | 'file'
  change?: 'new' | 'changed'
  children: ScanTreeNode[]
}

export type CheckState = 'checked' | 'unchecked' | 'indeterminate'

/** Collect all descendant file paths under a node. */
export function collectFilePaths(node: ScanTreeNode): string[] {
  if (node.kind === 'file') return [node.id]
  return node.children.flatMap(collectFilePaths)
}

/** Build a nested directory tree from vault-relative file paths. */
export function buildScanTree(
  files: Array<{ path: string; change: 'new' | 'changed' }>,
): ScanTreeNode[] {
  const root: ScanTreeNode = { id: '', name: '', kind: 'dir', children: [] }

  for (const file of files) {
    const parts = file.path.replace(/\\/g, '/').split('/').filter(Boolean)
    if (parts.length === 0) continue
    let cursor = root
    let prefix = ''
    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i]
      const isLeaf = i === parts.length - 1
      prefix = prefix ? `${prefix}/${part}` : part
      let child = cursor.children.find((c) => c.name === part)
      if (!child) {
        child = {
          id: prefix,
          name: part,
          kind: isLeaf ? 'file' : 'dir',
          change: isLeaf ? file.change : undefined,
          children: [],
        }
        cursor.children.push(child)
      } else if (isLeaf) {
        child.kind = 'file'
        child.change = file.change
      }
      cursor = child
    }
  }

  sortTree(root)
  return root.children
}

function sortTree(node: ScanTreeNode): void {
  node.children.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'dir' ? -1 : 1
    return a.name.localeCompare(b.name)
  })
  for (const child of node.children) {
    if (child.kind === 'dir') sortTree(child)
  }
}

export function checkStateForNode(node: ScanTreeNode, selected: Set<string>): CheckState {
  const paths = collectFilePaths(node)
  if (paths.length === 0) return 'unchecked'
  let checked = 0
  for (const p of paths) {
    if (selected.has(p)) checked += 1
  }
  if (checked === 0) return 'unchecked'
  if (checked === paths.length) return 'checked'
  return 'indeterminate'
}

/** Toggle a node: dirs select/deselect all descendant files. */
export function toggleNodeSelection(
  node: ScanTreeNode,
  selected: Set<string>,
): Set<string> {
  const paths = collectFilePaths(node)
  const next = new Set(selected)
  const state = checkStateForNode(node, selected)
  if (state === 'checked') {
    for (const p of paths) next.delete(p)
  } else {
    for (const p of paths) next.add(p)
  }
  return next
}

export function selectAllPaths(files: Array<{ path: string }>): Set<string> {
  return new Set(files.map((f) => f.path))
}
