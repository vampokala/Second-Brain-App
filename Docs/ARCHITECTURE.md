# ARCHITECTURE

## System Overview

Second-Brain-App runs as a three-service local stack:
- API: FastAPI + static React assets
- Database: Postgres 16 + pgvector
- Model runtime: Ollama

It also pulls from external team sources through a pluggable connector layer
(GitHub, JIRA, Confluence, Slack) on a per-connector schedule.

```mermaid
flowchart LR
  Browser[Browser UI] --> API[FastAPI]
  API --> DB[(Postgres + pgvector)]
  API --> OLL[Ollama]
  API --> FS[/Mounted Vault/]
  subgraph ext [External sources]
    GH[GitHub]
    JR[JIRA]
    CF[Confluence]
    SL[Slack]
  end
  API --> CONN[Connector layer + scheduler]
  CONN --> ext
```

## Ingest Pipeline

```mermaid
flowchart TB
  File[File/Text/URL input] --> Proc[DocumentProcessor]
  Conn[Connector sync: GitHub/JIRA/Confluence/Slack] --> Proc
  Proc --> Chunk[Chunk generation]
  Chunk --> BM25[BM25Index snapshot]
  Chunk --> VEC[document_chunks vectors]
  Chunk --> VF[vault_files metadata]
  Proc --> EVT[ingest_events]
  OLL[Ollama embeddings] --> VEC
  OLL -. unavailable .-> Q[embed_queue pending]
```

Flow details:
1. Input arrives from watcher or ingest routes.
2. Parser extracts metadata/frontmatter and normalizes content.
3. Chunks update BM25 snapshot and vector rows.
4. Ingest events stream via SSE and persist to DB.
5. If Ollama is unavailable, embeddings are deferred into `embed_queue`.

## Connector Sync (GitHub / JIRA / Confluence / Slack)

External team sources plug in through `SourceConnector` implementations. Each
connector fetches records, normalizes them to markdown, and routes them through
the **same** `IngestPipeline.ingest_text`, so synced items are indexed, retrieved,
and cited exactly like local documents. A per-connector scheduler triggers
incremental syncs on each connector's cadence.

```mermaid
flowchart TB
  STATE[(connector_sync_state)] --> SCHED[Per-connector scheduler]
  SCHED --> REG[Connector registry]
  REG --> GH[GitHub: commits, issues/PRs]
  REG --> JR[JIRA: issues via JQL]
  REG --> CF[Confluence: space pages]
  REG --> SL[Slack: messages + thread replies]
  GH --> NORM[Normalize to markdown + frontmatter]
  JR --> NORM
  CF --> NORM
  SL --> NORM
  NORM --> ING[IngestPipeline.ingest_text]
  ING --> IDX[BM25 snapshot + pgvector + vault_files]
  SCHED -. cursor advance / status .-> STATE
  ING -. progress .-> SSE[ingest SSE bus]
```

Flow details:
1. Scheduler ticks (~60s); a connector is due when `now - last_sync_at >= sync_interval_min` (an in-flight set prevents overlap).
2. The registry builds the connector; the secret is read from an env var named by `config.token_env` (never stored in the DB).
3. Records are fetched **incrementally** from the stored cursor, normalized, and written to `raw/connectors/<type>/<resource>/<id>.md`.
4. Each item is ingested through the standard pipeline; progress publishes on the shared ingest SSE bus.
5. On success the cursor advances and `last_status`/`item_count` persist; a failed sync leaves the cursor unchanged so the window retries.

## Chat Query Pipeline

```mermaid
flowchart TB
  U[User prompt] --> ORCH[RAG/Chat orchestrator]
  ORCH --> RET[Hybrid retrieval]
  RET --> BM25S[BM25 search]
  RET --> VECS[Vector search]
  RET --> FUSION[RRF fusion + optional rerank]
  FUSION --> LLM[Provider routing + generation]
  LLM --> SSE[SSE stream token/events]
  LLM --> MSG[messages + citations persisted]
```

## Module Map

- `src/api/main.py`: app bootstrap, lifespan, routing, auth/rate-limit helpers.
- `src/api/routes_ingest.py`: ingest endpoints and ingest SSE events.
- `src/api/routes_chats.py`: chat CRUD and streaming message operations.
- `src/api/routes_vault.py`: file browsing, file read, stats.
- `src/api/routes_settings.py`: persisted settings patch/read.
- `src/api/routes_connectors.py`: connector CRUD, test, manual sync, status.
- `src/core/connectors/`: connector layer — `base.py` (`SourceConnector`, `SourceItem`), `github.py`, `jira.py`, `confluence.py`, `slack.py`, `registry.py` (build + `sync_connector`), `scheduler.py` (`is_due`/`next_sync_at` + tick loop).
- `src/core/ingest_pipeline.py`: ingest orchestration, reindex, queue draining.
- `src/core/rag_orchestrator.py`: retrieval + generation glue.
- `src/core/bm25_index.py`: in-memory BM25 with Postgres snapshot persistence.
- `src/core/ollama_health.py`: availability checks + embed queue drain trigger.
- `src/db/models.py`: SQLAlchemy model definitions.
- `src/watcher/vault_watcher.py`: watchdog-based filesystem ingest trigger.

## Postgres Schema (Current)

```mermaid
erDiagram
  chats ||--o{ messages : has
  messages ||--o{ message_citations : cites
  document_chunks {
    uuid id
    string chunk_id
    string source_path
    int chunk_index
    vector embedding
  }
  bm25_snapshot {
    int id
    jsonb payload
  }
  vault_files {
    string path
    string title
    int chunk_count
  }
  ingest_events {
    uuid id
    string file_path
    string status
  }
  embed_queue {
    uuid id
    string file_path
    string status
  }
  app_settings {
    string key
    jsonb value
  }
  connector_sync_state {
    uuid id
    string connector_type
    string resource_id
    jsonb config
    jsonb cursor
    int sync_interval_min
    timestamptz last_sync_at
    string last_status
  }
```

`connector_sync_state` holds one row per configured source (GitHub repo, JIRA
project, Confluence space, Slack channel). `config` carries non-secret settings
plus a `token_env` pointer; `cursor` tracks incremental position;
`sync_interval_min` drives the scheduler. Synced documents land in
`document_chunks` / `vault_files` like any other ingested file.

## Resource Budget (Guideline)

| State | API RAM | Postgres RAM | Ollama RAM | Notes |
|---|---:|---:|---:|---|
| Idle | 20-80 MB | 80-180 MB | 200-400 MB | no active generation |
| Ingest burst | +150-400 MB | +20-80 MB | stable | depends on chunk fan-out |
| Active chat | +100-300 MB | +10-40 MB | 4-8 GB | model dominates |

## Reliability Controls

- Alembic migrations run at startup.
- Watcher debounce to avoid event storms.
- Queue-and-drain behavior for embedding outages.
- Single-DB durability and pg_dump backups.
- Docker restart policy + optional launchd autostart.
