# Documentation Hub

Reference and design docs for **Second-Brain-App** — a local-first LLM wiki that
ingests your documents and team sources and answers citation-grounded questions
over them (React UI + FastAPI + Postgres/pgvector + Ollama).

## Start here

- **Using the app** (setup, ingest, connectors, scheduler): [`INSTRUCTIONS.md`](INSTRUCTIONS.md)
- **What it is & how it's designed**: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)
- **Architecture & schema**: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- **Operations & recovery**: [`RUNBOOK.md`](RUNBOOK.md)

## Reference

- [`Second_Brain_ClaudProject_Context.md`](Second_Brain_ClaudProject_Context.md): full grounding doc — runtime topology, data flow, API surface, code map
- [`QUALITY_SOFT_LAUNCH.md`](QUALITY_SOFT_LAUNCH.md): quality tooling and gates
- [`verify-queries.md`](verify-queries.md): verification query suite
- [`ROADMAP.md`](ROADMAP.md): delivery status by phase

## Design history (how the core was built)

These describe the original design of the RAG core; some specifics have since
evolved (e.g. the vector store is Postgres/pgvector, not Chroma).

- [`phase1_core_infrastructure.md`](phase1_core_infrastructure.md): ingestion & indexing foundations
- [`phase2_hybrid_retrieval.md`](phase2_hybrid_retrieval.md): hybrid retrieval + RRF
- [`phase3_reranking_generation.md`](phase3_reranking_generation.md): reranking + generation
- [`phase4_citation_api.md`](phase4_citation_api.md): citation system & API
- [`phase5_observability.md`](phase5_observability.md) / [`Phase5-Monitoring-Observability.md`](Phase5-Monitoring-Observability.md): monitoring & observability
- [`performance_baseline.md`](performance_baseline.md): API overhead benchmark snapshot

## Code entry points

- API + lifespan + routing: [`../src/api/main.py`](../src/api/main.py)
- RAG orchestrator: [`../src/core/rag_orchestrator.py`](../src/core/rag_orchestrator.py)
- Ingest pipeline: [`../src/core/ingest_pipeline.py`](../src/core/ingest_pipeline.py)
- Connectors (GitHub/JIRA/Confluence) + scheduler: [`../src/core/connectors/`](../src/core/connectors/)
- React frontend: [`../frontend/src/`](../frontend/src/)
