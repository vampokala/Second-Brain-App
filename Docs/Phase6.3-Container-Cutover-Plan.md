# Phase 6.3 Plan: Single-Container Deploy and HF Spaces Cutover

Source of truth: `Docs/Phase6-RefactorDemo_React.md` (this file is an execution slice for iterative delivery).
Depends on: `Docs/Phase6.2-React-MVP-Plan.md`

## Objective

Deploy one container (FastAPI + built React SPA) to simplify delivery and align Hugging Face Spaces runtime with the new UI.

## Scope

Migrate from Streamlit SDK Space to Docker SDK Space with rollback path preserved.

## Files to modify

- `docker/Dockerfile`
  - Multi-stage build:
    - Node stage builds `frontend/dist`
    - Python stage copies static assets to `/app/static`
  - Final command runs uvicorn only.
- `src/api/main.py`
  - Mount static UI when available.
  - Keep API route behavior intact (`/health`, `/metrics`, `/query`, `/query/stream`).
  - Ensure SPA fallback does not shadow API routes.
- `spaces/README.md`
  - Switch to:
    - `sdk: docker`
    - `app_port: 8000`
  - Remove `app_file` streamlit setting.
- `spaces/app.py`
  - Repurpose as thin env bootstrap + uvicorn launcher, or remove if no longer needed.
- `.github/workflows/sync-to-spaces.yml`
  - Keep CI lean; prefer relying on HF Docker build unless prebuild is required.
- `.github/workflows/ci.yml`
  - Add frontend job (`lint`, `test`, `build`).
  - Add e2e job booting API + running Playwright.

## Verification

```bash
docker build -f docker/Dockerfile -t doc-ingest:demo .
docker run --rm -p 8000:8000 \
  -e DOC_PROFILE=demo -e DOC_DEMO_UPLOADS=1 \
  -e DOC_EMBEDDING_PROVIDER=sentence_transformers \
  doc-ingest:demo
open http://127.0.0.1:8000
```

Then push branch and validate HF Space after Docker rebuild.

## Handoff (Exit Criteria)

- Unified container runs locally and in HF with expected route behavior.
- Core API endpoints stay reachable and validated.
- Deployed smoke tests pass.
- Rollback path to pre-cutover setup is documented and tested.

## Transition to Phase 6.4

- React demo has soaked for at least one week.
- No unresolved high-severity deployment/runtime defects.
- Team confirms Streamlit rollback is no longer needed.
