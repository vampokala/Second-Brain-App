# Second Brain — Instructions

A practical guide to **installing**, running, ingesting documents, and keeping
knowledge fresh from team sources (GitHub, JIRA, Confluence, Slack). For deeper
architecture see [ARCHITECTURE.md](ARCHITECTURE.md); for operational recovery see
[RUNBOOK.md](RUNBOOK.md). The repo root [README.md](../README.md) has Quickstart
and the API surface.

---

## 1. What this app is

A local-first "LLM Wiki": ingest your documents and team sources, then ask
citation-grounded questions against them. Under the hood it uses hybrid retrieval
(BM25 + pgvector with RRF fusion), cross-encoder reranking, citation tracking, and
multi-provider LLM routing (Ollama / OpenAI / Anthropic / Gemini).

The UI has **four sections**:

| Section | What it does |
|---|---|
| **Ask** | Multi-turn chat: personas, grounding toggles, Sources drawer, save-to-wiki, rolling memory, pin / regenerate / edit-fork. |
| **Knowledge** | **Browse** vault · **Add** (wide formats + cancel + capabilities) · **Connectors** (sync + ask about synced). |
| **Settings** | LLM keys, connector tokens, chat persona, Brave / web / vision / memory prefs. |
| **Help** | Demo-script cards + observability dashboard link. |

Theme: cycle **Light / System / Dark** from the top bar. Success and error feedback
uses shell toasts (ingest, chat, settings).

---

## 2. Prerequisites

- **Docker Desktop** (the whole stack runs in Compose).
- ~15 GB free disk for the API image, Ollama models, and Postgres (first image build alone can exceed ~10 GB).
- Optional: a vault folder of your own documents to index (`VAULT_HOST_PATH`).
- **No NVIDIA / CUDA GPU required.** Generation and embeddings run via Ollama (or cloud providers). Torch is only used for optional local cross-encoder reranking / NLI scoring and runs fine on CPU.

---

## 3. Install & run the stack

```bash
cd ~/Documents/Second-Brain-App   # or your clone path
cp .env.example .env             # then edit values (see §7)
make build && make up            # or: docker compose up -d --build
```

### First Docker build: large one-time downloads

The first `docker compose up -d --build` (or `make build`) installs Python deps including **PyTorch**. On Linux container arches, pip often resolves the default CUDA wheel set, so you may see multi-hundred-MB downloads such as:

- `torch-…-aarch64.whl` (~400+ MB)
- `nvidia_cudnn_…whl` (~400+ MB)
- related `nvidia-*` CUDA runtime wheels

This is a **one-time** cost for that image layer. Subsequent builds reuse the Docker cache unless `requirements/base.txt` (or the Dockerfile pip step) changes. Expect 20–40+ minutes on a typical home connection the first time; progress may look “stuck” while a single large wheel downloads.

Notes:

- CUDA packages improve throughput **only** on Linux hosts with a usable NVIDIA GPU. On **Docker Desktop for Mac**, those wheels still download but the container cannot use an NVIDIA GPU — reranking stays on CPU.
- You do not need to cancel the build if you see `nvidia_*` downloads; let the layer finish so it is cached.

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

Optional full rebuild of the index after you have documents in the vault:

```bash
make reindex
```

Optional autostart on macOS:

```bash
make install-launchd
```

### First 60 seconds in the UI

1. Land on **Ask** — a chat is created automatically; pick a seed question or type one (Enter sends).
2. Watch **Searching knowledge…**, then open **Sources** (titles, previews, scores, provenance).
3. Open **Settings** → set a **Chat persona** (optional Brave key for web search).
4. Click a source / **Open in vault** → **Knowledge → Browse**, or **Ask about this file**.
5. **Knowledge → Add** a `.xlsx` / `.pptx` / `.md` and confirm progress rows (use **Stop** if needed).
6. Optional: **Connectors** → sync a public GitHub repo → **Ask about synced items**.
7. **Help** → open the observability dashboard when demoing for engineers.

---

## 4. Ask (chat)

- **Composer:** Enter = send, Shift+Enter = newline. Never left disabled waiting for “New chat” on a fresh load.
- **Persona chip:** reflects Settings → Chat persona; click through to change role / student grade / addon.
- **Grounding:** corpus-only vs allow general knowledge; optional **Web search** when a Brave key is configured (Settings or `BRAVE_SEARCH_API_KEY`).
- **Last-send meta:** hits, persona, grounding mode under the composer after a reply.
- **Save to wiki / Update memory:** write the last assistant answer to `wiki/analyses/…`, or roll the thread into `context/memory.md` for future prompts.
- **Scope pills:** **Vault** vs **Global** (separate from demo session upload scopes under Knowledge → Add).
- **Sources:** citations + chunks; truthfulness badge when the backend scores the answer; copy on messages.
- **Actions:** pin / delete; regenerate; edit-fork. **Mobile:** conversations sheet.
- **Demo mode:** dismissible session chip on Ask only.

---

## 5. Ingest documents

In the UI, go to **Knowledge ▸ Add**. Three ways to ingest into the vault:

- **Files** — drag-and-drop. Supported types include `.pdf`, `.docx`, `.txt`, `.md`, `.html`, `.csv`/`.xlsx`, `.pptx`, `.ipynb`, common code/IaC, and (if enabled) images.
- **Text** — paste content with a target path under the vault.
- **URL** — fetch and extract a web page.

