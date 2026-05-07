import { testInternals } from './streamQuery'

describe('streamQuery parsing', () => {
  it('parses token and final events', () => {
    expect(
      testInternals.parseSseFrame(
        'data: {"type":"token","text":"Hi"}\n\ndata: {"type":"final","citations":[],"retrieved":[],"truthfulness":null,"provider":"ollama","model":"llama3"}',
      ),
    ).toEqual([
      { type: 'token', text: 'Hi' },
      {
        type: 'final',
        citations: [],
        retrieved: [],
        truthfulness: null,
        provider: 'ollama',
        model: 'llama3',
      },
    ])
  })
})
