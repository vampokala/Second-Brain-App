# Doc-Ingestion Implementation Playbook

Use this playbook when the request is broad ("implement X") and you need a consistent delivery path.

## 1) Classify the Change

- Retrieval quality: `src/core/retriever.py`, `src/core/reranker.py`, orchestrator wiring
- Provider/model behavior: `src/core/llm_provider.py`, config allowlists/defaults
- API behavior: `src/api/` routes, schemas, middleware
- UI behavior: `src/web/streamlit_app.py` and related helpers
- Ingestion/data pipeline: `src/ingest.py`, document processing, indexing/storage

## 2) Keep Compatibility

- Preserve existing endpoint names and payload fields unless explicitly told to break/replace.
- Keep provider selection optional and request-scoped where already supported.
- Keep citations available in query outputs when requested.

## 3) Preferred Development Order

1. Add/update config flags with safe defaults.
2. Implement core behavior.
3. Wire API/CLI/UI entry points.
4. Add/update tests.
5. Update docs (`README.md` + `Docs/RUNBOOK.md` when operational impact exists).

## 4) Verification Matrix

- **Core logic**: unit tests for deterministic behavior and edge cases
- **API**: endpoint smoke plus auth and streaming path checks
- **Ingestion**: ingest small sample docs and verify retrieval returns grounded chunks
- **Ops**: confirm any new env vars are documented

## 5) Done Criteria

- Feature works end-to-end for intended path (CLI/API/UI as applicable)
- No regressions in existing retrieval/citation behavior
- Tests pass for touched areas
- Operator-facing instructions are updated
