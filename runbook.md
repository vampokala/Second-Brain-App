# Second-Brain-App Runbook

This runbook provides full step-by-step instructions to build, deploy, launch, and use the product locally.

## 1) Prerequisites

- macOS with Docker Desktop installed and running.
- Project directories:
  - `~/Documents/Second-Brain`
  - `~/Documents/Second-Brain-App`
- Verify Docker daemon:

```bash
docker info
```

## 2) Open project directory

```bash
cd ~/Documents/Second-Brain-App
```

## 3) Configure environment

Create your env file:

```bash
cp .env.example .env
```

Open `.env` and verify at minimum:

- `VAULT_HOST_PATH=/Users/vamshipokala/Documents/Second-Brain`
- `POSTGRES_PASSWORD=localdev`

Optional:

- Add `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `GROQ_API_KEY`.
- Tune `MAX_INGEST_WORKERS`, `WATCHER_DEBOUNCE_MS`, `OLLAMA_KEEP_ALIVE`.

## 4) Build and start stack

```bash
make build
make up
make status
```

Expected services:

- `postgres`
- `api`
- `ollama`

## 5) Pull required Ollama models

```bash
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama list
```

## 6) Verify API health

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/config/llm
```

Expected:

- Health returns `status: ok`.
- LLM config returns provider/model configuration.

## 7) Initial full indexing

Preferred (async trigger):

```bash
make reindex
```

Blocking mode (wait until complete):

```bash
curl -s -X POST http://localhost:8000/admin/reindex-sync
```

Check vault stats:

```bash
curl -s http://localhost:8000/vault/stats
```

## 8) Launch the UI

Open:

- `http://localhost:8000`

This is the main web app.

## 9) How to use the product

### 9.1 Ingest content

You can ingest in three ways:

1. Auto watcher: drop files into `~/Documents/Second-Brain/raw/`
2. UI Ingest tab: upload file, paste text, or ingest URL
3. API:
   - `POST /ingest`
   - `POST /ingest/text`
   - `POST /ingest/url`

### 9.2 Chat with your knowledge base

1. Open Chat tab in UI.
2. Ask a question about vault content.
3. Review retrieved context/citations if shown.

### 9.3 Browse vault files

Use UI or API:

- `GET /vault/files`
- `GET /vault/files/{path}`
- `GET /vault/stats`

### 9.4 Manage settings

- Use UI settings or `GET /settings` / `PATCH /settings`.
- Environment variables in `.env` continue to override defaults.

## 10) Daily operations

```bash
make up
make down
make restart
make status
make logs
make smoke
```

Database shell:

```bash
make dbshell
```

## 11) Backup and restore

Create backup:

```bash
make backup
```

Restore backup:

```bash
gunzip -c backups/secondbrain-YYYY-MM-DD.sql.gz | docker compose exec -T postgres psql -U secondbrain secondbrain
```

## 12) Optional auto-start on login

Install launchd jobs:

```bash
make install-launchd
launchctl list | grep secondbrain
```

Remove launchd jobs:

```bash
make uninstall-launchd
```

## 13) Troubleshooting

### UI not loading

```bash
make status
make logs
```

### API health fails

```bash
curl -s http://localhost:8000/health
docker compose logs api
```

### No new results after adding files

```bash
make reindex
```

### Ollama/model issues

```bash
docker compose logs ollama
docker compose exec ollama ollama list
```

If model RAM is insufficient, close heavy applications and retry with a smaller configured model.

### Docker issues

- Restart Docker Desktop.
- Re-run:

```bash
make up
make status
```

### Port conflict on Ollama

If host port `11434` is occupied by local Ollama, map compose Ollama to another host port (for example `11435`) and keep internal service networking unchanged.
