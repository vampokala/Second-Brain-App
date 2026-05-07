# ECMP AI Dashboard — AWS EKS Deployment & Redis Caching Plan

> **Date:** 2026-04-03
> **Project:** `hotelops-osdchat-ecmp-ai-dashboard`
> **Context:** Planning deployment on AWS EKS with Vault (DB creds) and Redis cache

---

## 1. AWS Services Required

### Already Configured

| Service | Purpose | Status |
|---------|---------|--------|
| **Amazon RDS (PostgreSQL)** | Primary datastore | `asyncpg` pool, 17 tables, Vault-injected creds |
| **HashiCorp Vault** (via vault-operator) | Secrets management | In Helm values — DB creds, LLM API keys |
| **AWS ALB Ingress Controller** | HTTPS ingress | Configured via `ingress.hostname` in Helm values |
| **AWS Certificate Manager (ACM)** | TLS certs | `certManager: enabled: true` in Helm chart |
| **Artifactory** | Container registry | Base images + Python packages |

### To Provision

| Service | Purpose | Why |
|---------|---------|-----|
| **Amazon ElastiCache (Redis)** | Shared cache layer | Cross-pod caching, session sharing, job coordination |
| **AWS CloudWatch + Container Insights** | Logging & metrics | App logs to stdout (uvicorn) — needs aggregation |
| **Amazon S3** | CSV import staging, eval exports, backup | Large CSV imports currently stream through memory; S3 staging decouples upload from processing |
| **HPA (Horizontal Pod Autoscaler)** | Auto-scaling | Currently `autoscaling: enabled: false` — must enable for production |
| **PgBouncer sidecar** | DB connection pooling | At max 10 connections/pod × N replicas = pressure on RDS |

### Recommended Additions for Production

| Concern | Service/Config | Detail |
|---------|---------------|--------|
| **Observability** | OpenTelemetry + CloudWatch/Datadog | No tracing instrumentation exists today. LLM calls (300s timeouts), batch jobs, and eval runs need distributed tracing |
| **Rate limiting** | AWS WAF or NGINX Ingress annotations | The LLM proxy endpoint (`/api/llm/chat`) has no rate limiting. A single user can exhaust LiteLLM quota |
| **Job queuing** | Amazon SQS or Celery + Redis | Batch jobs (workbench batch, eval runner, mapping discovery, readiness generation) all run in-process via `asyncio.create_task`. If pod crashes mid-batch, all progress is lost |
| **Horizontal scaling** | Sticky sessions or external state | The app uses in-memory caches (auth, taxonomy) and in-process background jobs. Multiple replicas need Redis for shared state |
| **DB connection pooling** | PgBouncer sidecar | Current pool is max 10 per pod. At 3+ replicas, that's 30+ connections to RDS |
| **Backup/DR** | RDS automated snapshots + cross-region | Non-negotiable for production data |

---

## 2. Redis Cache Strategy — What to Store

### P0 — Critical (Hit on nearly every request or batch message)

#### A. Taxonomy Data (`taxonomy_data` table)

- **Current state:** The classifier router has a 60s in-memory TTL cache, but the taxonomy lookup endpoint, `build_capabilities_section()` (prompt builder), and batch runners all do **independent full-table scans** of the same data
- **Problem:** During a 200-message batch, `build_capabilities_section()` does 200 full-table scans
- **Redis key:** `cache:taxonomy:lookup`
- **TTL:** 300 seconds
- **Invalidate on:** `POST /api/taxonomy/bulk`, `POST /api/taxonomy/import-csv`, `PATCH /api/taxonomy/{key}`, `DELETE /api/taxonomy`
- **Size estimate:** ~50–200 KB

#### B. LLM Config (`settings` table, key `llm_config`)

- **Current state:** **No caching.** Every `/api/llm/chat`, `/api/llm/chat/sync`, and `/api/llm/models` call does `SELECT value FROM settings WHERE key = 'llm_config'`
- **Problem:** During streaming chat or batch eval, this fires per-request
- **Redis key:** `cache:settings:llm_config`
- **TTL:** 120 seconds
- **Invalidate on:** `PUT /api/llm/config`
- **Size estimate:** ~500 bytes

#### C. RBAC Sessions + User Permissions

- **Current state:** 60s in-memory TTL cache per pod. With multiple replicas, a user authenticated on Pod A gets a cache miss on Pod B
- **Redis key:** `cache:auth:session:{token}`
- **TTL:** 60 seconds (or match session expiry)
- **Invalidate on:** `POST /api/auth/logout`, `PUT /api/admin/users/{id}`, `PUT /api/admin/users/{id}/overrides`
- **Size estimate:** ~1–2 KB per session

### P1 — High Impact (Dashboard page loads, batch efficiency)

#### D. MARSHA Mapping Data (`marsha_mapping` table)

- **Current state:** Loaded once per batch (batch-local cache), but no cross-request cache
- **Redis key:** `cache:marsha:mapping`
- **TTL:** 300 seconds
- **Invalidate on:** `POST /api/marsha-mapping/bulk`, `POST /api/marsha-mapping/import-csv`, `DELETE /api/marsha-mapping`
- **Size estimate:** ~100–500 KB

#### E. Property Catalog (`prop_catalog` table)

- **Current state:** Batch-local dict cache. If you run 5 consecutive batches for the same property, the catalog JSONB blob is fetched 5 times
- **Redis key:** `cache:prop_catalog:{marsha_code}`
- **TTL:** 600 seconds
- **Invalidate on:** `POST /api/prop-catalog/bulk`, `POST /api/prop-catalog/import-csv`, `DELETE /api/prop-catalog`
- **Size estimate:** 10–50 KB per property

