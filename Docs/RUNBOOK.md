# Project Runbook

This runbook describes how to start, run, validate, and troubleshoot Doc-Ingestion in both local and Docker environments.

## 1) Prerequisites

- OS: macOS/Linux/WSL
- Python: 3.11+ recommended for Docker parity
- Docker + Docker Compose plugin
- Ollama installed and running (for local models)
- Optional cloud model API keys (OpenAI/Anthropic/Gemini)

## 2) Repository setup (local)

```bash
git clone <your-repo-url>
cd Doc-Ingestion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/base.txt
```

## 3) Model setup

### 3.1 Ollama models

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

### 3.2 Optional cloud model keys

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
```

### 3.3 Hugging Face cache for reranker (recommended)

Keep reranking enabled while avoiding repeated model downloads:

```bash
export HF_HOME="$HOME/.cache/huggingface"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export SENTENCE_TRANSFORMERS_HOME="$HF_HOME/sentence_transformers"
```

Optional one-time warmup (local):

```bash
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
```

## 4) Configuration

Main config: `config.yaml`

Important sections:

- `generation`: default model, cache TTL
- `llm`: provider defaults + allowlists
- `api`: auth + rate limiting

### 4.1 API auth

Use one of:

- `api.api_keys` list in `config.yaml`
- or env var `DOC_API_KEYS` with comma-separated values

Example:

```bash
export DOC_API_KEYS="dev-key-1,dev-key-2"
export DOC_API_KEY="dev-key-1"   # Streamlit client key used for API calls
```

Note: local Ollama query requests can run without `X-API-Key`; cloud-provider requests still require API auth when enabled.
You can also paste the API key directly in the Streamlit sidebar (`Session Security`) and keep it session-scoped.
For cloud providers, you can paste provider keys in Streamlit (`Provider Keys (session-only)`) so they are sent per request without writing to disk.

### 4.2 Redis distributed limiter

Set:

- `api.redis_rate_limit_enabled: true`
- `api.redis_url: redis://localhost:6379/0`

If Redis is unavailable, API automatically falls back to in-memory limiter.

## 5) Ingest documents

Place files in `data/documents/` and run:

```bash
python -m src.ingest --docs data/documents
```

Verify artifacts:

- BM25 index: `data/embeddings/bm25_index.json`
- Chroma data: `data/embeddings/chroma/`

## 6) Start services locally

### 6.1 API

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6.2 Streamlit UI

In another terminal:

```bash
export DOC_API_KEY="dev-key-1"
PYTHONPATH=. streamlit run src/web/streamlit_app.py
```

Open:

- API: `http://localhost:8000/health`
- UI: `http://localhost:8501`

## 7) API usage

### 7.1 Health

```bash
curl http://127.0.0.1:8000/health
```

### 7.2 Query

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-1" \
  -d '{
    "query":"How does hybrid retrieval work?",
    "provider":"ollama",
    "model":"qwen2.5:7b",
    "top_k":5,
    "include_citations":true
  }'
```

### 7.3 Streaming query (SSE)

```bash
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-1" \
  -d '{
    "query":"Stream explanation of reranking",
    "provider":"openai",
    "model":"gpt-4o-mini",
    "stream":true
  }'
```

## 8) Start with Docker Compose

Compose file: `docker/docker-compose.yml`

Optional env file bootstrap:

```bash
cp docker/.env.example docker/.env
```

### 8.1 Build + start

```bash
docker compose -f docker/docker-compose.yml up --build
```

Docker image preloads reranker model weights during build:

```bash
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
```

and compose persists HF caches in `hf_cache` volume to avoid re-downloading.

### 8.1.1 Optional offline mode (air-gapped runtime)

After prewarming caches, run containers with HF network calls disabled:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 docker compose -f docker/docker-compose.yml up --build
```

Notes:

- Set offline flags only after cache is populated.
- If a model is missing from cache, offline mode will fail fast instead of downloading.

Services started:

- `api` on `:8000`
- `streamlit` on `:8501`
- `redis` on `:6379`
- `qdrant` on `:6333`

### 8.2 Start detached

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

### 8.3 Stop

```bash
docker compose -f docker/docker-compose.yml down
```

### 8.4 Stop and remove volumes

```bash
docker compose -f docker/docker-compose.yml down -v
```

## 9) Logs and audit events

API emits structured JSON audit events:

- `auth_success`, `auth_failed`
- `query_success`, `query_failed`
- `stream_success`, `stream_failed`

View logs:

```bash
docker compose -f docker/docker-compose.yml logs -f api
```

## 10) Operational checks

- Health: `GET /health`
- Metrics: `GET /metrics` with `X-API-Key`
- Rate limit check: run bursts and verify `429`
- Cloud provider check: confirm API key env vars and provider/model allowlist

## 11) Troubleshooting

### 11.1 API returns 401

- Missing or invalid `X-API-Key`
- `DOC_API_KEYS`/`api.api_keys` mismatch

### 11.2 API returns 503 on protected endpoints

- Auth enabled but no API keys configured

### 11.3 API returns 429 quickly

- `api.rate_limit_per_minute` too low
- shared key used by many clients

### 11.4 Redis unavailable

- Verify Redis container/service is up
- Check `api.redis_url`
- API should still run via in-memory fallback

### 11.5 Empty retrieval output

- Re-run ingestion
- Validate `data/embeddings` artifacts exist
- Ensure query has relevant corpus content

### 11.6 Ollama connection errors in Docker

- On macOS/Windows keep `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- Ensure Ollama service is running and model is pulled

### 11.7 Anthropic model not found

- If you see `not_found_error` for Anthropic model aliases, update `config.yaml` `llm.allowed_models_by_provider.anthropic`.
- Current recommended Anthropic model IDs in this project:
  - `claude-sonnet-4-6`
  - `claude-haiku-4-5`

### 11.8 Gemini model not found

- If you see Gemini `NOT_FOUND` errors, use current configured IDs:
  - `gemini-2.5-flash`
  - `gemini-2.5-pro`
- The app calls the `v1beta` generateContent endpoint; model availability can vary by account and region.

## 12) Validation checklist (before release)

- Unit tests pass:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit -q
```

- API smoke tests:
  - `/health`
  - authenticated `/query`
  - authenticated `/query/stream`
- UI smoke tests:
  - Query tab works with local provider
  - Ingest tab uploads and ingests file

## 13) Rollback

1. Roll back to previous image/tag or git revision.
2. Restart services.
3. Run smoke tests from section 12.
4. Verify ingestion + query on known document.
