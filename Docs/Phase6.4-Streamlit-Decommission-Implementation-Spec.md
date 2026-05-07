# Phase 6.4 Implementation Spec: Streamlit Decommission

Source plan: `Docs/Phase6.4-Streamlit-Decommission-Plan.md`
Depends on: `Docs/Phase6.3-Container-Cutover-Plan.md`
Optional phase: execute only after the Docker React deployment has stabilized.

## Objective

Remove the Streamlit runtime, legacy UI path, and Streamlit-only tests after the React + FastAPI Docker deployment is stable and rollback to Streamlit is no longer required.

The final system should have one supported user interface:

- React SPA served by FastAPI.
- FastAPI APIs for querying, session uploads, metrics, health, and sample prompts.
- No Streamlit dependency, process, compose service, or documentation path.

## Entry Criteria

Start this phase only when all are true:

- Phase 6.3 has been deployed for at least one week.
- No unresolved severity 1 or severity 2 issues exist for the React + FastAPI Docker runtime.
- The team explicitly confirms Streamlit rollback is no longer needed.
- The Phase 6.3 rollback procedure has been tested and documented.
- A current branch or tag exists that can restore the Streamlit implementation if needed later.

## Non-Goals

- Do not change retrieval, reranking, citation, or provider behavior.
- Do not change session isolation semantics.
- Do not redesign the React UI.
- Do not remove shared ingestion helpers that are still used by API upload endpoints.
- Do not delete demo sample prompts; move them to an API-served shared source.

## Implementation Sequence

### 1. Inventory Streamlit References

Find all active references before deleting anything:

```bash
rg "streamlit|8501|src/web/streamlit_app|DOC_INGEST_API_URL|_DEMO_QUESTIONS" .
```

Classify each match:

- Delete: Streamlit runtime, Streamlit command, Streamlit-only tests.
- Replace: documentation and quickstart references.
- Keep: generic `src/web` helper modules used by the API, such as `ingestion_service.py` and `session_corpus.py`.

Expected Streamlit-specific items to remove or update:

- `src/web/streamlit_app.py`
- `streamlit>=...` in `requirements/base.txt`
- `streamlit` service in `docker/docker-compose.yml`
- `tests/unit/test_streamlit_demo_routing.py`
- Streamlit SDK references in `README.md` and `spaces/README.md`
- Port `8501` references in docs and Docker metadata

### 2. Move Sample Prompts to a Shared API Source

The Streamlit app currently owns `_DEMO_QUESTIONS`. The React app currently has a shorter hard-coded prompt list in `frontend/src/components/SamplePromptChips.tsx`.

Create a backend-owned shared source before deleting Streamlit.

Recommended file:

```text
src/api/sample_prompts.py
```

Recommended content shape:

```python
SAMPLE_PROMPTS: tuple[str, ...] = (
    "What is Retrieval-Augmented Generation?",
    "What are the two main phases of a RAG system?",
    "How does hybrid retrieval work?",
    "What is BM25 and how does it differ from vector search?",
    "What are the weaknesses of BM25?",
    "What is Reciprocal Rank Fusion (RRF)?",
    "What is a vector database?",
    "What is HNSW?",
    "What is the difference between Chroma and Qdrant?",
    "Why use hybrid retrieval instead of just dense vector search?",
    "What failure mode does citation tracking help detect?",
    "How are embeddings used in a RAG pipeline?",
)
```

Add an API endpoint in `src/api/main.py`:

```text
GET /api/sample-prompts
```

Response contract:

```json
{
  "prompts": [
    "What is Retrieval-Augmented Generation?"
  ]
}
```

Best practices:

- Keep the endpoint unauthenticated. It is static demo content.
- Register it before the SPA static mount.
- Keep response shape stable and explicit.
- If API models are used for typed responses, add a small Pydantic response model.
- Add the endpoint to frontend OpenAPI generation if the frontend consumes generated types.

### 3. Update React Sample Prompt Consumption

Replace the hard-coded prompt array in `frontend/src/components/SamplePromptChips.tsx` with API-backed data.

Recommended approach:

- Add `getSamplePrompts()` to `frontend/src/api/client.ts`.
- Use TanStack Query in either `SamplePromptChips` or the parent `QueryTab`.
- Render a small loading state or skeleton while prompts load.
- Provide a local fallback only for network failure, using the same canonical prompt text as the backend. Keep the fallback clearly secondary so backend remains the source of truth.

Testing requirements:

- Unit test that prompts returned by the API render as chips.
- Unit test that selecting a prompt still fills the query text and resets scope to Global if that behavior already exists.
- Unit test the failure fallback or empty-state UI.

### 4. Delete Streamlit Runtime Code

Delete:

```text
src/web/streamlit_app.py
```

Keep:

```text
src/web/ingestion_service.py
src/web/session_corpus.py
```

Reason:

- `ingestion_service.py` and `session_corpus.py` are no longer UI code only; FastAPI session upload endpoints depend on them.
- The package name `src.web` can remain for now to avoid a broad refactor. A later cleanup may move these helpers into `src/api` or `src/services`.

After deletion, run:

```bash
rg "src.web.streamlit_app|streamlit_app|_DEMO_QUESTIONS" src tests frontend Docs README.md spaces
```

Expected result:

- No runtime references remain.
- `_DEMO_QUESTIONS` has been replaced by `SAMPLE_PROMPTS`.

### 5. Remove Streamlit Dependency

Edit `requirements/base.txt`:

- Remove `streamlit>=1.37.0`.
- Keep `requests`, `fastapi`, `python-multipart`, and `uvicorn` because the API still needs them.

Validation:

```bash
python -m pip install -r requirements/base.txt
PYTHONPATH=. python -m pytest tests/unit -q
```

Best practice:

