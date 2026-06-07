# Second Brain — Instructions

A practical guide to running the app, ingesting documents, and keeping knowledge
fresh from team sources (GitHub, JIRA, Confluence). For deeper architecture see
[ARCHITECTURE.md](ARCHITECTURE.md); for operational recovery see [RUNBOOK.md](RUNBOOK.md).

---

## 1. What this app is

A local-first "LLM Wiki": ingest your documents and team sources, then ask
citation-grounded questions against them. Under the hood it uses hybrid retrieval
(BM25 + pgvector with RRF fusion), cross-encoder reranking, citation tracking, and
multi-provider LLM routing (Ollama / OpenAI / Anthropic / Gemini).

The UI has **four sections**:

| Section | What it does |
|---|---|
| **Ask** | Chat (multi-turn) and Quick ask (single-shot with citations + retrieval details). |
| **Knowledge** | Browse the indexed vault, Add documents (file / text / URL), and configure Connectors. |
| **Settings** | LLM provider API keys and default models. |
| **Help** | How scopes, citations, and scoring work. |

---

## 2. Prerequisites

- **Docker Desktop** (the whole stack runs in Compose).
- ~8 GB free disk for models and Postgres.
- Optional: a vault folder of your own documents to index.

---

## 3. Run the stack

```bash
cp .env.example .env          # then edit values (see §6)
docker compose up -d          # starts postgres, api, ollama
```

Services and ports:

| Service | Container | URL / Port |
|---|---|---|
| API + built frontend | `second-brain-app-api-1` | http://127.0.0.1:8000 |
| Postgres (pgvector) | `second-brain-app-postgres-1` | localhost:5433 (db/user `secondbrain`) |
| Ollama | `second-brain-app-ollama-1` | http://127.0.0.1:11435 |

Open **http://127.0.0.1:8000**. Check health any time:

```bash
curl -s http://127.0.0.1:8000/health
```

> Database migrations run automatically on API startup (`alembic upgrade head`).

### First run: pull the local models

```bash
docker exec second-brain-app-ollama-1 ollama pull nomic-embed-text   # embeddings
docker exec second-brain-app-ollama-1 ollama pull llama3.1:8b        # generation
```

---

## 4. Ingest documents

In the UI, go to **Knowledge ▸ Add**. Three ways to ingest:

- **Files** — drag-and-drop `.pdf`, `.docx`, `.txt`, `.md`, `.html`.
- **Text** — paste content with a target path.
- **URL** — fetch and extract a web page.

Live progress streams into the panel. You can also drop files into the mounted
vault folder (`VAULT_HOST_PATH`) and the file watcher ingests them automatically.

Browse what's indexed in **Knowledge ▸ Browse**; corpus counts show in the top bar.

---

## 5. Connectors — keep team knowledge fresh

**Knowledge ▸ Connectors** syncs external sources into the same pipeline, so synced
items become fully retrievable and citable.

### Set up a connector

1. Put the credential in an environment variable (see §6) and restart the API.
2. Click **Add connector**, choose a type, fill the fields, pick a **Sync schedule**, **Save**.
3. Click **Test** to verify connectivity, then **Sync now** for an immediate pull.

| Type | `resource_id` | Key config | Token env var |
|---|---|---|---|
| **GitHub** | `owner/repo` | branch (opt.), include issues/PRs | `GITHUB_TOKEN` |
| **JIRA** | project key | `base_url`, `email`, `jql` (opt.) | `JIRA_API_TOKEN` |
| **Confluence** | space key | `base_url`, `email` | `CONFLUENCE_API_TOKEN` |
| **Slack** | channel ID | include thread replies, `workspace_url` (opt.) | `SLACK_BOT_TOKEN` |

> **Secrets are never stored in the database** — only a pointer to the env var is
> kept. GitHub works on public repos without a token (rate-limited).

### Scheduler (automatic ingestion)

Each connector has its own cadence: **Manual / 15 min / Hourly / 6 hours / Daily**.
A background scheduler ticks every 60s and runs any connector whose interval has
elapsed; the same connector never runs twice concurrently. Syncs are **incremental**
(a stored cursor means only new/updated items are pulled). Each card shows the
schedule badge, last sync, and next sync time. `CONNECTOR_SYNC_INTERVAL_MIN` acts as
a global default for connectors left on "Manual only".

Synced records land under `raw/connectors/<type>/<resource>/<id>.md` with frontmatter
(source, external id, URL, author, timestamp).

---

## 6. Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `VAULT_HOST_PATH` | Host folder mounted into the API at `/vault`. |
| `POSTGRES_PASSWORD`, `POSTGRES_HOST_PORT` | Postgres password / host port (default 5433). |
| `VECTOR_BACKEND` | `pgvector` (default). |
| `EMBED_MODEL`, `LLM_DEFAULT_MODEL` | Embedding / default generation model. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Optional cloud LLM providers. |
| `GITHUB_TOKEN` / `JIRA_API_TOKEN` / `CONFLUENCE_API_TOKEN` / `SLACK_BOT_TOKEN` | Connector credentials. |
| `CONNECTOR_SYNC_INTERVAL_MIN` | Global default sync cadence (0 = manual only). |

Cloud provider keys can also be managed per-provider in the **Settings** tab.

---

## 7. Connectors API (for scripting)

```bash
B=http://127.0.0.1:8000
curl -s $B/connectors                                   # list
curl -s -X POST $B/connectors -H 'Content-Type: application/json' \
  -d '{"connector_type":"github","resource_id":"owner/repo","config":{},"sync_interval_min":60}'
curl -s -X POST $B/connectors/<id>/test                 # connectivity check
curl -s -X POST $B/connectors/<id>/sync                 # trigger a sync
curl -s    $B/connectors/<id>/status                    # last/next sync state
curl -s -X DELETE $B/connectors/<id>                    # remove
```

Sync progress is published on the shared ingest stream: `GET /events/ingest`.

---

## 8. Development & tests

```bash
# Frontend (in ./frontend)
npm run dev            # Vite dev server on :5173 (proxies API to :8000)
npm run build          # type-check + production build
npm run test           # vitest unit tests
npx playwright test    # e2e (reuses a running dev server)

# Backend changes are baked into the api image — rebuild to apply:
docker compose build api && docker compose up -d api
```

> **Note:** `frontend/.npmrc` (`legacy-peer-deps=true`) is required for `npm ci` in
> the Docker build — make sure it is committed, or CI/teammate builds will fail on a
> known eslint/sonarjs peer-dependency conflict.

The runtime image does not include `pytest`. To run backend tests, install them in
the container and copy the test files in:

```bash
docker exec second-brain-app-api-1 pip install -q pytest pytest-asyncio
docker cp tests/unit/. second-brain-app-api-1:/app/tests/unit/
docker exec second-brain-app-api-1 python -m pytest /app/tests/unit -o asyncio_mode=auto -q
```

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| "Vault ingest is not configured" | Set `DATABASE_URL` and `VECTOR_BACKEND=pgvector`; the API needs Postgres. |
| Connector **Test** fails (401/403) | Token missing or lacks scope — set the env var (§6) and restart the API. |
| Connector **Test** fails (404) | Wrong `resource_id` (repo / project / space key). |
| No answers / empty retrieval | Ingest documents first; confirm models are pulled (§3). |
| Docker build fails on `npm ci` | Ensure `frontend/.npmrc` is present/committed (§8). |