#### F. Model Pricing (`settings` table, key `model_pricing`)

- **Current state:** **No caching.** Every cost analytics endpoint loads pricing. A single cost page visit triggers 5 DB reads for the same data
- **Redis key:** `cache:settings:model_pricing`
- **TTL:** 3600 seconds (changes only on manual sync)
- **Invalidate on:** `POST /api/llm/pricing/sync`
- **Size estimate:** ~50–200 KB

#### G. Aggregations (pre-computed dashboard data)

- **Current state:** Already a two-tier pattern (compute + read). The read is a single-row PK fetch, but every dashboard page load hits it
- **Redis key:** `cache:aggregations:current`
- **TTL:** 120 seconds
- **Invalidate on:** `POST /api/aggregations/compute`
- **Size estimate:** ~100 KB–1 MB

### P2 — Nice to Have (Reduced DB pressure)

#### H. Settings (generic frequently-read keys)

- Keys: `brand_reference`, `routing_rules`, `model_ctx_limits`, `judge_prompt`, `discovery_prompt`
- **Redis key:** `cache:settings:{key}`
- **TTL:** 300 seconds
- **Invalidate on:** `PUT /api/settings/{key}`

#### I. Default Prompt Template

- **Redis key:** `cache:prompt_template:default`
- **TTL:** 300 seconds
- **Invalidate on:** `PUT /api/workbench/templates/{id}/default`, any template update

#### J. Row Counts (`/api/stats/row-counts`)

- Currently runs `SELECT COUNT(*)` across all 17 tables on every call
- **Redis key:** `cache:stats:row_counts`
- **TTL:** 60 seconds
- **Size estimate:** ~500 bytes

---

## 3. Redis Keyspace Layout

```
cache:taxonomy:lookup                     → Full taxonomy dict (P0, 300s TTL)
cache:settings:llm_config                 → LLM endpoints + API key (P0, 120s TTL)
cache:auth:session:{token}                → User + role + permissions (P0, 60s TTL)
cache:marsha:mapping                      → Intent→field mappings (P1, 300s TTL)
cache:prop_catalog:{marsha_code}          → Property catalog JSON (P1, 600s TTL)
cache:settings:model_pricing              → Model pricing table (P1, 3600s TTL)
cache:aggregations:current                → Pre-computed dashboard data (P1, 120s TTL)
cache:settings:{key}                      → Generic settings (P2, 300s TTL)
cache:prompt_template:default             → Default prompt template (P2, 300s TTL)
cache:stats:row_counts                    → Table row counts (P2, 60s TTL)
```

**Total Redis memory estimate:** ~2–5 MB for a typical deployment.

**Invalidation pattern:** Write-through invalidation. On every DB write to a cached entity, `DELETE` the corresponding Redis key. The next read triggers a cache-miss refill.

---

## 4. Scaling Concerns Specific to This App

1. **Background jobs are single-pod** — Workbench batch, eval runner, mapping discovery, and readiness generation all use `asyncio.create_task()` within a single process. With HPA scaling to N replicas, you need either:
   - A **job coordination layer** (Redis-backed distributed lock or SQS queue) to prevent duplicate job execution
   - Or designate one "worker" pod for background jobs (via a separate Deployment)

2. **SSE streaming ties up connections** — The `/api/llm/chat` endpoint holds an HTTP connection open for the entire LLM response. With multiple concurrent users streaming, you need enough pod resources and ALB idle timeout set high enough (default 60s may be too low for LLM responses).

3. **asyncpg pool per pod** — At `MAX_POOL_SIZE=10` and 3 replicas, you're opening 30 persistent connections to RDS. Consider PgBouncer as a sidecar or use RDS Proxy.

4. **CSV imports load into memory** — Large file imports (`/api/classification/import-csv`, etc.) stream the entire file into memory before bulk inserting. For production, consider S3 pre-staging with async processing.

---

## 5. Current Deployment Config Reference

- **Helm values:** `env/dev/mgp-tip-dev-use1/hotelops-osdchat-dev/hotelops-osdchat-ecmp-ai-dashboard.yaml`
- **PostgreSQL config:** `env/dev/mgp-tip-dev-use1/hotelops-osdchat-dev/postgresql.yml`
- **Dockerfile:** `Dockerfile` (multi-stage, `artifactory.marriott.com/base-images/python:3.10`)
- **App entry:** `uvicorn src.adapters.inbound.server:app --host 0.0.0.0 --port 8080`
- **Current resources:** 1 CPU / 1.5–2 GB RAM, single replica, autoscaling disabled
- **Vault path:** `global/dev1/dev1-osdchat-rds-cluster-aws-use1/users/rw`
- **Ingress hostname:** `ecmp-ai-dashboard.hotelops-osdchat-dev.dev.cld.marriott.com`

---

## 6. Existing In-Memory Caches (Already in Codebase)

| Cache | File | TTL | Scope |
|-------|------|-----|-------|
| Classifier taxonomy | `routers/classifier.py:16` | 60s | Per-pod |
| Auth session/perms | `auth.py:247` | 60s | Per-pod |
| Batch prop/tax/mapping | `workbench_batch.py:199` | Batch lifetime | Per-batch |
| Batch prop/tax/mapping | `eval_runner.py:176` | Batch lifetime | Per-batch |

These all need to be migrated to Redis for multi-replica consistency.
