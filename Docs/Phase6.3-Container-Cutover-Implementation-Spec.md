# Phase 6.3 Implementation Spec: Single-Container Deploy and HF Spaces Cutover

Source plan: `Docs/Phase6.3-Container-Cutover-Plan.md`
Depends on: `Docs/Phase6.2-React-MVP-Plan.md`
Next phase: `Docs/Phase6.4-Streamlit-Decommission-Plan.md`

## Objective

Ship the React MVP and FastAPI API from one Docker container, then cut Hugging Face Spaces from the Streamlit SDK runtime to the Docker SDK runtime.

The deployed container must:

- Serve the built React SPA at `/`.
- Keep API endpoints reachable with their current contracts.
- Preserve the Streamlit rollback path until Phase 6.4.
- Continue to support demo session uploads, scoped retrieval, citations, and health checks.

## Current State

- `frontend/` already has npm scripts for `lint`, `typecheck`, `test`, `test:e2e`, and `build`.
- `.github/workflows/ci.yml` already contains a frontend job, but e2e execution should be reviewed because the Playwright config currently starts only the Vite dev server.
- `docker/Dockerfile` runs FastAPI on port `8000` and still exposes `8501`.
- `spaces/README.md` still declares `sdk: streamlit`, `sdk_version`, and `app_file: spaces/app.py`.
- `spaces/app.py` still starts FastAPI in a background thread and delegates to `src.web.streamlit_app`.
- `src/api/main.py` does not yet mount the React build output as static UI.

## Non-Goals

- Do not delete `src/web/streamlit_app.py`.
- Do not remove `streamlit` from `requirements/base.txt`.
- Do not remove the Streamlit service from `docker/docker-compose.yml`.
- Do not change the `/health`, `/metrics`, `/query`, or `/query/stream` API payload contracts.
- Do not introduce a second production web server such as nginx unless a concrete deployment issue requires it.

## Implementation Sequence

### 1. Confirm Phase 6.2 Readiness

Before editing deployment files, verify the React app is buildable and API-compatible:

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
```

Expected result:

- `frontend/dist/` is produced reproducibly.
- The frontend does not require a hard-coded `VITE_API_BASE_URL` when served from the same origin.
- Playwright tests can run against a backend URL that represents the deployment shape.

If Playwright currently depends on a separate dev API, update the e2e setup in this phase so CI boots FastAPI in demo mode before running the browser tests.

### 2. Update `docker/Dockerfile`

Convert the Dockerfile to a multi-stage build.

Recommended structure:

1. `frontend-builder` stage based on `node:20-alpine`.
2. Python runtime stage based on the existing `python:3.11-slim`.
3. Copy `frontend/package.json` and `frontend/package-lock.json` before copying all frontend files so npm dependencies cache properly.
4. Run `npm ci` and `npm run build`.
5. Copy `frontend/dist` into the runtime image at `/app/static`.
6. Keep `PYTHONPATH=/app`, Hugging Face cache env vars, non-root `appuser`, and the existing FastAPI `CMD`.
7. Remove `EXPOSE 8501` from the final runtime image.

Best practices:

- Use `npm ci`, not `npm install`, in image builds.
- Keep dependency installation before source copies where practical for Docker cache reuse.
- Keep the final container single-process: uvicorn only.
- Keep Streamlit installed for rollback during Phase 6.3, but do not run it in the final container command.
- Preserve the existing `/health` Docker healthcheck.

Acceptance checks:

- `docker build -f docker/Dockerfile -t doc-ingest:demo .` succeeds from repo root.
- `docker run` starts uvicorn on port `8000`.
- `/app/static/index.html` exists in the image.
- No runtime process listens on port `8501` in the unified image.

### 3. Mount React Static Assets in `src/api/main.py`

Serve the SPA only after API routes have been registered.

Implementation requirements:

- Import `Path` and `StaticFiles`.
- Resolve the static directory relative to the deployed app, for example `/app/static` in Docker and `static/` from the repo root locally.
- Mount static assets only if the directory exists and contains `index.html`.
- Register all API routes before mounting the catch-all UI route.
- Ensure SPA fallback does not shadow `/health`, `/metrics`, `/query`, `/query/stream`, `/sessions`, `/observability/dashboard`, or OpenAPI docs.

Recommended route strategy:

- Keep existing routes at their current paths for backward compatibility.
- Add optional `/api` aliases only if the frontend needs them, but do not remove current top-level API paths.
- Mount `StaticFiles(directory=..., html=True)` at `/` after all current route decorators.

Testing focus:

- `GET /` returns the React app when `static/index.html` exists.
- `GET /assets/...` serves bundled frontend assets.
- Unknown browser routes fall back to the SPA.
- API routes continue to return JSON and do not return `index.html`.
- OpenAPI remains available at `/openapi.json`.

### 4. Rework `spaces/app.py` for Docker Runtime

In Docker SDK mode, HF Spaces will run the container command, so `spaces/app.py` no longer needs to launch Streamlit.

Preferred implementation:

- Keep `spaces/app.py` as a thin bootstrap utility only if it is still useful for local or HF startup.
- Move demo env defaults into the Docker runtime or a small bootstrap function used by the Docker entrypoint.
- Continue to set:
  - `DOC_PROFILE=demo`
  - `DOC_API_KEYS=demo-key`
  - `DOC_EMBEDDING_PROVIDER=sentence_transformers`
  - `DOC_DEMO_UPLOADS=1`
  - `DOC_DEMO_SESSION_ROOT=/tmp/doc-ingest-sessions`
  - `DOC_DEMO_MAX_FILES=3`
  - `DOC_DEMO_MAX_FILE_MB=3`
  - `DOC_DEMO_MAX_SESSION_MB=8`
  - `DOC_DEMO_SESSION_TTL=1800`
- Ensure `spaces.bootstrap_demo.bootstrap_if_needed()` still runs before traffic depends on the sample corpus.

Acceptable options:

- Add an entrypoint script that runs bootstrap, then `exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 1`.
- Or keep Docker `CMD` as uvicorn and move bootstrap into FastAPI lifespan startup, guarded so it only runs in demo profile.

Best practice:

- Prefer `exec` in shell entrypoints so uvicorn receives container signals directly.
- Keep bootstrap idempotent.
- Do not start background API threads in Docker SDK mode.

### 5. Update `spaces/README.md`

Change Hugging Face Spaces metadata:

```yaml
sdk: docker
app_port: 8000
```

Remove:

```yaml
sdk_version: "1.37.0"
app_file: spaces/app.py
```

Refresh user-facing text:

- Describe the React + FastAPI demo.
- Mention session uploads are enabled in demo mode with the configured limits.
- Point users to the root URL on port `8000` for the UI.
- Keep provider/API-key limitations accurate for HF.

### 6. Review `.github/workflows/ci.yml`

The frontend job already exists. Review and adjust it so it reflects the deployment contract:

- Keep `npm ci`, `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`.
- Add a dedicated e2e job or e2e steps that start FastAPI in demo mode before Playwright runs.
- Use `DOC_PROFILE=demo`, `DOC_DEMO_UPLOADS=1`, and `DOC_EMBEDDING_PROVIDER=sentence_transformers` for e2e.
- Wait for `http://127.0.0.1:8000/health` before launching browser tests.
- Keep Python and Node caches scoped to the correct lockfiles.

