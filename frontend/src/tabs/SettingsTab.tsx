import { useEffect, useState } from 'react'

export function SettingsTab() {
  const [data, setData] = useState<{ values: Record<string, unknown>; env_override_keys: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      const res = await fetch('/settings')
      if (!res.ok) throw new Error(await res.text())
      setData(await res.json())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function savePatch(patch: Record<string, unknown>) {
    setBusy(true)
    try {
      const res = await fetch('/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patch }),
      })
      if (!res.ok) throw new Error(await res.text())
      setData(await res.json())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-card space-y-6 p-5">
      <h2 className="text-lg font-bold">Settings</h2>
      {error ? <div className="rounded-lg bg-amber-50 p-3 text-sm">{error}</div> : null}
      <section className="space-y-2">
        <h3 className="font-semibold text-slate-800">Providers</h3>
        <p className="text-sm text-slate-600">Keys are stored in Postgres unless overridden by env.</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            disabled={busy}
            onClick={() => void savePatch({ openai_api_key: { secret: '' } })}
          >
            Placeholder save
          </button>
          <button
            type="button"
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white"
            disabled={busy}
            onClick={() => void savePatch({})}
          >
            Reload
          </button>
        </div>
      </section>
      <section>
        <h3 className="mb-2 font-semibold text-slate-800">Current values (masked)</h3>
        <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
          {data ? JSON.stringify(data.values, null, 2) : 'Loading…'}
        </pre>
        {data?.env_override_keys?.length ? (
          <p className="mt-2 text-xs text-slate-500">Env overrides: {data.env_override_keys.join(', ')}</p>
        ) : null}
      </section>
    </div>
  )
}
