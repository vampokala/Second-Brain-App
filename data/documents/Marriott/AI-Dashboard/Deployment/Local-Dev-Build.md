# Local Development — Build & Run

> **Stack:** FastAPI · asyncpg · PostgreSQL (RDS) · Uvicorn  
> **Dockerfile:** `Dockerfile.local` (public Docker Hub image, no Artifactory creds needed)  
> **Last updated:** 2026-04-15

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker Desktop | 4.x+ | Ensure it's running |
| Python | 3.10+ | Only needed if running outside Docker |
| Poetry | 2.x | Only needed if running outside Docker |
| `.env` file | — | Copy from `.env.example`, fill in DB creds |

---

## 1. One-time Setup

### 1a. Create your `.env`
```bash
cp .env.example .env
# Edit .env — set POSTGRES_HOST_NAME, POSTGRES_DB_USERNAME, POSTGRES_DB_PASSWORD, etc.
```

Key variables to set in `.env`:

| Variable | Example | Notes |
|----------|---------|-------|
| `POSTGRES_HOST_NAME` | `your-rds-host.rds.amazonaws.com` | RDS endpoint or `host.docker.internal` if Postgres is local |
| `POSTGRES_PORT` | `5432` | |
| `POSTGRES_DB_USERNAME` | `dashboard` | |
| `POSTGRES_DB_PASSWORD` | `***` | |
| `POSTGRES_DB_NAME` | `marriott_dashboard` | |
| `POSTGRES_DB_SSLMODE` | `require` | Overridden to `disable` by docker-compose for local |
| `LITELLM_API_KEY` | `***` | Optional — for LLM workbench |

> **Note:** `docker-compose.yml` overrides `POSTGRES_DB_SSLMODE=disable` automatically.  
> The RDS CA is not in the corporate bundle, so cert verification is skipped locally.

---

## 2. Build & Run — Docker Compose (recommended)

```bash
# From the project root: emergingtech-tipai-ecmp-dashboard/

# First run or after Dockerfile.local / requirements.txt changes:
docker compose up --build

# Subsequent runs (no dependency changes):
docker compose up

# Teardown:
docker compose down
```

App will be available at: **http://localhost:9080**

### Useful log commands
```bash
# Follow logs in a second terminal:
docker compose logs -f dashboard

# Tail last 50 lines:
docker compose logs --tail=50 dashboard
```

---

## 3. Build & Run — Plain Docker (no compose)

```bash
# Build
docker build --platform linux/amd64 \
  -f Dockerfile.local \
  -t emergingtech-tipai-ecmp-dashboard .

# Run (loads your .env, connects to RDS)
docker run --rm \
  -p 8080:8080 \
  --env-file .env \
  -e POSTGRES_DB_SSLMODE=disable \
  --add-host host.docker.internal:host-gateway \
  emergingtech-tipai-ecmp-dashboard
```

---

## 4. Run Locally Without Docker (Poetry)

```bash
# Install dependencies
poetry install

# Run the app
poetry run uvicorn src.adapters.inbound.server:app \
  --host 0.0.0.0 --port 8080 \
  --reload --log-level debug
```

> **TLS note (CERTIFICATE_VERIFY_FAILED):** If Poetry install fails on SSL, set:
> ```bash
> export SSL_CERT_FILE=$HOME/.certs/combined-ca-bundle.crt
> export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE
> poetry install
> ```

---

## 5. Run Tests

```bash
# Unit tests (no DB needed)
poetry run pytest

# With coverage report
poetry run pytest --cov=src --cov-report=term-missing

# Skip integration tests (need live DB)
poetry run pytest -m "not integration"
```

---

## 6. Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| `CERTIFICATE_VERIFY_FAILED` | RDS CA not trusted in container | `POSTGRES_DB_SSLMODE=disable` in docker-compose (already set) |
| `Connection refused` on `localhost:5432` | DB is outside container network | Set `POSTGRES_HOST_NAME=host.docker.internal` in `.env` |
| `The option "--no-dev" does not exist` | Poetry 2.x removed `--no-dev` | Use `poetry install --only main` (fixed in `Dockerfile`) |
| `ENV PATH=...e` syntax error | Stray character in CI `Dockerfile` | Fixed — trailing `e` removed from line 20 |
| Port `9080` already in use | Another process | Change port mapping in `docker-compose.yml` |