Recommended e2e smoke:

```bash
PYTHONPATH=. DOC_PROFILE=demo DOC_DEMO_UPLOADS=1 \
  DOC_EMBEDDING_PROVIDER=sentence_transformers \
  uvicorn src.api.main:app --host 127.0.0.1 --port 8000

cd frontend
npm run test:e2e
```

### 7. Review `.github/workflows/sync-to-spaces.yml`

Keep this workflow lean. Hugging Face should build the Docker image from the pushed repo.

Implementation notes:

- Update comments that still say HF uses `spaces/app.py` as the entry point.
- Do not add a prebuild unless HF Docker builds are too slow or unreliable.
- Keep the repo push behavior aligned with the current release process.
- Ensure `spaces/README.md` is included in the pushed content so HF detects Docker SDK metadata.

## Local Verification

Run these checks before opening a PR:

```bash
PYTHONPATH=. python -m pytest tests/unit -q
PYTHONPATH=. python -m pytest tests/integration -q

cd frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
cd ..

docker build -f docker/Dockerfile -t doc-ingest:demo .
docker run --rm -p 8000:8000 \
  -e DOC_PROFILE=demo \
  -e DOC_DEMO_UPLOADS=1 \
  -e DOC_EMBEDDING_PROVIDER=sentence_transformers \
  doc-ingest:demo
```

Smoke checks while the container is running:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/metrics
curl -fsS http://127.0.0.1:8000/openapi.json
curl -fsS http://127.0.0.1:8000/ | head
```

Browser checks:

- Open `http://127.0.0.1:8000`.
- Confirm the React UI loads without Vite.
- Create or reuse a demo session.
- Upload one small supported file.
- Query with `Mine` scope and confirm citation provenance.
- Query with `Global` scope and confirm existing sample corpus still works.
- Refresh the browser and confirm the session resumes or remints cleanly.

## Hugging Face Spaces Verification

Recommended cutover flow:

1. Deploy to a fresh validation Space first, for example `doc-ingestion-demo-v2`.
2. Confirm the Space is using Docker SDK metadata.
3. Wait for Docker build completion.
4. Smoke-test:
   - `/`
   - `/health`
   - `/metrics`
   - `/openapi.json`
   - `POST /sessions`
   - document upload
   - scoped query
   - streaming query fallback behavior
5. Validate logs for bootstrap, model download, and session janitor errors.
6. Only then switch the public demo target.

## Rollback Plan

Rollback must remain available until Phase 6.4 is intentionally executed.

Fast rollback:

- Revert `spaces/README.md` to Streamlit SDK metadata:
  - `sdk: streamlit`
  - `sdk_version: "1.37.0"`
  - `app_file: spaces/app.py`
- Restore the pre-cutover `spaces/app.py` behavior that starts FastAPI in a thread and delegates to Streamlit.
- Keep `src/web/streamlit_app.py` and `streamlit` dependency untouched during Phase 6.3.

Container rollback:

- Revert the Dockerfile to the previous Python-only image if the multi-stage build breaks HF.
- Keep the React app and backend changes in the branch if they are not the cause.

Rollback validation:

- HF Space boots in Streamlit SDK mode.
- Streamlit UI loads.
- `/health` is reachable from the background FastAPI server.
- Sample prompts still work.

## Acceptance Criteria

- One Docker image serves FastAPI and the built React SPA.
- `/`, static assets, and client-side browser routes work from the container.
- `/health`, `/metrics`, `/query`, `/query/stream`, `/sessions`, and `/openapi.json` keep expected behavior.
- HF Spaces runs the Docker SDK Space on `app_port: 8000`.
- CI validates backend tests, frontend checks, frontend build, and e2e smoke against a running FastAPI backend.
- Streamlit rollback is documented and tested.

## Handoff to Phase 6.4

Do not start Phase 6.4 until:

- React demo has soaked for at least one week in the Docker deployment.
- No unresolved severity 1 or severity 2 deployment/runtime defects remain.
- The team confirms Streamlit rollback is no longer needed.
- The rollback steps above were tested at least once during cutover.
