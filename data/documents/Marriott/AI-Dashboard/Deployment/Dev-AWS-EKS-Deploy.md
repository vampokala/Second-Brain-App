# Dev Environment — AWS EKS Deploy

> **Pipeline:** Harness CI/CD  
> **Registry:** `artifactory.marriott.com/emergingtech-docker-local/`  
> **Project:** `tipai` · **Org:** `emergingtech`  
> **Dockerfile:** `Dockerfile` (Artifactory base image + Poetry + secrets)  
> **Last updated:** 2026-04-15

---

## Deploy Flow Overview

```
Feature Branch push
      │
      ▼
Harness CI Pipeline (CICD)
      │
      ├─ 1. Docker Build & Push  ──► Artifactory registry
      │      Dockerfile (Poetry, Artifactory secrets)
      │      Image tag: <branch>-<short-sha>-<build-id>
      │
      └─ 2. EKS Deploy  ──► Dev cluster
             Image tag injected into K8s manifest / Helm values
```

---

## 1. Trigger a Dev Deploy

### Via Git push (automatic)
```bash
git push origin feature/<your-branch>
# Harness pipeline triggers automatically on push
```

### Via Harness UI (manual re-run)
1. Go to: [Harness Pipeline](https://marriott.harness.io/ng/#/account/v9v9EP_lQrehegNHrzmF9Q/ci/orgs/emergingtech/projects/tipai/pipelines/CICD)
2. Select pipeline **CICD**
3. Click **Run** → choose branch → **Run Pipeline**

---

## 2. Image Naming Convention

```
artifactory.marriott.com/emergingtech-docker-local/emergingtech-tipai-ecmp-dashboard:<tag>

# Tag format:
<branch-slug>-<short-sha>-<build-number>

# Example:
feature-ai-dashboard-sync-e5cd6f1-1333
```

Cache image:
```
...emergingtech-tipai-ecmp-dashboard:cache
```

---

## 3. Manual Docker Build (CI-equivalent, run locally)

> Requires: VPN, Artifactory credentials, corporate CA bundle at `~/.certs/combined-ca-bundle.crt`

```bash
export ARTIFACTORY_USERNAME=<your-username>
export ARTIFACTORY_TOKEN=<your-token>

DOCKER_BUILDKIT=1 docker build --platform linux/amd64 \
  --secret id=CORP_CA_BUNDLE,src="${HOME}/.certs/combined-ca-bundle.crt" \
  --secret id=ARTIFACTORY_USERNAME,env=ARTIFACTORY_USERNAME \
  --secret id=ARTIFACTORY_TOKEN,env=ARTIFACTORY_TOKEN \
  -t artifactory.marriott.com/emergingtech-docker-local/emergingtech-tipai-ecmp-dashboard:<tag> \
  .
```

### Push to Artifactory
```bash
docker login artifactory.marriott.com \
  -u $ARTIFACTORY_USERNAME \
  -p $ARTIFACTORY_TOKEN

docker push artifactory.marriott.com/emergingtech-docker-local/emergingtech-tipai-ecmp-dashboard:<tag>
```

---

## 4. Dockerfile Key Points (CI `Dockerfile`)

| Step | Detail |
|------|--------|
| Base image | `artifactory.marriott.com/base-images/python:3.10` (RHEL/UBI8) |
| Package manager | Poetry 2.3.4 (pre-installed in base image) |
| Install command | `poetry install --only main --no-interaction` ⚠️ `--no-dev` removed in Poetry 2.x |
| Secrets | `ARTIFACTORY_USERNAME` + `ARTIFACTORY_TOKEN` via BuildKit `--secret` |
| PyPI index | `https://artifactory.marriott.com/artifactory/api/pypi/pypi/simple` |
| Runtime user | `marriott` (non-root, gid `10000`) |
| Entrypoint | `./startup.sh` → `poetry run uvicorn ... --port 8080` |
| Port | `8080` |

---

## 5. Harness Pipeline — Key Secrets

| Secret ID | Maps to |
|-----------|---------|
| `ARTIFACTORY_TOKEN` | Artifactory API token |
| `ARTIFACTORY_USERNAME` | Artifactory username |

Secrets are injected as BuildKit `--secret` mounts (not baked into image layers).

---

## 6. Environment Variables — Dev EKS

| Variable | Source | Notes |
|----------|--------|-------|
| `POSTGRES_HOST_NAME` | K8s secret / Vault | RDS Dev endpoint |
| `POSTGRES_DB_USERNAME` | K8s secret / Vault | |
| `POSTGRES_DB_PASSWORD` | K8s secret / Vault | |
| `POSTGRES_DB_SSLMODE` | K8s ConfigMap | `require` |
| `LITELLM_API_BASE` | K8s ConfigMap | Dev LiteLLM gateway |
| `LITELLM_API_KEY` | K8s secret / Vault | |
| `LITELLM_MODEL` | K8s ConfigMap | e.g. `claude-3-5-sonnet-20241022` |
| `ENV_NAME` | K8s ConfigMap | `development` |

---

## 7. Monitor the Deploy

### Harness execution URL pattern
```
https://marriott.harness.io/ng/#/account/v9v9EP_lQrehegNHrzmF9Q/ci/orgs/emergingtech/projects/tipai/pipelines/CICD/executions/<execution-id>/pipeline
```

### Check running pod (after EKS step completes)
```bash
# List pods
kubectl get pods -n emergingtech -l app=emergingtech-tipai-ecmp-dashboard

# Follow logs
kubectl logs -f -n emergingtech -l app=emergingtech-tipai-ecmp-dashboard

# Describe pod (events, image, env)
kubectl describe pod -n emergingtech <pod-name>
```

---

## 8. Rollback

### In Harness UI
1. Open the last successful pipeline execution
2. Click **Rollback** (if configured) or re-trigger with previous commit SHA

### Via kubectl (force previous image)
```bash
kubectl set image deployment/emergingtech-tipai-ecmp-dashboard \
  dashboard=artifactory.marriott.com/emergingtech-docker-local/emergingtech-tipai-ecmp-dashboard:<previous-tag> \
  -n emergingtech
```

---

## 9. Known Issues & Fixes

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| `The option "--no-dev" does not exist` | Poetry 2.x removed `--no-dev` | Changed to `--only main` in `Dockerfile` line 21 |
| `ENV PATH=...e` syntax error | Stray `e` character | Removed from `Dockerfile` line 20 |
| `CERTIFICATE_VERIFY_FAILED` (local) | RDS CA not in corporate bundle | `POSTGRES_DB_SSLMODE=disable` in `docker-compose.yml` |
