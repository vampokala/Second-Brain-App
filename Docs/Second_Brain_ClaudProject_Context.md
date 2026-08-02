# Second-Brain-App — Claude Project knowledge base

Use this document as the primary grounding file when answering questions about this repository, designing features, debugging, or explaining behavior. Prefer facts stated here and in cited paths; verify against the codebase when behavior may have changed.

---

## 1. What this project is

**Second-Brain-App** is a local-first web application that indexes an Obsidian-style vault (mounted from the host) and exposes **multi-turn chat**, **hybrid retrieval (BM25 + pgvector)**, optional **reranking**, **streaming** answers with **citations**, and **vault browsing** (`raw/` and `wiki/`).

**Important boundary:** The companion vault repo (e.g. `Second-Brain` on disk) holds immutable `raw/` notes and maintained `wiki/` content. This **app repo** owns the API, UI, Postgres schema, ingest pipeline, and RAG orchestration. Do not assume the agent should edit files under the vault’s `raw/` from app documentation alone.

---

## 2. Runtime topology

| Component | Role |
|-----------|------|
| **FastAPI** (`src/api/main.py`) | HTTP API, static React build, lifespan (migrations, watcher, Ollama health) |
| **Postgres 16 + pgvector** | Chats, messages, citations, `document_chunks`, BM25 snapshot JSON, `vault_files`, `ingest_events`, `embed_queue`, `app_settings`, `connector_sync_state` |
| **Ollama** | Default LLM + embedding models |
| **Vault mount** | Host path (e.g. `VAULT_HOST_PATH`) → `/vault` in container; watcher ingests changes under configured subdirs (`raw`, `wiki` by default) |
| **Connectors** | Pluggable external sources (GitHub, JIRA, Confluence, Slack) under `src/core/connectors/`; a per-connector scheduler syncs them into the ingest pipeline on a cadence |

“Second brain mode” (full RAG + vault + migrations) is tied to **`DATABASE_URL`** being set at startup (see `SecondBrainSettings` in `src/utils/sb_env.py`). Without it, the app may run in a reduced/legacy path.

---

## 3. End-to-end data flow

### Ingest

1. Triggers: filesystem **watcher** (`src/watcher/vault_watcher.py`), or **ingest routes** (`src/api/routes_ingest.py`), or **reindex**, or **connector sync** (scheduled/manual; `src/core/connectors/`, `src/api/routes_connectors.py`).
2. **Document processing** → chunking (sizes from `config.yaml`: `chunk_size`, `overlap`, tokenizer).
3. Chunks feed **BM25** (`src/core/bm25_index.py`) and **vector** storage (`src/utils/pgvector_store.py`, `document_chunks`).
4. Metadata in **`vault_files`**; progress/history in **`ingest_events`** (SSE bus: `src/api/sse_bus.py`).
5. If Ollama/embeddings fail: work lands in **`embed_queue`** for later drain (`src/core/ollama_health.py`, ingest pipeline).

### Query / chat

1. User message → **chat orchestration** (`src/core/chat_orchestrator.py`) and/or **RAG orchestrator** (`src/core/rag_orchestrator.py`).
2. **Hybrid retrieval** (`src/core/hybrid_retriever.py`): BM25 + vector search → fusion (e.g. RRF) → optional **reranker** (`src/core/reranker.py`, `config.yaml` → `reranker.*`).
3. **LLM routing** (`src/core/llm_provider.py`) uses `config.yaml` `llm.*` (providers, allowed models, timeouts) plus runtime keys from env.
4. Response may include **citations** (`src/core/citation_tracker.py`, `message_citations`); optional **evaluation / truthfulness** hooks exist under `src/evaluation/` (often disabled by default for latency).

---

## 4. HTTP API surface (high level)

Base URL in local Docker: typically `http://localhost:8000`. The React dev server may use `5173` with CORS; see `_frontend_origins()` in `src/api/main.py`.

| Area | Notable routes |
|------|------------------|
| Core | `GET /health`, `GET /config/llm`, `GET /metrics` |
| Stateless query | `POST /query`, `POST /query/stream` |
| Chats | `GET/POST /chats`, `GET/PATCH/DELETE /chats/{id}`, message POST/regenerate/edit (see `src/api/routes_chats.py`) |
| Ingest | `POST /ingest`, text/URL variants, `POST /reindex`, `GET /events/ingest` (SSE) |
| Vault | `GET /vault/files`, `GET /vault/files/{path}`, `GET /vault/stats` (`src/api/routes_vault.py`) |
| Settings | `GET /settings`, `PATCH /settings` (`src/api/routes_settings.py`) |
| Connectors | `GET/POST /connectors`, `DELETE /connectors/{id}`, `POST /connectors/{id}/test`, `POST /connectors/{id}/sync`, `GET /connectors/{id}/status` (`src/api/routes_connectors.py`) |
| Legacy / demo | Session upload routes under `/sessions` in `main.py` (guarded by profile/demo flags) |
| Ops | `GET /observability/dashboard` |

