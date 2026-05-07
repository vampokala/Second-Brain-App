# Phase 6.1 Plan: Backend Session Isolation Foundation

Source of truth: `Docs/Phase6-RefactorDemo_React.md` (this file is an execution slice for iterative delivery).

## Objective

Land session-isolated ingestion/retrieval in the backend while keeping existing Streamlit behavior intact.

## Scope

Ships independently. Streamlit UI continues to work as today. The new HTTP surface unblocks the React build.

## Files to modify

**`src/ingest.py`** — make `ingest()` accept overrides
- Change signature to:
  `def ingest(docs_path, *, bm25_index_path=BM25_INDEX_PATH, collection_name=COLLECTION_NAME, chroma_path="data/embeddings/chroma", processor=None) -> tuple[BM25Index, VectorDatabase]`
- Replace hard-coded uses with kwargs.
- Keep module constants as defaults so CLI remains unchanged.
- Ensure fresh `DocumentProcessor` per session when caller passes one.

**`src/web/ingestion_service.py`** — caps + session-target passthrough
- Add env-overridable caps:
  - `DOC_DEMO_MAX_FILES` (default `3`)
  - `DOC_DEMO_MAX_FILE_MB` (default `3`)
  - `DOC_DEMO_MAX_SESSION_MB` (default `8`)
- Extend `save_uploaded_files()` to enforce:
  - per-file cap
  - file count cap
  - total session cap
- Add magic-bytes check (`.pdf`, `.docx`) and reject type mismatch.
- Extend `run_ingest()` to pass `bm25_index_path`, `collection_name`, `chroma_path` overrides.

**`src/web/session_corpus.py`** (new)
- Add `SessionCorpus` dataclass and helpers:
  - `new_session_id`, `get_or_create`, `touch`, `total_bytes`, `list_active_sessions`, `delete_session`, `janitor_sweep`
- Session layout:
  - `${SESSION_ROOT}/<sid>/{uploads/, chroma/, bm25_index.json, .touched}`
- Defaults:
  - `DOC_DEMO_SESSION_ROOT=/tmp/doc-ingest-sessions`
  - `DOC_DEMO_SESSION_TTL=1800`

**`src/core/rag_orchestrator.py`** — session-aware retrieval
- Extend `QueryRequest`:
  - `session_bm25_index_path`
  - `session_collection_name`
  - `session_chroma_path`
  - `knowledge_scope` (`global|session|both`)
- `session` scope uses only session corpus.
- `both` scope merges global + session results and dedups by id.
- Cache fingerprint must include scope + session corpus identifiers.

**`src/api/main.py`** — session endpoints + CORS + janitor
- Add CORS using `DOC_FRONTEND_ORIGINS`.
- Add endpoints:
  - `POST /sessions`
  - `GET /sessions/{sid}`
  - `POST /sessions/{sid}/documents`
  - `DELETE /sessions/{sid}`
- Extend `POST /query` with optional `session_id` and `knowledge_scope`.
- Reject `session/both` if session has no uploads (409 with hint).
- Mount only in demo mode:
  - `DOC_PROFILE=demo`
  - `DOC_DEMO_UPLOADS=1`
- Reuse upload rate limiter for `POST /sessions/{sid}/documents`.
- Add lifespan janitor task (`session_corpus.janitor_sweep()` every 60s).

**`spaces/app.py`** — enable demo defaults for this phase
- Set:
  - `DOC_DEMO_UPLOADS=1`
  - `DOC_DEMO_SESSION_ROOT=/tmp/doc-ingest-sessions`
  - `DOC_DEMO_MAX_FILES=3`
  - `DOC_DEMO_MAX_FILE_MB=3`
  - `DOC_DEMO_MAX_SESSION_MB=8`
  - `DOC_DEMO_SESSION_TTL=1800`

## Tests

- `tests/unit/test_session_corpus.py`
- `tests/unit/test_ingestion_service.py` (extend or create)
- `tests/unit/test_ingest_overrides.py`
- `tests/unit/test_streamlit_demo_routing.py` (extend)
- `tests/integration/test_session_isolation.py`
- `tests/integration/test_global_corpus_pristine.py`
- `tests/integration/test_session_api.py`

## Verification

```bash
pytest tests/unit/test_session_corpus.py tests/unit/test_ingestion_service.py \
       tests/unit/test_ingest_overrides.py tests/unit/test_streamlit_demo_routing.py \
       tests/integration/test_session_isolation.py \
       tests/integration/test_global_corpus_pristine.py \
       tests/integration/test_session_api.py -v

DOC_PROFILE=demo DOC_EMBEDDING_PROVIDER=sentence_transformers \
DOC_DEMO_UPLOADS=1 DOC_DEMO_SESSION_ROOT=/tmp/doc-ingest-sessions \
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 &
DOC_PROFILE=demo streamlit run src/web/streamlit_app.py
```

API smoke:

```bash
curl -X POST http://127.0.0.1:8000/sessions
curl -X POST -F "files=@./README.md" http://127.0.0.1:8000/sessions/<sid>/documents
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"summarize my doc","session_id":"<sid>","knowledge_scope":"session"}'
sha256sum data/embeddings/bm25_index.json
```

## Handoff (Exit Criteria)

- Backend supports isolated session lifecycle (`create/get/upload/query/delete`) with no cross-session leakage.
- `knowledge_scope` works end-to-end and cache keys are session-safe.
- Guardrails enforced server-side (caps, MIME checks, rate limiting, TTL janitor).
- Streamlit demo still works in demo profile.
- Phase 6.1 tests pass locally and in CI.

## Transition to Phase 6.2

- API contracts are stable for frontend usage.
- OpenAPI includes new request/response shapes.
- Demo env defaults for session uploads are confirmed.