- If a lockfile is introduced later, regenerate it in the same change.
- Do not remove dependencies solely because they were imported by Streamlit unless no remaining module imports them.

### 6. Simplify Docker Compose

Edit `docker/docker-compose.yml`:

- Remove the `streamlit` service.
- Remove port `8501`.
- Keep `api`, `redis`, `qdrant`, and shared volumes.
- Ensure the API service exposes the React UI through `8000`.
- Add demo env vars to the API service only if local compose should support demo uploads by default.

Recommended local URL after this phase:

```text
http://localhost:8000
```

Compose validation:

```bash
docker compose -f docker/docker-compose.yml up --build
curl -fsS http://127.0.0.1:8000/health
open http://127.0.0.1:8000
```

### 7. Update Dockerfile and HF Files

Review files touched in Phase 6.3:

- `docker/Dockerfile`
- `spaces/README.md`
- `spaces/app.py`

Required outcomes:

- No `EXPOSE 8501`.
- No Streamlit command.
- No Streamlit SDK metadata.
- No docs claiming `spaces/app.py` is the Streamlit entrypoint.

If `spaces/app.py` is no longer used:

- Delete it only if HF Docker runtime and local workflows do not import it.
- Keep `spaces/bootstrap_demo.py` if the Docker startup path still uses it.

If `spaces/app.py` is kept as a bootstrap helper:

- Remove all Streamlit imports and comments.
- Keep only demo env defaults/bootstrap logic that is still called.

### 8. Update Documentation

Update `README.md`:

- Replace Streamlit quickstart with React + FastAPI quickstart.
- Change Docker instructions to open `http://localhost:8000`.
- Update architecture bullets:
  - `src/api/` serves FastAPI routes and the React SPA.
  - `frontend/` contains the React app.
  - `src/web/` should not be described as the UI layer if it remains only for helper modules.
- Remove screenshots or text that show the Streamlit sidebar.
- Add sample prompt endpoint reference if useful for frontend/API developers.

Update `spaces/README.md`:

- Confirm it describes Docker SDK and app port `8000`.
- Remove upload-disabled Streamlit limitations if Phase 6.1 uploads are enabled.
- Describe the supported upload caps and TTL.

Update any runbooks or phase docs that still instruct users to run:

```bash
streamlit run src/web/streamlit_app.py
```

Replace with:

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

or, for unified container:

```bash
docker build -f docker/Dockerfile -t doc-ingest:demo .
docker run --rm -p 8000:8000 doc-ingest:demo
```

### 9. Remove or Replace Streamlit Tests

Delete:

```text
tests/unit/test_streamlit_demo_routing.py
```

Add or extend tests so the removed behavior remains covered through API and React tests:

- API test for `GET /api/sample-prompts`.
- API test that demo upload/session routes still work when `DOC_PROFILE=demo` and `DOC_DEMO_UPLOADS=1`.
- Frontend test that sample prompts render from API data.
- Frontend test that sample prompt selection populates the query.
- Playwright smoke that loads the unified UI and runs a global sample prompt.

Important:

- Do not reduce coverage for provider/model request passing, session scope, or citation provenance if those were previously asserted through Streamlit tests.
- Move assertions to API or frontend tests rather than deleting them outright.

## Validation Checklist

Run after implementation:

```bash
rg "streamlit|8501|src/web/streamlit_app|_DEMO_QUESTIONS" .
```

Expected allowed matches:

- Historical phase docs may mention Streamlit as completed/decommissioned context.
- No active runtime, dependency, compose, CI, or README quickstart references should remain.

Backend:

```bash
PYTHONPATH=. python -m pytest tests/unit -q
PYTHONPATH=. python -m pytest tests/integration -q
PYTHONPATH=. uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

API smoke:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/sample-prompts
curl -fsS http://127.0.0.1:8000/
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Docker:

```bash
docker build -f docker/Dockerfile -t doc-ingest:demo .
docker run --rm -p 8000:8000 \
  -e DOC_PROFILE=demo \
  -e DOC_DEMO_UPLOADS=1 \
  -e DOC_EMBEDDING_PROVIDER=sentence_transformers \
  doc-ingest:demo
```

Manual smoke:

- Open `http://127.0.0.1:8000`.
- Confirm the React UI loads.
- Confirm sample prompt chips load from the API.
- Run a global sample prompt.
- Upload one small supported file.
- Query with `Mine` scope and verify citation provenance.
- Clear the session and confirm a new session is minted.

## Rollback Plan

Rollback after this phase is no longer the normal operating path. If rollback is required, use the saved Phase 6.3 branch/tag.

Emergency rollback steps:

1. Restore `src/web/streamlit_app.py`.
2. Restore `streamlit` in `requirements/base.txt`.
3. Restore the `streamlit` service in `docker/docker-compose.yml`.
4. Restore Streamlit SDK metadata in `spaces/README.md` if rolling HF back to the old runtime.
5. Restore `spaces/app.py` Streamlit launcher behavior.
6. Re-run backend tests and a Streamlit smoke test.

Because Phase 6.4 intentionally removes the rollback path, require team approval before merging it.

## Acceptance Criteria

- Streamlit runtime code is removed.
- `streamlit` dependency is removed.
- Docker Compose has no Streamlit service or `8501` port.
- HF and Docker docs describe only React + FastAPI on port `8000`.
- Sample prompts are served by `GET /api/sample-prompts` and consumed by the React UI.
- API, frontend, e2e, and Docker smoke checks pass.
- No active runtime or onboarding docs instruct users to run Streamlit.

## Handoff

After merge:

- Mark Phase 6.4 complete in the phase index.
- Record the final React + FastAPI deployment URL and smoke-test date.
- Move any deferred cleanup, such as relocating `src/web/ingestion_service.py`, to the Phase 7 backlog.
