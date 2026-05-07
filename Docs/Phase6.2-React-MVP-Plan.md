# Phase 6.2 Plan: React MVP Front-end Over Stable API

Source of truth: `Docs/Phase6-RefactorDemo_React.md` (this file is an execution slice for iterative delivery).
Depends on: `Docs/Phase6.1-Backend-Session-Isolation-Plan.md`

## Objective

Ship a usable React demo UI that consumes Phase 6.1 APIs and validates isolated user-upload experience.

## Scope

Build in top-level `frontend/`; FastAPI backend remains unchanged. No HF cutover yet; develop locally against `http://127.0.0.1:8000`.

## Stack

- Vite + React 18 + TypeScript
- Tailwind CSS + shadcn/ui
- TanStack Query
- Zustand (or Context) for session id state
- `openapi-typescript` generated API typings
- Streaming via `POST /query/stream` using `fetch` + `ReadableStream`

## Planned frontend layout

```text
frontend/
├─ src/App.tsx                    # Query | My documents
├─ src/api/client.ts              # fetch wrapper + session header
├─ src/api/generated.ts           # OpenAPI types
├─ src/session/SessionProvider.tsx
├─ src/tabs/QueryTab.tsx
├─ src/tabs/DocumentsTab.tsx
├─ src/components/ScopeToggle.tsx
├─ src/components/Uploader.tsx
└─ src/lib/streamQuery.ts
```

## Required behavior

- On first mount, mint session via `POST /sessions`; store id in localStorage.
- Disable Mine/Both scope until session has at least one indexed file.
- Sample prompts default to Global scope.
- Stream response tokens from `/query/stream`; fallback to non-streaming on failure.
- "Clear my session" triggers `DELETE /sessions/{id}` and remints a session id.
- Surface citation provenance as `[global]` and `[yours]`.

## Tests

- Vitest + RTL (`frontend/src/**/*.test.tsx`):
  - Session mint/persist behavior
  - Scope toggle enable/disable states
  - Uploader cap and server-rejection UI
  - Incremental stream rendering
- Playwright smoke:
  - load -> upload -> scope Mine -> query -> citation from uploaded file
- Playwright negative:
  - no upload keeps Mine/Both disabled
  - rejected upload errors are clearly shown

## Verification

```bash
DOC_PROFILE=demo DOC_DEMO_UPLOADS=1 \
  uvicorn src.api.main:app --host 127.0.0.1 --port 8000

cd frontend && npm install && npm run dev
cd frontend && npm run test
cd frontend && npm run test:e2e
```

## Handoff (Exit Criteria)

- Query + My Documents tabs are complete with session reset flow.
- Scope toggle, upload caps messaging, and TTL messaging are visible and correct.
- Streaming and fallback response paths are reliable.
- Unit + e2e tests pass locally and in CI.
- Citation source labeling enables user trust verification.

## Transition to Phase 6.3

- Frontend builds reproducibly (`npm ci && npm run build`).
- API CORS includes intended frontend origins.
- No unresolved frontend/backend contract mismatches.
