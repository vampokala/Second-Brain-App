# Plan: Per-session document upload for the demo, on a React + FastAPI front-end

## Context

The Hugging Face Spaces demo at [src/web/streamlit_app.py](src/web/streamlit_app.py) currently disables document uploads in demo mode (early-return at [src/web/streamlit_app.py:344-350](src/web/streamlit_app.py#L344-L350)) because the ingestion pipeline writes to a single shared Chroma collection (`"documents"` at [src/core/rag_orchestrator.py:32](src/core/rag_orchestrator.py#L32)) and a single shared BM25 index file ([src/core/rag_orchestrator.py:30](src/core/rag_orchestrator.py#L30)). Visitors can only run pre-canned prompts against pre-loaded sample docs, which leaves them unable to verify whether the RAG pipeline is genuinely grounded — eroding trust on first contact.

Goal: let a visitor (a) try the existing sample prompts, (b) upload a few of their own documents, (c) ask questions scoped to global / their uploads / both, and (d) see citations they can verify against the file they just uploaded — all without polluting the shared corpus or other visitors' sessions.

You opted to go straight to a React + FastAPI front-end (rather than extending Streamlit) and to ship the work in phases. Backend isolation must land first regardless of front-end choice, so the plan starts there.

Decisions captured: **3-way knowledge-scope toggle (Global / Mine / Both)**; **conservative caps: 3 files, 3 MB each, 8 MB total, 30 min idle TTL**.

## High-level approach

The clean architectural seam already exists in the code — three hard-coded constants (`BM25_INDEX_PATH`, `COLLECTION_NAME`, `CHROMA_PATH`) at module scope in [src/ingest.py:21-22](src/ingest.py#L21-L22) and [src/core/rag_orchestrator.py:30-32](src/core/rag_orchestrator.py#L30-L32). The plan parameterizes those, threads a session-scoped triple `(bm25_index_path, collection_name, chroma_path)` through the request, and unions retrieval results when scope is "Both". Existing components (`HybridRetriever`, `BM25Search`, `VectorSearch`, `CrossEncoderReranker`, `RAGGenerator`, `CitationVerifier`) require no changes.

The cached singleton orchestrator at [src/web/streamlit_app.py:39](src/web/streamlit_app.py#L39) stays — it reads its session inputs per-`QueryRequest`, not at construction.

## Phase 6.1 — Backend session isolation foundation (~2-3 days)

Ships independently. Streamlit UI continues to work as today. The new HTTP surface unblocks the React build.

### Objective

Land session-isolated ingestion/retrieval in the backend while keeping existing Streamlit behavior intact.

### Scope

### Files to modify

**[src/ingest.py](src/ingest.py)** — make `ingest()` accept overrides
- Change signature at [L37](src/ingest.py#L37) to:
  `def ingest(docs_path, *, bm25_index_path=BM25_INDEX_PATH, collection_name=COLLECTION_NAME, chroma_path="data/embeddings/chroma", processor=None) -> tuple[BM25Index, VectorDatabase]`
- Replace hard-coded uses at [L54](src/ingest.py#L54), [L55](src/ingest.py#L55), [L91](src/ingest.py#L91), [L97-98](src/ingest.py#L97-L98) with the kwargs.
- When `processor is None`, build one as today; the parameter exists so the caller passes a fresh `DocumentProcessor` per session (its `_seen_hashes` is per-instance and would otherwise leak dedup state across sessions).
- Module constants stay as defaults — CLI usage unchanged.

**[src/web/ingestion_service.py](src/web/ingestion_service.py)** — caps + session-target passthrough
- Add module constants (env-overridable):
  - `MAX_FILES_PER_SESSION = int(os.getenv("DOC_DEMO_MAX_FILES", "3"))`
  - `MAX_FILE_BYTES = int(os.getenv("DOC_DEMO_MAX_FILE_MB", "3")) * 1024 * 1024`
  - `MAX_SESSION_BYTES = int(os.getenv("DOC_DEMO_MAX_SESSION_MB", "8")) * 1024 * 1024`
- Extend `save_uploaded_files()` at [L29](src/web/ingestion_service.py#L29) to accept `existing_bytes: int = 0, max_files: int | None = None, max_file_bytes: int | None = None, max_session_bytes: int | None = None`. Reject with `IngestFileResult(status="rejected", message=...)` for: oversize file, file count cap, session disk cap.
- Add a magic-bytes sanity check (e.g., `.pdf` must start with `%PDF`, `.docx` must start with `PK\x03\x04`); reject `type_mismatch` otherwise.
- Extend `run_ingest()` at [L50](src/web/ingestion_service.py#L50) to accept `bm25_index_path: str | None = None, collection_name: str | None = None, chroma_path: str | None = None` and forward to `ingest(...)`.

**`src/web/session_corpus.py`** (new — only new module)
```
SESSION_ROOT = Path(os.getenv("DOC_DEMO_SESSION_ROOT", "/tmp/doc-ingest-sessions"))
SESSION_TTL_SECONDS = int(os.getenv("DOC_DEMO_SESSION_TTL", "1800"))

@dataclass
class SessionCorpus:
    session_id: str
    upload_dir: Path
    chroma_path: Path
    bm25_index_path: Path
    collection_name: str   # f"sess_{session_id}" — Chroma-safe
    created_at: float

def new_session_id() -> str        # uuid4().hex[:12]
def get_or_create(sid: str) -> SessionCorpus
def touch(sid: str) -> None        # bump .touched mtime, refresh TTL
def total_bytes(s: SessionCorpus) -> int
def list_active_sessions() -> list[SessionCorpus]
def delete_session(sid: str) -> None
def janitor_sweep(now: float | None = None) -> int
```
Layout per session: `${SESSION_ROOT}/<sid>/{uploads/, chroma/, bm25_index.json, .touched}`. Idempotent and safe under concurrent reruns.

**[src/core/rag_orchestrator.py](src/core/rag_orchestrator.py)** — session-aware retrieval
- Extend `QueryRequest` at [L36](src/core/rag_orchestrator.py#L36) with:
  - `session_bm25_index_path: Optional[str] = None`
  - `session_collection_name: Optional[str] = None`
  - `session_chroma_path: Optional[str] = None`
  - `knowledge_scope: str = "global"`  # `"global" | "session" | "both"`
- `_load_components()` at [L87](src/core/rag_orchestrator.py#L87): when scope is `session` or `both`, also load a second `(BM25Index, VectorDatabase)` from session paths. If session BM25 file is missing/empty (user hasn't uploaded yet), fall back gracefully — log warning and demote scope to `global`.
- `_retrieve()` at [L92](src/core/rag_orchestrator.py#L92): when `scope == "session"` run hybrid against the session pair only; when `scope == "both"` run two `HybridRetriever.retrieve()` calls and concatenate, deduping by `id`. The reranker at [L165](src/core/rag_orchestrator.py#L165) is the final arbiter — no change to fusion/rerank logic.
- Cache-key fingerprint at [L126](src/core/rag_orchestrator.py#L126) must include scope and session triple so global cache hits don't leak across users:
  `corpus_fingerprint=f"{COLLECTION_NAME}:{BM25_INDEX_PATH}|{req.knowledge_scope}|{req.session_collection_name or '-'}:{req.session_bm25_index_path or '-'}"`

**[src/api/main.py](src/api/main.py)** — new endpoints + CORS + janitor
- Add CORS middleware (allow the React origin: localhost dev port + the deployed origin from env `DOC_FRONTEND_ORIGINS`).
- New endpoints:
  - `POST /sessions` → `{session_id, expires_at}`. Mints id, calls `session_corpus.get_or_create()`. Sets `X-Demo-Session-Id` response header so the React app can also use it without cookies.
  - `GET /sessions/{sid}` → `{session_id, files: [...], total_bytes, max_session_bytes, max_files, expires_at}`. Useful for the "My documents" panel.
  - `POST /sessions/{sid}/documents` → multipart upload. Calls `save_uploaded_files(session.upload_dir, files, existing_bytes=total_bytes(session), ...)`, then `run_ingest(session.upload_dir, bm25_index_path=session.bm25_index_path, collection_name=session.collection_name, chroma_path=str(session.chroma_path))`. Touches the session.
  - `DELETE /sessions/{sid}` → `session_corpus.delete_session(sid)` then mints a new id.
- Extend `POST /query` at [L155](src/api/main.py#L155): accept optional `session_id`, `knowledge_scope`. If provided, look up the session, touch it, and pass `session_*` paths into `QueryRequest`. Reject `session`/`both` scopes when session has no uploads (return 409 with a hint to upload first).
- Demo-mode guard at [L112](src/api/main.py#L112): the new session endpoints are **only** mounted when `DOC_PROFILE=demo` and `DOC_DEMO_UPLOADS=1`. Outside demo mode, ingestion stays through the existing batch path.
- Per-IP upload rate limit: reuse the existing limiter at [L77-99](src/api/main.py#L77-L99) on `POST /sessions/{sid}/documents`.
- FastAPI `lifespan`: start a background `asyncio` task that runs `session_corpus.janitor_sweep()` every 60 s; stop it on shutdown. Replaces the on-rerun best-effort sweep entirely.

**[spaces/app.py](spaces/app.py)** — opt the deployed demo into Phase 6.1
- After [L34](spaces/app.py#L34) add the env defaults:
  - `DOC_DEMO_UPLOADS=1`
  - `DOC_DEMO_SESSION_ROOT=/tmp/doc-ingest-sessions`
  - `DOC_DEMO_MAX_FILES=3`, `DOC_DEMO_MAX_FILE_MB=3`, `DOC_DEMO_MAX_SESSION_MB=8`, `DOC_DEMO_SESSION_TTL=1800`
- HF Spaces ephemeral disk is wiped on container restart — `/tmp` keeps the persisted `data/` clean.

### Functions/classes to reuse unchanged

- `save_uploaded_files()` at [src/web/ingestion_service.py:29](src/web/ingestion_service.py#L29) — body preserved, signature additions only
- `RAGOrchestrator` class itself at [src/core/rag_orchestrator.py:64](src/core/rag_orchestrator.py#L64) — only `QueryRequest` grows
- `HybridRetriever`, `BM25Search`, `VectorSearch` ([src/core/](src/core/)) — second instance per request when scope demands; otherwise unchanged
- `VectorDatabase` at [src/utils/database.py:29](src/utils/database.py#L29) — already accepts `chroma_path`; just construct a second one for sessions
- `BM25Index.save` / `BM25Index.load` at [src/core/bm25_index.py](src/core/bm25_index.py) — already path-parameterized
- `CrossEncoderReranker`, `RAGGenerator`, `CitationVerifier`, `ResponseCache` — unchanged

### Tests (Phase 6.1)

Add under [tests/unit/](tests/unit/) and [tests/integration/](tests/integration/):

- `tests/unit/test_session_corpus.py` — id format, idempotent `get_or_create`, janitor TTL eviction, `delete_session` on missing dir is a no-op, concurrent `get_or_create` is safe.
- Extend `tests/unit/test_ingestion_service.py` (or create) — caps enforced (oversize, count, session disk), magic-byte mismatch rejected, override kwargs forwarded.
- `tests/unit/test_ingest_overrides.py` — `ingest(tmp, bm25_index_path=..., collection_name="sess_x", chroma_path=...)` writes to overrides and not defaults; default-arg call still hits the global paths.
- Extend `tests/unit/test_streamlit_demo_routing.py` — `knowledge_scope="session"` carries session paths only; `"both"` carries both; cache key changes when session paths change.
- `tests/integration/test_session_isolation.py` — bootstrap a tiny global corpus; mint sessions A and B; ingest different fixtures into each; query A scope=`session` returns only A's chunks; query A scope=`both` returns A+global, never B's; janitor with mocked clock past TTL deletes the session dirs.
- `tests/integration/test_global_corpus_pristine.py` — sha256 the global BM25 + Chroma store before/after multiple session ingests; assert unchanged.
- `tests/integration/test_session_api.py` — exercise `POST /sessions`, `POST /sessions/{id}/documents`, `GET /sessions/{id}`, `DELETE /sessions/{id}` and `POST /query` with session_id end-to-end via FastAPI `TestClient`.

### Verification (Phase 6.1, local)

```
# Unit + integration
pytest tests/unit/test_session_corpus.py tests/unit/test_ingestion_service.py \
       tests/unit/test_ingest_overrides.py tests/unit/test_streamlit_demo_routing.py \
       tests/integration/test_session_isolation.py \
       tests/integration/test_global_corpus_pristine.py \
       tests/integration/test_session_api.py -v

# Boot demo-mode API + Streamlit (Streamlit still works)
DOC_PROFILE=demo DOC_EMBEDDING_PROVIDER=sentence_transformers \
DOC_DEMO_UPLOADS=1 DOC_DEMO_SESSION_ROOT=/tmp/doc-ingest-sessions \
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 &
DOC_PROFILE=demo streamlit run src/web/streamlit_app.py

# Curl smoke the new API
curl -X POST http://127.0.0.1:8000/sessions
# → {"session_id":"...","expires_at":...}
curl -X POST -F "files=@./README.md" http://127.0.0.1:8000/sessions/<sid>/documents
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"summarize my doc","session_id":"<sid>","knowledge_scope":"session"}'

# Confirm shared corpus untouched
sha256sum data/embeddings/bm25_index.json   # before/after — identical
```

### Phase 6.1 handoff (exit criteria)

- Backend supports isolated session corpus lifecycle (`create/get/upload/query/delete`) without cross-session leakage.
- `knowledge_scope` (`global|session|both`) works end-to-end and cache keys are session-safe.
- Guardrails are enforced server-side (file caps, MIME sanity checks, rate limiting, TTL janitor).
- Existing Streamlit demo still runs in demo profile (no regression to current user flow).
- All Phase 6.1 tests pass locally and in CI.

### Transition to Phase 6.2 (entry criteria)

- API contracts are stable for frontend consumption (`/sessions`, `/sessions/{id}`, `/sessions/{id}/documents`, `/query` with session fields).
- OpenAPI spec reflects new request/response shapes.
- Demo env defaults for session uploads are available.

## Phase 6.2 — React MVP front-end over stable API (~5-7 days)

Built in a new top-level `frontend/` directory; FastAPI keeps running unchanged. No HF cutover yet — develop locally against `http://127.0.0.1:8000`.

### Objective

Ship a usable React demo UI that consumes Phase 6.1 APIs and validates isolated user-upload experience.

### Scope

### Stack

- **Vite + React 18 + TypeScript** (lean SPA, no SSR needed for a demo).
- **Tailwind CSS + shadcn/ui** (Radix-based primitives — drop-in card, tabs, radio-group, file-uploader, progress, toast).
- **TanStack Query** for server state (session, file list, query results) — gives caching, retries, and dedup for free.
- **Zustand** (or React Context) for the session-id slice that needs to outlive a route change.
- **Typed API client** generated from FastAPI's OpenAPI schema via `openapi-typescript` so the FE stays type-safe against the BE contract.
- **Streaming**: consume `POST /query/stream` via the `EventSource`-style `fetch` + `ReadableStream` pattern (since SSE doesn't natively support POST).

### Component layout

```
frontend/
├─ index.html
├─ vite.config.ts
├─ tailwind.config.ts
├─ src/
│  ├─ main.tsx
│  ├─ App.tsx                      # Tabs: Query | My documents
│  ├─ api/
│  │  ├─ client.ts                 # fetch wrapper, attaches X-Demo-Session-Id
│  │  └─ generated.ts              # openapi-typescript output
│  ├─ session/
│  │  ├─ SessionProvider.tsx       # mints session via POST /sessions on first load
│  │  └─ useSession.ts
│  ├─ tabs/
│  │  ├─ QueryTab.tsx              # sample prompts, scope toggle, run
│  │  └─ DocumentsTab.tsx          # drop-zone, file list, caps meter, reset
│  ├─ components/
│  │  ├─ SamplePromptChips.tsx     # mirrors _DEMO_QUESTIONS
│  │  ├─ ScopeToggle.tsx           # 3-way radio, disables Mine/Both until upload
│  │  ├─ AnswerPanel.tsx           # answer + truthfulness badge
│  │  ├─ CitationsList.tsx         # tagged [global]/[yours]
│  │  ├─ RetrievedChunks.tsx
│  │  └─ Uploader.tsx              # drag-drop, per-file status
│  └─ lib/streamQuery.ts           # SSE-over-POST helper
```

### UX wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│ Doc Ingestion Assistant            session …a91c · 28:14 left   │
│ ⓘ Hosted demo. Your uploads stay in this session for 30 min,    │
│   are not added to the shared corpus, and aren't visible to     │
│   anyone else.                                                  │
├─ [ Query ] [ My documents ] ─────────────────────────────────── │
│                                                                 │
│ Query tab:                                                      │
│   Try a sample:  [What is RAG?] [What is RRF?] [BM25 vs vec…]   │
│                                                                 │
│   Knowledge scope:                                              │
│     ◉ Global sample corpus                                      │
│     ○ My uploads only         (disabled until upload)           │
│     ○ Both                                                      │
│                                                                 │
│   Provider [ ▼ ]   Model [ ▼ ]                                  │
│   ┌───────────────────────────────────────────────┐             │
│   │ Ask a question…                               │             │
│   └───────────────────────────────────────────────┘             │
│   [ Run ]                                                       │
│                                                                 │
│   ── Answer ──  🟢 Truthfulness 0.89                            │
│   …answer text streaming in…                                    │
│                                                                 │
│   Citations:                                                    │
│     [yours] my-resume.pdf · chunk 2                             │
│     [global] phase2_hybrid_retrieval.md · chunk 5               │
│                                                                 │
│ My documents tab:                                               │
│   Disk used: 1.2 / 8.0 MB     Files: 2 / 3                      │
│   ⓘ ≤ 3 files · ≤ 3 MB each · ≤ 8 MB total                      │
│   ┌───────── drop files here ─────────┐                         │
│   └──────────────────────────────────┘                          │
│   • my-resume.pdf      indexed                                  │
│   • report.txt         indexed                                  │
│   [ Clear my session ]                                          │
└─────────────────────────────────────────────────────────────────┘
```

Behavior detail:
- On first mount, `SessionProvider` calls `POST /sessions` and stashes the id in localStorage (so a refresh keeps the same session until TTL).
- The scope toggle disables Mine/Both until `GET /sessions/{id}` reports ≥ 1 indexed file.
- Sample prompts always target Global scope by default (clicking a chip sets scope=Global and fills the textarea).
- The streaming answer uses `lib/streamQuery.ts` to read tokens off `/query/stream`; falls back to non-streaming if SSE fails.
- "Clear my session" calls `DELETE /sessions/{id}` then mints a new one.

### Tests (Phase 6.2)

- `frontend/src/**/*.test.tsx` with **Vitest + React Testing Library**:
  - SessionProvider mints a session on first mount and stores it.
  - ScopeToggle disables Mine/Both when no uploads, enables after upload.
  - Uploader respects 3-file cap client-side and shows server rejection toasts.
  - QueryTab renders streamed tokens incrementally.
- **Playwright** smoke (`frontend/e2e/`): full happy-path — load → upload one file → switch to Mine → ask a question → see the file's citation.
- **Playwright** negative path: no uploads keeps Mine/Both disabled; rejected uploads surface clear cap/type errors.

### Verification (Phase 6.2, local)

```
# Backend
DOC_PROFILE=demo DOC_DEMO_UPLOADS=1 \
  uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173

# E2E
cd frontend && npm run test       # vitest
npm run test:e2e                  # playwright
```

### Phase 6.2 handoff (exit criteria)

- React app provides Query + My Documents tabs, scope toggle, streaming/fallback answer flow, and session reset.
- UI clearly communicates upload limits and session TTL.
- Frontend unit tests and e2e tests pass locally and in CI.
- UX supports clear citation provenance (`[global]` vs `[yours]`) for trust validation.

### Transition to Phase 6.3 (entry criteria)

- Frontend builds reproducibly (`npm ci && npm run build`) and can be served as static assets.
- API CORS config includes intended frontend origins.
- No unresolved API/frontend contract mismatches remain.

## Phase 6.3 — Single-container deploy & HF Spaces cutover (~2 days)

The current HF Space uses the Streamlit SDK (`spaces/README.md`). Switch to the Docker SDK so we ship one container with FastAPI + the built React SPA.

### Objective

Deploy one container (FastAPI + built React) to simplify ops and align HF delivery with the new UI.

### Scope

### Files to modify

- **[docker/Dockerfile](docker/Dockerfile)** — multi-stage:
  - Stage 1 (`node:20-alpine`): `npm ci && npm run build` → `frontend/dist`.
  - Stage 2 (existing Python image): `COPY --from=stage1 /app/frontend/dist /app/static`.
  - Final `CMD` runs uvicorn only — Streamlit is no longer in the deployed image.
- **[src/api/main.py](src/api/main.py)** — when the static dir exists, mount it: `app.mount("/", StaticFiles(directory="static", html=True), name="ui")`. Move existing API routes under `/api` prefix (or use `app.mount` ordering so SPA fallback kicks in only on unknown paths). Keep `/health`, `/metrics`, `/query`, `/query/stream` reachable.
- **[spaces/README.md](spaces/README.md)** — change frontmatter:
  ```yaml
  sdk: docker
  app_port: 8000
  ```
  Drop `app_file: spaces/app.py`.
- **[spaces/app.py](spaces/app.py)** — repurpose as a tiny launcher that just sets the demo env vars and execs uvicorn (or remove entirely if env defaults move into the Dockerfile).
- **[.github/workflows/sync-to-spaces.yml](.github/workflows/sync-to-spaces.yml)** — extend to run `npm ci && npm run build` before pushing, OR rely on HF's Docker build (preferred — keeps CI fast).
- **[.github/workflows/ci.yml](.github/workflows/ci.yml)** — add a `frontend` job: `npm ci`, `npm run lint`, `npm run test`, `npm run build`. Add a `e2e` job that boots the API and runs Playwright.

Streamlit code stays in `src/web/streamlit_app.py` behind an env flag during the cutover so we can roll back to the previous Space SDK by reverting `spaces/README.md`.

### Verification (Phase 6.3)

```
# Build and run the unified container locally
docker build -f docker/Dockerfile -t doc-ingest:demo .
docker run --rm -p 8000:8000 \
  -e DOC_PROFILE=demo -e DOC_DEMO_UPLOADS=1 \
  -e DOC_EMBEDDING_PROVIDER=sentence_transformers \
  doc-ingest:demo
open http://127.0.0.1:8000

# Push branch → HF Space rebuilds via Docker SDK; smoke-test the live URL.
```

### Phase 6.3 handoff (exit criteria)

- Unified container runs locally and in HF Spaces with expected routes and SPA fallback behavior.
- Core API routes (`/health`, `/metrics`, `/query`, `/query/stream`) remain reachable and validated.
- Demo smoke tests pass against deployed environment.
- Rollback procedure to prior Space setup is documented and tested.

### Transition to Phase 6.4 (entry criteria)

- React demo has soaked in production-like traffic for at least one week.
- No unresolved severity-1/2 issues tied to the new deployment path.
- Team confirms Streamlit rollback is no longer required.

## Phase 6.4 — Decommission Streamlit (optional, after 6.3 soaks)

Once the React demo has been live for a week without regressions:

- Delete [src/web/streamlit_app.py](src/web/streamlit_app.py).
- Remove `streamlit` from [requirements/base.txt](requirements/base.txt).
- Drop the Streamlit container from [docker/docker-compose.yml](docker/docker-compose.yml).
- Update [README.md](README.md) screenshots and quickstart.
- Delete `tests/unit/test_streamlit_demo_routing.py`.

Keep `_DEMO_QUESTIONS` (move into a small JSON the API serves at `GET /api/sample-prompts` so the React FE stays in sync).

### Phase 6.4 handoff (exit criteria)

- Streamlit runtime, dependencies, and tests are removed cleanly.
- Documentation and quickstart reflect the React + FastAPI deployment only.
- Sample prompts are served from API/shared source of truth.

### Transition to next program increment

- Phase 6 is complete when 6.1-6.4 exit criteria are satisfied (with 6.4 optional per release decision).
- Any deferred improvements become backlog items for Phase 7 (e.g., hard TTL cap, query concurrency limiter, enhanced abuse controls).

## Caps & abuse guardrails (locked-in defaults)

| Guard | Default | Enforced where | Failure mode |
|---|---|---|---|
| Per-file size cap | 3 MB | `save_uploaded_files()` | `rejected: oversize` |
| File count cap | 3 / session | `save_uploaded_files()` | `rejected: file_count_cap` |
| Total session disk cap | 8 MB | `save_uploaded_files()` | `rejected: session_disk_cap` |
| Extension allowlist | `.pdf .docx .txt .md .html` | already at `_SUPPORTED_EXTS` ([L15](src/web/ingestion_service.py#L15)) | `failed: unsupported` |
| MIME magic | header sniff | new helper in `save_uploaded_files()` | `rejected: type_mismatch` |
| Per-IP upload rate-limit | reuse [src/api/main.py:77-99](src/api/main.py#L77-L99) limiter | `POST /sessions/{sid}/documents` | 429 |
| Janitor disk ceiling | total `SESSION_ROOT > 1 GB` evicts oldest | `janitor_sweep()` | oldest sessions dropped |
| Idle TTL | 30 min, refreshed on every query/upload | `.touched` mtime + janitor | session purged |

All caps overridable via env (`DOC_DEMO_*`) so we can tune on HF without code changes.

## Phase execution re-review (end-to-end)

Execution order is intentionally strict: **6.1 -> 6.2 -> 6.3 -> 6.4 (optional)**.

- **6.1 is the architectural base**: session isolation, scoped retrieval, and backend guardrails must be correct before any UI investment.
- **6.2 depends on 6.1 contracts**: React work starts only after session APIs and `knowledge_scope` behavior are stable and test-covered.
- **6.3 depends on 6.2 build maturity**: container cutover happens only after frontend build/test reliability and CORS/origin alignment are in place.
- **6.4 is a stabilization cleanup**: Streamlit removal is deferred until post-soak confidence to protect rollback safety.

Readiness checklist before starting each phase:

- Previous phase exit criteria are met and documented.
- Phase-specific test suite passes locally and in CI.
- No open blocker in cross-phase risks that invalidates next-phase assumptions.
- Handoff artifacts are available (API contract, env defaults, deployment notes, rollback notes as applicable).

## Cross-phase risks & open questions

1. **HF Space SDK switch (Streamlit → Docker)** is a one-way door for the running Space. Do the cutover on a fresh Space first (e.g., `…-demo-v2`), validate, then point the public URL at it.
2. **Reranker memory under concurrency** — cross-encoder is the dominant cost (~400 MB) and serializes on CPU. More visitors uploading doesn't worsen retrieval contention, but Phase 6.2 should add a concurrency limiter on `/query` if HF traffic grows.
3. **Cache-key fingerprint correctness** — the change at [rag_orchestrator.py:126](src/core/rag_orchestrator.py#L126) is load-bearing. Test must assert two sessions with identical query text get distinct cache keys.
4. **`DocumentProcessor._seen_hashes` per-instance** ([src/core/document_processor.py:49](src/core/document_processor.py#L49)) — passing a fresh processor per session ingest is required, otherwise a session can silently skip files matching another session's hashes.
5. **TTL refresh on read vs write** — refreshing on every query keeps active users' uploads alive indefinitely; consider an absolute hard cap (4 h) in Phase 6.2 if abuse appears.
6. **SSE-over-POST quirks** — some proxies break long-lived POST streams. The React client falls back to non-streaming on first failure.
7. **CORS scope** — set `DOC_FRONTEND_ORIGINS` tightly (no `"*"`) once the Space URL is final.
8. **Browser refresh** — localStorage retains `session_id`; if backend has expired it, the FE catches a 404 from `GET /sessions/{id}` and re-mints transparently.
9. **Citation labeling** — to display `[yours]` vs `[global]`, the merged `RetrievedResult.metadata` must carry the source collection. Cheapest: prefix chunk `id`s with `sess_<sid>__` for session uploads (already implicit since the collection name differs); the FE checks the prefix.
10. **Streamlit coexistence during transition** — keep the Streamlit page reachable via a hidden `/legacy` route until Phase 6.4 to ease rollback.

## Critical files by phase

- **Phase 6.1**
  - [src/ingest.py](src/ingest.py)
  - [src/web/ingestion_service.py](src/web/ingestion_service.py)
  - `src/web/session_corpus.py` (new)
  - [src/core/rag_orchestrator.py](src/core/rag_orchestrator.py)
  - [src/api/main.py](src/api/main.py)
  - [spaces/app.py](spaces/app.py)
- **Phase 6.2**
  - `frontend/` (new tree)
- **Phase 6.3**
  - [docker/Dockerfile](docker/Dockerfile)
  - [src/api/main.py](src/api/main.py)
  - [spaces/README.md](spaces/README.md)
  - [spaces/app.py](spaces/app.py)
  - [.github/workflows/ci.yml](.github/workflows/ci.yml)
  - [.github/workflows/sync-to-spaces.yml](.github/workflows/sync-to-spaces.yml)
- **Phase 6.4**
  - [src/web/streamlit_app.py](src/web/streamlit_app.py)
  - [requirements/base.txt](requirements/base.txt)
  - [docker/docker-compose.yml](docker/docker-compose.yml)
  - [README.md](README.md)
  - `tests/unit/test_streamlit_demo_routing.py`
