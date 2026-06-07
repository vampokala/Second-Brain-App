---
name: doc-ingestion
description: Implements and extends the Doc-Ingestion local-first RAG system using existing project architecture, retrieval patterns, API/UI contracts, and validation workflow. Use when adding new ingestion, retrieval, reranking, citation, provider, API, Streamlit, config, or performance features in this repository.
---

# Doc-Ingestion Skill

## Purpose

Apply this skill for implementation tasks in this repository so new work stays aligned with the existing RAG architecture and operational conventions.

## Project Defaults

- Keep the system local-first and retrieval-grounded.
- Preserve hybrid retrieval flow: BM25 + vector -> weighted RRF -> optional rerank.
- Keep citation-aware generation behavior intact when modifying generation paths.
- Reuse existing config-driven behavior in `config.yaml` and `src/utils/config.py`.
- Prefer extending existing modules over creating parallel abstractions.

## Code Areas

- `src/core/`: retrieval, reranking, orchestration, generation, citations, LLM routing
- `src/api/`: FastAPI endpoints, request/response contracts, auth/rate-limit middleware behavior
- `src/web/`: Streamlit query and ingest UX
- `src/utils/`: config, vector DB integration, shared utilities
- `src/ingest.py` and `src/query.py`: CLI entry points
- `tests/unit/` and `tests/integration/`: expected safety net for behavior changes

## Implementation Workflow

1. Confirm where the change belongs (`core`, `api`, `web`, `utils`, CLI, or docs).
2. Prefer minimal, composable edits in current modules before adding new files.
3. Keep provider/model selection per-request where relevant (API/UI).
4. For retrieval changes, maintain determinism and stable ranking semantics.
5. For API changes, keep `/health`, `/metrics`, `/query`, `/query/stream` contracts consistent unless explicitly asked to version/break them.
6. Update docs when behavior or operator commands change.

## Guardrails

- Do not hardcode secrets or API keys.
- Keep cloud providers optional and environment-driven.
- Preserve fallback behavior (for example, Redis limiter fallback to in-memory).
- Avoid introducing breaking schema changes in API payloads unless requested.
- Keep naming consistent with existing terminology: ingestion, hybrid retrieval, rerank, citation, provider, model.

## Validation Checklist

Run the smallest relevant checks first, then broader checks:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit -q
PYTHONPATH=. .venv/bin/python -m pytest tests/integration -q
```

For API changes, verify:

- `GET /health`
- authenticated `POST /query`
- authenticated `POST /query/stream`

For ingestion/retrieval changes, re-run ingest on `data/documents` and validate grounded responses.

## Common Commands

```bash
python -m src.ingest --docs data/documents
python -m src.query "What are the key project phases?"
uvicorn src.api.main:app --reload --port 8000
PYTHONPATH=. streamlit run src/web/streamlit_app.py
```

## Output Expectations For Future Tasks

When implementing features with this skill:

- explain which subsystem is being changed and why
- list edited files
- run and report relevant validation steps
- call out any config/env updates needed for operators

## Additional References

- Architecture and usage: [README.md](../../../README.md)
- Operations and troubleshooting: [Docs/RUNBOOK.md](../../../Docs/RUNBOOK.md)
- Delivery status and milestones: [Docs/ROADMAP.md](../../../Docs/ROADMAP.md)
