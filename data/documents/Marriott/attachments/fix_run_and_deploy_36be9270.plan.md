---
name: Fix Run and Deploy
overview: Unify the port configuration, fix the production Dockerfile to build the frontend, clean up env vars, and establish clear local + Docker + Harness workflows.
todos:
  - id: fix-ports
    content: Standardize port to 8080 across Dockerfile.local CMD, docker-compose.yml, .env, vite.config.ts, startup.sh
    status: pending
  - id: fix-prod-dockerfile
    content: Add Node multi-stage frontend build to production Dockerfile
    status: pending
  - id: fix-startup-sh
    content: Remove --reload, read APP_PORT/APP_HOST/LOG_LEVEL from env
    status: pending
  - id: fix-dockerfile-local
    content: Make Dockerfile.local CMD read APP_PORT from environment
    status: pending
  - id: clean-env
    content: Remove dead DB_* vars from .env, update .env.example with clear per-scenario docs
    status: pending
  - id: fix-requirements
    content: Remove pytest-asyncio from requirements.txt (keep in requirements-dev.txt)
    status: pending
  - id: add-makefile
    content: Add Makefile with dev, docker, build-fe, test, lint targets
    status: pending
isProject: false
---

# Fix Run and Deploy for Local + Docker + Harness

## Problem Summary

Six independent issues prevent a clean local and CI/CD experience:

1. **Port mismatch** -- five files define different ports (9600, 9080, 8080). The Dockerfile.local hardcodes `--port 9080` in CMD, ignoring `APP_PORT` from `.env`.
2. **Production Dockerfile missing frontend build** -- [Dockerfile](emergingtech-tipai-ecmp-dashboard/Dockerfile) copies the repo but never runs `npm install` / `npm run build`. The React SPA won't exist in the production image.
3. **startup.sh uses `--reload`** -- [startup.sh](emergingtech-tipai-ecmp-dashboard/startup.sh) runs with `--reload` which is a dev-only flag, unsafe for production and Harness.
4. **Dead DB env vars** -- [.env](emergingtech-tipai-ecmp-dashboard/.env) has two conflicting sets (`DB_*` pointing at RDS, `POSTGRES_*` pointing at local). `settings.py` only reads `POSTGRES_*`, so the `DB_*` block is dead code that causes confusion.
5. **Test dep in runtime requirements** -- [requirements.txt](emergingtech-tipai-ecmp-dashboard/requirements.txt) includes `pytest-asyncio` which bloats the production image.
6. **No Makefile** -- common workflows (local dev, docker build, frontend build) require memorizing multi-step commands.

## Proposed Changes

### 1. Standardize on port 8080 everywhere

The Helm values and `settings.py` default already use 8080. Align everything to match:

- **`Dockerfile.local`** -- change CMD to use `${APP_PORT:-8080}` via shell form or an entrypoint script
- **`docker-compose.yml`** -- map `8080:8080`, set `APP_PORT=8080` in env
- **`.env`** -- change `APP_PORT=9600` to `APP_PORT=8080`
- **`vite.config.ts`** -- change proxy target from `localhost:9600` to `localhost:8080`
- **`startup.sh`** -- read `APP_PORT` env var instead of hardcoding 8080

This way: local bare-metal, Docker, and Harness all default to 8080. Override with `APP_PORT` if needed.

### 2. Add frontend build stage to production Dockerfile

Add a Node multi-stage build to [Dockerfile](emergingtech-tipai-ecmp-dashboard/Dockerfile), same pattern as `Dockerfile.local`:

```dockerfile
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM artifactory.marriott.com/base-images/python:3.10 AS builder
# ... existing Poetry install ...
COPY --from=frontend-builder /frontend/dist ./frontend/dist
```

For Harness behind the corporate proxy, npm will need Artifactory's npm registry or `--strict-ssl=false` (same as local).

### 3. Fix startup.sh for production safety

Replace hardcoded values with env-var-driven config:

```bash
#!/bin/bash
PORT="${APP_PORT:-8080}"
HOST="${APP_HOST:-0.0.0.0}"
LOG_LEVEL="${LOG_LEVEL:-info}"
poetry run uvicorn src.adapters.inbound.server:app \
  --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"
```

No `--reload` in production. Workers count can be added via `WEB_CONCURRENCY` env var later.

### 4. Make Dockerfile.local port-aware

Change the CMD from hardcoded `9080` to an entrypoint script (or shell form) that reads `APP_PORT`:

```dockerfile
CMD ["sh", "-c", "uvicorn src.adapters.inbound.server:app --host 0.0.0.0 --port ${APP_PORT:-8080} --log-level info --no-use-colors"]
```

### 5. Clean up .env and .env.example

- **Remove the dead `DB_*` block** from `.env` (lines 16-22) since `settings.py` never reads them
- **Update `.env.example`** with clear instructions for local-bare-metal vs Docker vs RDS scenarios
- **Remove credentials from `.env`** -- use `.env.local` (gitignored) for secrets, `.env` for non-sensitive defaults only

### 6. Remove test dep from runtime requirements

Remove `pytest-asyncio` from [requirements.txt](emergingtech-tipai-ecmp-dashboard/requirements.txt) -- it already exists in `requirements-dev.txt`.

### 7. Add a Makefile for common workflows

```makefile
dev:          # Local bare-metal: backend + frontend in parallel
docker:       # Docker compose up --build  
build-fe:     # cd frontend && npm install && npm run build
test:         # pytest
lint:         # ruff check + eslint
```

## How Each Environment Will Work After Changes

### Local bare-metal (fast iteration)

```
Terminal 1:  make dev-backend   # uvicorn --reload on :8080
Terminal 2:  make dev-frontend  # vite dev server on :3000, proxies /api to :8080
Browser:     http://localhost:3000
```

### Local Docker (production-like)

```
docker compose up --build       # builds frontend+backend, runs on :8080
Browser: http://localhost:8080/app
```

### Harness pipeline

```
docker build -f Dockerfile \
  --secret id=ARTIFACTORY_USERNAME,... \
  --secret id=ARTIFACTORY_TOKEN,... \
  -t artifactory.marriott.com/emergingtech/emergingtech-tipai-ecmp-dashboard:TAG .
```

Helm values inject `POSTGRES_*`, `LITELLM_*` via Vault. App listens on 8080. Health probes at `/actuator/health/{liveness,readiness}` on 8080.
