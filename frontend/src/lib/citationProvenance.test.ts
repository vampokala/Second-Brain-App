import { citationLabel } from './citationProvenance'

describe('citationLabel', () => {
  it('labels citations matching uploaded files as yours', () => {
    expect(
      citationLabel(
        { title: 'uploaded-doc.md', source: '/tmp/doc-ingest-sessions/abc/uploads/uploaded-doc.md' },
        [{ name: 'uploaded-doc.md', size_bytes: 12 }],
      ),
    ).toBe('yours')
  })

  it('labels unmatched citations as global', () => {
    expect(citationLabel({ title: 'README.md', source: 'data/documents/README.md' }, [])).toBe('global')
  })
})
