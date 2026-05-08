import { describe, expect, it } from 'vitest'

import { vaultPathQuery } from './vaultDeepLink'

describe('vaultDeepLink', () => {
  it('encodes path for hash', () => {
    expect(vaultPathQuery('raw/a/b.md')).toContain('raw%2Fa%2Fb.md')
  })
})
