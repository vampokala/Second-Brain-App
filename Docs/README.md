# Documentation Hub

This folder contains implementation references and phase-level design notes.

## Core docs

- [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md): system architecture and execution surfaces (CLI/API/UI)
- [`ROADMAP.md`](ROADMAP.md): delivery status by phase
- [`performance_baseline.md`](performance_baseline.md): API overhead benchmark snapshot

## Phase docs

- [`phase1_core_infrastructure.md`](phase1_core_infrastructure.md): ingestion and indexing foundations
- [`phase2_hybrid_retrieval.md`](phase2_hybrid_retrieval.md): hybrid retrieval + RRF design
- [`phase3_reranking_generation.md`](phase3_reranking_generation.md): reranking + generation
- [`phase4_citation_api.md`](phase4_citation_api.md): citation API/UI goals (now partially implemented)

## Implementation-first entry points

- API: `src/api/main.py`
- UI: `src/web/streamlit_app.py`
- Orchestrator: `src/core/rag_orchestrator.py`
- Query CLI: `src/query.py`
- Ingest CLI: `src/ingest.py`
# Documentation Hub

Purpose: help different readers find the right project information quickly.  
Audience: visitors, engineering reviewers, and contributors.  
Reading time: 2-3 minutes.

## Start here by audience

- First-time visitors and interview loops: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)
- Engineers evaluating architecture: [`phase2_hybrid_retrieval.md`](phase2_hybrid_retrieval.md), [`phase3_reranking_generation.md`](phase3_reranking_generation.md)
- Contributors and maintainers: project root [`README.md`](../README.md)

## Documentation map

```mermaid
flowchart LR
  rootReadme[RootREADME] --> docsHub[DocsHub]
  docsHub --> projOverview[ProjectOverview]
  docsHub --> roadmapDoc[Roadmap]
  docsHub --> phase1Doc[Phase1]
  docsHub --> phase2Doc[Phase2]
  docsHub --> phase3Doc[Phase3]
  docsHub --> phase4Doc[Phase4]
```

## Core docs

- Project summary and outcomes: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)
- Public phase progress: [`ROADMAP.md`](ROADMAP.md)
- Foundation/infrastructure: [`phase1_core_infrastructure.md`](phase1_core_infrastructure.md)
- Hybrid retrieval details: [`phase2_hybrid_retrieval.md`](phase2_hybrid_retrieval.md)
- Reranking + generation: [`phase3_reranking_generation.md`](phase3_reranking_generation.md)
- Citation and API work: [`phase4_citation_api.md`](phase4_citation_api.md)

## Repo quick links

- Main project guide: [`../README.md`](../README.md)
- Query CLI entrypoint: [`../src/query.py`](../src/query.py)
- Core retrieval module: [`../src/core/hybrid_retriever.py`](../src/core/hybrid_retriever.py)