For exact request/response shapes, read Pydantic models in `src/api/models.py`, `src/api/models_chats.py`, `src/api/models_ingest.py`, `src/api/models_vault.py`, and OpenAPI at `/docs` when the server is running.

---

## 5. Configuration layers

1. **`config.yaml` (repo root)** — Loaded via `src/utils/config.py` / `load_config()`. Controls chunking, reranker, context window token limits, generation defaults, **multi-provider LLM** lists, API auth/rate-limit **declarations** (e.g. `api.api_keys`), evaluation toggles. **Note:** values here may differ from README examples; trust the file + code paths that read it.

2. **`.env` / environment** — Vault path, `DATABASE_URL`, Ollama host/models, worker counts, watcher debounce, provider API keys, `DOC_API_KEYS`, `LOG_LEVEL`, `DOC_PROFILE`, `HF_TOKEN`, Redis URL if used for rate limiting, etc. See `.env.example`.

3. **`app_settings` in Postgres** — User-tunable persisted settings with env overrides (see settings routes).

When answering “what model is default?” distinguish **Docker env defaults** (e.g. `LLM_DEFAULT_MODEL`) from **`config.yaml` `llm.default_provider` / `default_model_by_provider`**.

---

## 6. Frontend (React)

- Location: `frontend/`.
- **Tabs** include Chat (e.g. `frontend/src/tabs/ChatTab.tsx`), vault navigation, ingest, dashboard as wired in the app shell.
- API clients: e.g. `frontend/src/api/chatsClient.ts`, generated types under `frontend/src/api/generated` if OpenAPI codegen is used.
- Streaming: `frontend/src/lib/streamChat.ts` (and related) for SSE/token handling.

UI work should preserve existing layout/components (`frontend/src/components/chat/*`) unless explicitly refactoring.

---

## 7. Code map (where to look)

| Concern | Primary files |
|---------|-----------------|
| App bootstrap, middleware, query routes, static files | `src/api/main.py` |
| Chat CRUD + streaming | `src/api/routes_chats.py`, `src/core/chat_orchestrator.py`, `src/core/chat_store.py` |
| Ingest + reindex | `src/api/routes_ingest.py`, `src/core/ingest_pipeline.py`, `src/core/document_processor.py` |
| Connectors + scheduler | `src/core/connectors/{base,github,jira,confluence,slack,registry,scheduler}.py`, `src/api/routes_connectors.py`, `connector_sync_state` model in `src/db/models.py` |
| RAG glue | `src/core/rag_orchestrator.py`, `src/core/query_processor.py` |
| Retrieval | `src/core/hybrid_retriever.py`, `src/core/bm25_search.py`, `src/core/vector_search.py` |
| Reranking | `src/core/reranker.py` |
| DB models / migrations | `src/db/models.py`, `src/db/migrations/versions/*`, `alembic.ini` |
| Vault FS API | `src/api/routes_vault.py` |
| Watcher | `src/watcher/vault_watcher.py` |
| Observability / metrics | `src/core/observability.py`, `src/monitoring/metrics.py` |
| Streamlit (if used) | `src/web/streamlit_app.py` |

---

## 8. Operations (operator memory)

Common Makefile targets (see repo `Makefile`): `build`, `up`, `down`, `logs`, `reindex`, `smoke`, `migrate`, `backup`, `dbshell`. Ollama models must be pulled inside the Ollama container/service to match `EMBED_MODEL` / chat model env or UI-selected models.

Backups: Postgres dump pattern documented in `README.md` / `Docs/RUNBOOK.md`.

---

## 9. Testing

- Python: `tests/unit`, `tests/integration` (pytest).
- Frontend: `npm run test` in `frontend/`.
- Smoke: `make smoke` / `scripts/smoke.sh` when present.

---

## 10. How to use this file in Claude Projects

- **Architecture / “how does X work?”** — Sections 2–3 + module map §7.
- **API contracts** — §4 + `src/api/models*.py` + live `/docs`.
- **Config / why is model Y used?** — §5 + `config.yaml` + `.env.example`.
- **Debugging ingest / citations** — §3 ingest branch, `embed_queue`, `make reindex`, vault mount paths.
- **Adding a feature** — Identify layer (ingest, retrieval, generation, API, UI), extend the smallest existing module, keep API and DB migrations aligned.

When this document conflicts with the code, **the code wins** — update this file after substantive changes.

---

## 11. Related docs in-repo

- `README.md` — user-facing quickstart, env table, structure.
- `Docs/ARCHITECTURE.md` — diagrams, schema-oriented overview.
- `Docs/RUNBOOK.md` — operations detail (if present).
- `.cursor/skills/doc-ingestion/SKILL.md` — contributor workflow for RAG/ingest/API changes in this codebase.

---

*Last updated for Claude Project ingestion: 2026-06-06 (added connectors: GitHub, JIRA, Confluence, Slack + scheduler).*