The header shows **ingest capabilities** (provider/model + extensions). While busy, **Stop** requests cancel. Unchanged files are skipped via content-hash (`.ingest-manifest.json`).

**Knowledge ▸ Ingest** — **Scan** lists new/changed vault files (for shared/external drops). Select files or directories with checkboxes, then **Ingest** to index only the selection. Progress and a final summary stream over SSE.

**Progress** shows human status rows (Running / Done / Error). Raw SSE JSON is folded under **Advanced · raw events**. Dropping files into the mounted vault folder (`VAULT_HOST_PATH`) still triggers the watcher.

**Browser Cursor-assist** (optional, no Cursor `workspaceStorage` reads): `POST /ingest/cursor-assist/prepare` → paste pack into Cursor → `preview` / `commit` JSON. See Lite’s corporate-cursor docs for the JSON shape; App keeps the browser-only path.

### Demo session uploads

When the API is in demo mode, **Add** also shows **Session uploads** with the
global / my uploads / both scope toggle. Those files stay private to the browser
session, expire after inactivity, and are **not** merged into the shared vault.

Browse what's indexed in **Knowledge ▸ Browse**; corpus counts show in the top bar.

---

## 6. Connectors — keep team knowledge fresh

**Knowledge ▸ Connectors** syncs external sources into the same pipeline, so synced
items become fully retrievable and citable.

> **MCP setup (recommended):** step-by-step for Atlassian, GitHub, GitHub Enterprise,
> Google Workspace, and custom MCP — including every extra `.env` / Cloud Console
> setting — is in [`MCP_CONNECTORS.md`](MCP_CONNECTORS.md).

### Set up a connector

1. Enter the token in the UI (**Settings → Connector credentials**, or the token field
   when adding a connector). Tokens are saved as app settings (masked on read) and
   applied to the running API without putting them on the connector row.
2. Alternatively, put the credential in `.env` / Compose and restart the API — env
   always wins over UI-saved values.
3. Click **Add connector**, choose a type, fill the fields (JIRA/Confluence need
   account **email** in the form), pick a **Sync schedule**, **Save**.
4. Click **Test** to verify connectivity, then **Sync now** for an immediate pull.
5. Watch the card’s syncing state; when finished, use **Ask about synced items**.

| Type | `resource_id` | Key config | Token (UI or env) |
|---|---|---|---|
| **GitHub** | `owner/repo` | branch (opt.), include issues/PRs | Settings / `GITHUB_TOKEN` (optional for public repos) |
| **JIRA** | project key | `base_url`, `email`, `jql` (opt.) | Settings / `JIRA_API_TOKEN` |
| **Confluence** | space key | `base_url`, `email` | Settings / `CONFLUENCE_API_TOKEN` |
| **Slack** | channel ID | include thread replies, `workspace_url` (opt.) | Settings / `SLACK_BOT_TOKEN` |

> **Tokens are never stored on the connector row.** UI saves go to `app_settings`
> (same pattern as LLM keys). Docker `.env` overrides UI if both are set.

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

## 7. Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `VAULT_HOST_PATH` | Host folder mounted into the API at `/vault`. |
| `POSTGRES_PASSWORD`, `POSTGRES_HOST_PORT` | Postgres password / host port (default 5433). |
| `VECTOR_BACKEND` | `pgvector` (default). |
| `EMBED_MODEL`, `LLM_DEFAULT_MODEL` | Embedding / default generation model. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Optional cloud LLM providers. |
| `BRAVE_SEARCH_API_KEY` | Optional; enables Ask web search (also via Settings). |
| `VISION_INGEST_ENABLED` | Optional `true`/`1` to allow image ingest placeholders. |
| `GITHUB_TOKEN` / `JIRA_API_TOKEN` / `CONFLUENCE_API_TOKEN` / `SLACK_BOT_TOKEN` | Connector credentials. |
| `CONNECTOR_SYNC_INTERVAL_MIN` | Global default sync cadence (0 = manual only). |

Cloud provider keys, persona prefs, Brave key, and vision toggle can also be managed in the **Settings** tab (Postgres `app_settings`; env wins for secrets).

**Settings → Chat persona:** `chat_persona`, `student_grade`, `persona_prompt_addon`, `rolling_memory_enabled`, `web_search_enabled`, `vision_ingest_enabled`. List roles via `GET /settings/personas`.

---

## 8. Connectors API (for scripting)

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

## 9. Development & tests

```bash
# Frontend (in ./frontend)
npm install
npm run dev            # Vite dev server on :5173 (proxies API to :8000)
npm run build          # type-check + production build
npm run test           # vitest unit tests
npm run test:e2e       # Playwright (expects API/dev setup per playwright.config)

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

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Vault ingest / empty corpus | Ensure Postgres is up and `VECTOR_BACKEND=pgvector`; ingest via **Knowledge → Add** or `make reindex`. |
| Connector **Test** fails (401/403) | Token missing — enter it in Settings or Add connector, or set the env var (§7) and restart. |
| Connector **Test** fails (404) | Wrong `resource_id` (repo / project / space key). |
| No answers / empty retrieval | Ingest documents first; confirm models are pulled (§3). |
| Composer disabled / no chats | Hard-refresh; Ask auto-creates a chat on load. |
| Docker build fails on `npm ci` | Ensure `frontend/.npmrc` is present/committed (§9). |
| Frontend Vitest workers time out | Retry: `npx vitest run --pool=threads --maxWorkers=1`. |
